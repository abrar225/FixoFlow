"""Explicit, cancellable provisioning; dictation never downloads a model.

Only pinned public model files are fetched. A complete pack is promoted from a
private staging directory after validation; a failed install cannot replace a
working pack. No audio, identifiers, API keys or transcripts are transmitted.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.request

# Sizes and Git/LFS digests from the pinned repositories' file metadata.
PACKS = {
    'mlx': {
        'repo': 'mlx-community/whisper-base-mlx',
        'revision': '1e3e249fb8d01c655324bd6841b1deadffd6d04c',
        'files': {
            'config.json': (262, 'git-sha1', '3860125a7f82a556e43e28eda7147a51c802ba5a'),
            'weights.npz': (143724204, 'sha256', '2f57d5f3ef473054c638961f90716f4ee415e8108de81313eccb2c5fd62eff0b'),
            'README.md': (341, 'git-sha1', '0e0b81afa0d31463f15b14d2db75efe4147a4df3'),
        },
    },
    'cpu': {
        'repo': 'Systran/faster-whisper-base',
        'revision': 'ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66',
        'files': {
            'config.json': (2309, 'git-sha1', '867cf1a0fece1394e01d55e287ba2f09a577c046'),
            'model.bin': (145217532, 'sha256', 'd01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9'),
            'tokenizer.json': (2203239, 'git-sha1', '7818adb6de9fa3064d3ff81226fdd675be1f6344'),
            'vocabulary.txt': (459861, 'git-sha1', 'c9074644d9d1205686f16d411564729461324b75'),
            'README.md': (1991, 'git-sha1', 'cddfec65ffb3e3df45d2234f09f3d261bf9a9c0a'),
        },
    },
    # Evaluation-only: the application's install button always selects Base.
    'mlx-small': {
        'repo': 'mlx-community/whisper-small-mlx',
        'revision': '45f3915923c7a79a5a5b5a7d909d39aeb0e5630e',
        'files': {
            'config.json': (266, 'git-sha1', 'df4c65c442a30e50034ee63422b31bde60c3d407'),
            'weights.npz': (481307592, 'sha256', '55b6674c9b339702d486e2b1573839a66f8ec8f821ed2886993ef717a86b09f5'),
            'README.md': (343, 'git-sha1', '8996da18aab170971998d5fe7548a2cc1c50eefd'),
        },
    },
}
_VALIDATED = {}
_VALIDATION_LOCK = threading.Lock()


def backend(): return 'mlx' if sys.platform == 'darwin' else 'cpu'


def pack_path(kind=None):
    kind = kind or backend()
    return Path.home()/'.fixoflow'/'models'/('small-mlx' if kind == 'mlx-small' else 'base-'+kind)


def validate_model_language(config, kind):
    """Reject English-only/custom incompatible weights at the model boundary."""
    if not isinstance(config, dict):
        raise ValueError('Model configuration must be a JSON object.')
    if kind.startswith('mlx'):
        vocab = config.get('n_vocab')
        multilingual = type(vocab) is int and vocab >= 51865
    else:
        languages = config.get('lang_ids')
        multilingual = (isinstance(languages, list) and len(languages) >= 99
                        and all(type(x) is int and x > 0 for x in languages)
                        and len(set(languages)) == len(languages))
    if not multilingual:
        raise ValueError('This is not a compatible multilingual model.')


def _verify_file(file, expected):
    size, algorithm, digest = expected
    if file.stat().st_size != size:
        raise ValueError('Model file has an unexpected size: '+file.name)
    hasher = hashlib.sha256() if algorithm == 'sha256' else hashlib.sha1()
    if algorithm == 'git-sha1':
        hasher.update(f'blob {size}\0'.encode())
    with file.open('rb') as stream:
        while block := stream.read(1024*1024):
            hasher.update(block)
    if hasher.hexdigest() != digest:
        raise ValueError('Model file failed integrity validation: '+file.name)


def validate_pack(path, kind):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Model pack must be a regular directory.')
    signatures = []
    for name in PACKS[kind]['files']:
        file = path/name
        if file.is_symlink() or not file.is_file():
            raise ValueError('Multilingual pack is incomplete: '+name)
        stat = file.stat()
        signatures.append((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
    key = (str(path.resolve()), kind)
    # Reuse a verified pack only while all result-affecting files are unchanged.
    # The cache retains at most one location per kind; it never stores weights.
    with _VALIDATION_LOCK:
        if _VALIDATED.get(kind) == (key, signatures):
            return path
    for name, expected in PACKS[kind]['files'].items():
        _verify_file(path/name, expected)
    try:
        config = json.loads((path/'config.json').read_text())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid model configuration.') from error
    validate_model_language(config, kind)
    with _VALIDATION_LOCK:
        _VALIDATED[kind] = (key, signatures)
    return path


class ModelPackManager:
    def __init__(self, kind=None, directory=None):
        self.kind = kind or backend()
        self.path = Path(directory) if directory else pack_path(self.kind)
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._worker = None
        self._stage = None
        self._closing = False
        self._status = {'state': 'not_installed', 'bytes': 0,
                        'message': 'Base multilingual pack is optional. About 150 MB; local recognition after installation.'}
        try:
            validate_pack(self.path, self.kind)
            self._status.update(state='ready', message='Base multilingual pack is installed locally.')
        except (ValueError, OSError, json.JSONDecodeError):
            pass

    def snapshot(self):
        with self._lock:
            return dict(self._status)

    def _publish(self, **changes):
        with self._lock:
            self._status.update(changes)

    def start(self):
        with self._lock:
            if self._closing:
                return
            if self._worker and self._worker.is_alive():
                return
            try:
                self._cleanup_stage()
            except OSError as error:
                self._status.update(state='error', message=f'Model staging cleanup needs retry: {error}')
                return
            try:
                validate_pack(self.path, self.kind)
                self._status.update(state='ready', message='Multilingual pack is already installed locally.')
                return
            except (ValueError, OSError, json.JSONDecodeError):
                pass
            self._cancel.clear()
            self._status.update(state='downloading', bytes=0,
                                message='Downloading the selected Base multilingual model; no audio is sent.')
            self._worker = threading.Thread(target=self._download, name='FixoFlow-model-pack', daemon=True)
            self._worker.start()

    def cancel(self): self._cancel.set()

    def close(self, timeout=2):
        with self._lock:
            self._closing = True
            self.cancel()
            worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout)
        if worker and worker.is_alive():
            return False
        try:
            self._cleanup_stage()
        except OSError as error:
            self._publish(state='error', message=f'Model staging cleanup needs retry: {error}')
            return False
        return True

    def _cleanup_stage(self):
        if self._stage is not None:
            if self._stage.exists():
                shutil.rmtree(self._stage)
            self._stage = None

    def _download(self):
        stage = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._cleanup_stage()
            stage = Path(tempfile.mkdtemp(prefix='.base-download-', dir=self.path.parent))
            self._stage = stage
            spec = PACKS[self.kind]
            hashes = {}
            total = 0
            for name, expected in spec['files'].items():
                url = f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{name}"
                request = urllib.request.Request(url, headers={'User-Agent': 'FixoFlow-model-installer'})
                digest = hashlib.sha256()
                size = 0
                with urllib.request.urlopen(request, timeout=30) as response, (stage/name).open('xb') as target:
                    while True:
                        if self._cancel.is_set():
                            raise InterruptedError('Model installation cancelled. The existing model was preserved.')
                        block = response.read(1024*1024)
                        if not block:
                            break
                        size += len(block)
                        total += len(block)
                        if size > expected[0]:
                            raise ValueError('Model file exceeds the allowed pack size.')
                        target.write(block)
                        digest.update(block)
                        self._publish(bytes=total, message=f'Downloading {name} · {total//1_000_000} MB received')
                    target.flush()
                    os.fsync(target.fileno())
                _verify_file(stage/name, expected)
                hashes[name] = digest.hexdigest()
            validate_pack(stage, self.kind)
            (stage/'pack-manifest.json').write_text(json.dumps(
                {'repository': spec['repo'], 'revision': spec['revision'], 'sha256': hashes}, indent=2))
            if self._cancel.is_set():
                raise InterruptedError('Model installation cancelled.')
            # Never overwrite any existing directory, even malformed caller data.
            if self.path.exists():
                validate_pack(self.path, self.kind)
            else:
                stage.rename(self.path)
            self._publish(state='ready', message='Multilingual pack is ready locally. Choose a language and save preferences.')
        except Exception as error:
            self._publish(state='cancelled' if isinstance(error, InterruptedError) else 'error', message=str(error))
        finally:
            if self._stage is not None:
                try:
                    self._cleanup_stage()
                except OSError as error:
                    self._publish(state='error', message=f'Model staging cleanup needs retry at {stage}: {error}')

"""Verified model provisioning with explicit download, cancellation and warm-up.

Only catalog assets are downloaded; no audio or transcript leaves the computer.
Downloads do not overwrite existing installations, including damaged directories.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from urllib.request import Request, urlopen

from fixoflow.models.catalog import CATALOG, ModelSpec, runtime_backend, compatible_backend

_VERIFIED = {}
_VERIFY_LOCK = threading.Lock()


def model_root():
    return Path.home() / '.fixoflow' / 'models' / 'catalog'


def verify_model(path, spec: ModelSpec):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Selected model is not installed. Download it explicitly in Settings.')
    signatures = []
    for asset in spec.assets:
        file = path / asset.name
        if file.is_symlink() or not file.is_file():
            raise ValueError('Model installation is incomplete or linked: '+asset.name)
        info = file.stat()
        if info.st_size != asset.bytes:
            raise ValueError('Model file size does not match the pinned catalog: '+asset.name)
        signatures.append((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
    key = (str(path.resolve()), spec.id, spec.revision)
    with _VERIFY_LOCK:
        if _VERIFIED.get(key) == signatures:
            return path.resolve()
    for asset in spec.assets:
        digest = hashlib.sha256()
        with (path / asset.name).open('rb') as file:
            while block := file.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != asset.sha256:
            raise ValueError('Model failed SHA-256 integrity validation: '+asset.name)
    with _VERIFY_LOCK:
        _VERIFIED[key] = signatures
    return path.resolve()


def resolve_catalog_model(name, expected_backend, root=None):
    if not name.startswith('catalog:'):
        return None
    key = name.removeprefix('catalog:')
    spec = CATALOG.get(key)
    if spec is None or spec.backend != expected_backend:
        raise ValueError('Selected catalog model is incompatible with this speech backend.')
    return str(verify_model(Path(root or model_root()) / spec.id, spec))


class ModelManager:
    def __init__(self, root=None, catalog=None, backend=None, opener=urlopen):
        self.root = Path(root or model_root())
        self.catalog = CATALOG if catalog is None else catalog
        self.backend = backend or runtime_backend()
        self.opener = opener
        self._lock = threading.RLock()
        self._worker = None
        self._cancel = threading.Event()
        self._closed = False
        self._states = {}

    @property
    def busy(self):
        with self._lock:
            return bool(self._worker and self._worker.is_alive())

    def snapshot(self):
        with self._lock:
            result = []
            for spec in self.catalog.values():
                compatible = compatible_backend(spec, self.backend)
                installed = (self.root / spec.id).is_dir()
                result.append({**spec.public(), 'compatible': compatible, 'installed': installed,
                    'state': 'installed' if installed else 'absent', 'bytes_received':0,
                    'message': 'Files present; verified before use.' if installed else 'Explicit download required.',
                    **self._states.get(spec.id, {})})
            return result

    def _spec(self, key):
        spec = self.catalog.get(key)
        if spec is None or not compatible_backend(spec, self.backend):
            raise ValueError('This model is incompatible with the current computer/backend.')
        return spec

    def _publish(self, key, **values):
        with self._lock:
            self._states[key] = {**self._states.get(key, {}), **values}

    def install(self, key):
        """Synchronous explicit install. Use start_install from a UI host."""
        spec = self._spec(key)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = self.root / spec.id
        if destination.exists() or destination.is_symlink():
            verify_model(destination, spec)
            self._publish(key, state='installed', message='Verified model already installed.')
            return destination
        if shutil.disk_usage(self.root).free < spec.download_bytes + 64 * 1024 * 1024:
            raise OSError('Not enough free disk space for the model and safe staging.')
        stage = Path(tempfile.mkdtemp(prefix='.'+spec.id+'-', dir=self.root))
        total = 0
        try:
            self._publish(key, state='downloading', bytes_received=0, message='Downloading pinned model assets; no audio is sent.')
            for asset in spec.assets:
                self._check_cancel()
                request = Request(spec.url(asset.name), headers={'User-Agent':'FixoFlow-model-installer'})
                size, digest = 0, hashlib.sha256()
                with self.opener(request, timeout=30) as response, (stage/asset.name).open('xb') as output:
                    while block := response.read(1024*1024):
                        self._check_cancel()
                        size += len(block)
                        if size > asset.bytes:
                            raise ValueError('Downloaded model exceeds its pinned size.')
                        output.write(block)
                        digest.update(block)
                        total += len(block)
                        self._publish(key, bytes_received=total)
                    output.flush()
                    os.fsync(output.fileno())
                if size != asset.bytes or digest.hexdigest() != asset.sha256:
                    raise ValueError('Downloaded model does not match its pinned SHA-256/size.')
            self._publish(key, state='verifying', message='Verifying all installed assets.')
            verify_model(stage, spec)
            self._check_cancel()
            (stage/'installation.json').write_text(json.dumps(spec.public(), indent=2))
            # Rename does not replace a nonempty installation. Preserve any
            # installation that appeared while this download was running.
            if destination.exists() or destination.is_symlink():
                raise FileExistsError('An installation appeared during download; it was preserved.')
            stage.rename(destination)
            self._publish(key, state='installed', message='Verified model installed. Select it to warm up.')
            return destination
        except Exception as error:
            self._publish(key, state='cancelled' if isinstance(error, InterruptedError) else 'failed', message=str(error))
            raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def _check_cancel(self):
        if self._cancel.is_set():
            raise InterruptedError('Model operation cancelled; existing models were preserved.')

    def _start(self, key, operation, initial_state, message):
        with self._lock:
            if self._closed:
                raise RuntimeError('Model manager is closing.')
            if self._worker and self._worker.is_alive():
                raise RuntimeError('A model operation is already running.')
            self._cancel.clear()
            self._publish(key, state=initial_state, bytes_received=0, message=message)
            def run():
                try:
                    operation()
                except Exception as error:
                    self._publish(key, state='cancelled' if isinstance(error, InterruptedError) else 'failed', message=str(error))
            self._worker = threading.Thread(target=run, name='FixoFlow-model', daemon=True)
            self._worker.start()

    def start_install(self, key):
        self._spec(key)
        self._start(key, lambda: self.install(key), 'downloading', 'Preparing explicit model installation.')

    def warm_up(self, key, engine):
        """Warm the supplied idle-session engine; never select/download implicitly."""
        spec = self._spec(key)
        try:
            self._publish(key, state='verifying', message='Checking model before warm-up.')
            path = str(verify_model(self.root/spec.id, spec))
            self._check_cancel()
            if engine.resolve_model_path() != path:
                raise ValueError('Warm-up engine does not match the selected model.')
            self._publish(key, state='warming', message='Loading model locally. First use can take longer.')
            engine.warm_up()
            self._check_cancel()
            self._publish(key, state='ready', message='Model is loaded locally.')
        except Exception as error:
            self._publish(key, state='cancelled' if isinstance(error, InterruptedError) else 'failed', message=str(error))
            raise

    def start_warm_up(self, key, engine):
        self._spec(key)
        self._start(key, lambda: self.warm_up(key, engine), 'verifying', 'Preparing verified local warm-up.')

    def cancel(self):
        self._cancel.set()

    def close(self, timeout=2, *, terminal=True):
        with self._lock:
            self._closed = terminal
            self.cancel()
            worker = self._worker
        if worker:
            worker.join(timeout)
        return not worker or not worker.is_alive()

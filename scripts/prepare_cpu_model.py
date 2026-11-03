"""Stage a byte-verified pinned CPU model; downloads occur only in this build tool."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request

REPO = 'Systran/faster-whisper-base.en'
REVISION = '3d3d5dee26484f91867d81cb899cfcf72b96be6c'
# Non-LFS files use the repository's Git blob identity; the LFS weight uses SHA256.
FILES = {
    'config.json': (2227, 'git-sha1', '594369787efe617005d199b03739ee0ead7e3ab7'),
    'model.bin': (145216508, 'sha256', '2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef'),
    'tokenizer.json': (2128466, 'git-sha1', '15d7bdf9ba25718ca2504eec6a8f02bc55af0a6a'),
    'vocabulary.txt': (422309, 'git-sha1', 'ee695b8d3e3c10d488304e04468efec4ca27554a'),
    'README.md': (1323, 'git-sha1', '9ee8023dc11d4d835bd6bf2e0a88dc9a2b652e6b'),
}


def verify(path, expected):
    size, algorithm, digest = expected
    if path.stat().st_size != size:
        raise ValueError(f'Wrong size for {path.name}')
    checksum = hashlib.sha256() if algorithm == 'sha256' else hashlib.sha1(f'blob {size}\0'.encode())
    with path.open('rb') as source:
        while block := source.read(1024 * 1024):
            checksum.update(block)
    if checksum.hexdigest() != digest:
        raise ValueError(f'Pinned identity mismatch for {path.name}')


def stage(output, offline=False):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cpu-model-', dir=output.parent) as temporary:
        staged = Path(temporary)
        for name, expected in FILES.items():
            cached = output / name
            try:
                verify(cached, expected)
            except (OSError, ValueError):
                if offline:
                    raise RuntimeError(f'Missing verified offline model file: {name}') from None
                with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}', timeout=120) as response, (staged / name).open('wb') as destination:
                    count = 0
                    while block := response.read(1024 * 1024):
                        count += len(block)
                        if count > expected[0]:
                            raise ValueError(f'Oversized model response: {name}')
                        destination.write(block)
                verify(staged / name, expected)
            else:
                shutil.copy2(cached, staged / name)
        manifest = {'repository': REPO, 'revision': REVISION, 'license': 'MIT', 'verified': True,
                    'files': {name: hashlib.sha256((staged / name).read_bytes()).hexdigest() for name in FILES}}
        (staged / 'bundle-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        output.mkdir(parents=True, exist_ok=True)
        # Validation completes before any previously staged model is replaced.
        for file in staged.iterdir():
            file.replace(output / file.name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offline', action='store_true', help='Require an already verified model, never download')
    args = parser.parse_args()
    print(json.dumps(stage(args.output, args.offline), indent=2))


if __name__ == '__main__':
    main()

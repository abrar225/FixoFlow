"""Pinned English model candidates; quality/speed labels are hypotheses to measure.

Metadata fetched from the Hugging Face repository APIs on 2 November 2026.
All files have byte counts and SHA-256. Weights are immutable revision URLs.
Whisper model/code upstream license: MIT (https://github.com/openai/whisper).
Model conversion repositories and their README attribution travel with assets.
"""
from dataclasses import dataclass
import platform
import re
import sys


@dataclass(frozen=True)
class Asset:
    name: str
    bytes: int
    sha256: str

    def __post_init__(self):
        if self.name not in {'README.md','config.json','weights.npz','weights.safetensors','model.bin','tokenizer.json','vocabulary.txt'}:
            raise ValueError('Unexpected catalog asset name')
        if self.bytes <= 0 or len(self.sha256) != 64 or any(c not in '0123456789abcdef' for c in self.sha256):
            raise ValueError('Invalid pinned asset metadata')


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    backend: str
    repository: str
    revision: str
    assets: tuple[Asset, ...]
    purpose: str
    license: str = 'MIT'
    language: str = 'en'

    def __post_init__(self):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', self.id):
            raise ValueError('Invalid model identifier')
        if not re.fullmatch(r'[a-f0-9]{40}', self.revision):
            raise ValueError('Model revision must be immutable')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repository):
            raise ValueError('Invalid model repository')
        if self.backend not in {'mlx','cpu'} or not self.assets:
            raise ValueError('Unsupported model format or empty assets')

    @property
    def download_bytes(self):
        return sum(asset.bytes for asset in self.assets)

    def url(self, name):
        return f'https://huggingface.co/{self.repository}/resolve/{self.revision}/{name}'

    def public(self):
        return {'id':self.id,'name':self.name,'backend':self.backend,'model_name':'catalog:'+self.id,
            'repository':self.repository,'revision':self.revision,'download_bytes':self.download_bytes,
            'language':self.language,'license':self.license,'purpose':self.purpose,
            'qualification':'candidate; comparative quality not established',
            'assets':[{'name':a.name,'bytes':a.bytes,'sha256':a.sha256} for a in self.assets]}


def runtime_backend():
    return 'mlx' if sys.platform == 'darwin' and platform.machine().lower() in {'arm64','aarch64'} else 'cpu'


CATALOG = {
    'tiny-en-mlx': ModelSpec(
        id='tiny-en-mlx', name='Whisper Tiny English (MLX)', backend='mlx',
        repository='mlx-community/whisper-tiny.en-mlx', revision='5f4dafbb28e62a53c1b10426ff7eed36ca733bf7',
        purpose='Speed candidate; qualify latency and accuracy before recommending.', assets=(
            Asset('README.md', 305, '089f656c3ed18305617da1495182a0f9519ac61fdc1b8699d30ca67203a77f0c'),
            Asset('config.json', 262, '452e616242261333a661bc86db762b3720d6cc7e2eccd3d8e19a631871c26dd9'),
            Asset('weights.npz', 74417804, '4627203f0807d6496dda0d200e893b04ff24c98e73aa51c485c06203a0330b17'),
        )),
    'base-en-mlx': ModelSpec(
        id='base-en-mlx', name='Whisper Base English (MLX)', backend='mlx',
        repository='mlx-community/whisper-base.en-mlx', revision='aa0678c3466ed62c5c6114ec600a0e1f96820089',
        purpose='English baseline candidate.', assets=(
            Asset('README.md', 305, '9c5a2b42e9513ee1a44402a46cdf4239da13ba11a935d48a2c31a2743f107e8c'),
            Asset('config.json', 262, 'b0f55e86f8092c1188306dc346742253f759aecea0da7b00ae526e566fd53b14'),
            Asset('weights.npz', 143723132, 'b6c8ee500656e04e8e57c2949a5253f0dda002ba36cd1561846574dbcf01132e'),
        )),
    'small-en-mlx': ModelSpec(
        id='small-en-mlx', name='Whisper Small English (MLX)', backend='mlx',
        repository='mlx-community/whisper-small.en-mlx', revision='52a88bf6e98b114a210c21bb83e22d6e1505cb73',
        purpose='Quality candidate; qualify accuracy and resource cost before recommending.', assets=(
            Asset('README.md', 307, '0714a1ca0a7adb9033c602c5a2091f4c78ddfae5f8a5820b0a1626416296fd08'),
            Asset('config.json', 266, '40028e43687458e79ba89cc16bf14184c5414a5cbc00fd511f8f78d138647afd'),
            Asset('weights.npz', 481306200, '1bb29b030aca711a035f7a084a0eefac6251ecc2bdd356fa748858fbad082f5a'),
        )),
    'tiny-en-cpu': ModelSpec(
        id='tiny-en-cpu', name='Whisper Tiny English (CPU)', backend='cpu',
        repository='Systran/faster-whisper-tiny.en', revision='0d3d19a32d3338f10357c0889762bd8d64bbdeba',
        purpose='Speed candidate; qualify latency and accuracy before recommending.', assets=(
            Asset('README.md', 1323, '1b7816626bf0548e4b71a467f4112b4592924bc818e3117f19aefcc50ce4b6aa'),
            Asset('config.json', 2317, '14b1b421a90349bc551b881461426b561a874049cb9e4c4864f2ca384f6a7cc5'),
            Asset('model.bin', 75537502, '1a5afae06a4db91c975c9a9d78be5cc110ee4ea022ad57d55492e4550e936b2a'),
            Asset('tokenizer.json', 2128466, '929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df'),
            Asset('vocabulary.txt', 422309, 'ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf'),
        )),
    'base-en-cpu': ModelSpec(
        id='base-en-cpu', name='Whisper Base English (CPU)', backend='cpu',
        repository='Systran/faster-whisper-base.en', revision='3d3d5dee26484f91867d81cb899cfcf72b96be6c',
        purpose='English baseline candidate.', assets=(
            Asset('README.md', 1323, '0360e1518671daf4064d44121ad1c4bbb0446dd5b0f8c724c8d3132fd33a1540'),
            Asset('config.json', 2227, 'f3bc3821e9fc76a27bae538e11ae5b677dcdd352b4600429ce7951d398569aeb'),
            Asset('model.bin', 145216508, '2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef'),
            Asset('tokenizer.json', 2128466, '929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df'),
            Asset('vocabulary.txt', 422309, 'ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf'),
        )),
    'small-en-cpu': ModelSpec(
        id='small-en-cpu', name='Whisper Small English (CPU)', backend='cpu',
        repository='Systran/faster-whisper-small.en', revision='d1d751a5f8271d482d14ca55d9e2deeebbae577f',
        purpose='Quality candidate; qualify accuracy and resource cost before recommending.', assets=(
            Asset('README.md', 1330, 'c87ff776137c2ecb30ee3b324b4cf5f38abf9423464613641ee45430bf580851'),
            Asset('config.json', 2657, '666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae'),
            Asset('model.bin', 483545366, '62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a'),
            Asset('tokenizer.json', 2128466, '929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df'),
            Asset('vocabulary.txt', 422309, 'ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf'),
        )),
}

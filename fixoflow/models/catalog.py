"""Pinned Whisper and Parakeet choices; quality labels require separate evidence.

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
        if self.name not in {'README.md','config.json','weights.npz','weights.safetensors','model.bin','tokenizer.json','vocabulary.txt','vocabulary.json','preprocessor_config.json','nemo128.onnx','vocab.txt','encoder-model.int8.onnx','decoder_joint-model.int8.onnx'}:
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
    languages: tuple[str, ...] | None = None

    def __post_init__(self):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', self.id):
            raise ValueError('Invalid model identifier')
        if not re.fullmatch(r'[a-f0-9]{40}', self.revision):
            raise ValueError('Model revision must be immutable')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repository):
            raise ValueError('Invalid model repository')
        if self.backend not in {'mlx','cpu','onnx'} or not self.assets:
            raise ValueError('Unsupported model format or empty assets')

    @property
    def download_bytes(self):
        return sum(asset.bytes for asset in self.assets)

    def url(self, name):
        return f'https://huggingface.co/{self.repository}/resolve/{self.revision}/{name}'

    @property
    def supported_languages(self):
        if self.languages is not None:
            return self.languages
        if self.language == 'en':
            return ('en',)
        from fixoflow.languages import LANGUAGES
        return tuple(LANGUAGES)

    def public(self):
        upstream = ('https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3' if self.id=='parakeet-v3-onnx'
                    else 'https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2' if self.id=='parakeet-v2-onnx'
                    else 'https://github.com/openai/whisper')
        return {'id':self.id,'name':self.name,'backend':self.backend,'model_name':'catalog:'+self.id,
            'repository':self.repository,'revision':self.revision,'download_bytes':self.download_bytes,
            'language':self.language,'license':self.license,'purpose':self.purpose,
            'upstream':upstream,'attribution':('NVIDIA Parakeet; ONNX conversion by istupakov; CC BY 4.0.'
                if self.backend=='onnx' else 'OpenAI Whisper; conversion repository credited above; MIT.'),
            'languages':list(self.supported_languages),'auto_detect':self.language!='en',
            'forced_language':self.backend!='onnx',
            'qualification':'candidate; comparative quality not established',
            'assets':[{'name':a.name,'bytes':a.bytes,'sha256':a.sha256} for a in self.assets]}


def runtime_backend():
    return 'mlx' if sys.platform == 'darwin' and platform.machine().lower() in {'arm64','aarch64'} else 'cpu'


def compatible_backend(spec, backend=None):
    backend = backend or runtime_backend()
    if spec.backend == 'onnx':
        return not (sys.platform == 'darwin' and platform.machine().lower() not in {'arm64','aarch64'})
    return spec.backend == backend


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

# Multilingual Whisper and Parakeet assets pinned from upstream metadata.
CATALOG.update({
    'tiny-multi-mlx': ModelSpec(
        id='tiny-multi-mlx', name='Whisper Tiny Multilingual (MLX)', backend='mlx',
        repository='mlx-community/whisper-tiny-mlx', revision='6caf9c55601caafbe6508a8b0d216bdf4783c4e8',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 299, '64166743e9db4d6907c1655930648089e0f7c895d950b20409d13b7ccfe9f948'),
            Asset('config.json', 262, 'aaff20ce8f69beddee3fe0cc1e08f4e92f58586cb9f12ba00a6f73cbfec1cb1c'),
            Asset('weights.npz', 74418540, '0e03a5993d6eea43b07ee2dcc772b0e4cef5bb227257dacc24bf289387d49186'),
        )),
    'base-multi-mlx': ModelSpec(
        id='base-multi-mlx', name='Whisper Base Multilingual (MLX)', backend='mlx',
        repository='mlx-community/whisper-base-mlx', revision='1e3e249fb8d01c655324bd6841b1deadffd6d04c',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 341, 'cae7055dda5f053fe9f35b5356e9fe1b985ebcb077acc1d93199608588ec2197'),
            Asset('config.json', 262, '737220a6d958b3ad48e78f840fa991556266983c84ea2ca40e413389c62e4c2f'),
            Asset('weights.npz', 143724204, '2f57d5f3ef473054c638961f90716f4ee415e8108de81313eccb2c5fd62eff0b'),
        )),
    'small-multi-mlx': ModelSpec(
        id='small-multi-mlx', name='Whisper Small Multilingual (MLX)', backend='mlx',
        repository='mlx-community/whisper-small-mlx', revision='45f3915923c7a79a5a5b5a7d909d39aeb0e5630e',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 343, '47bab1dbd0bd831bd6f1b76e9d5a774041c585c63a1ec29a60cee60cbb56a084'),
            Asset('config.json', 266, 'e8f58e638208af66d5d5d67801259dc7a12d199e971967a9f9d33a8e3635668e'),
            Asset('weights.npz', 481307592, '55b6674c9b339702d486e2b1573839a66f8ec8f821ed2886993ef717a86b09f5'),
        )),
    'turbo-multi-mlx': ModelSpec(
        id='turbo-multi-mlx', name='Whisper Turbo Multilingual (MLX)', backend='mlx',
        repository='mlx-community/whisper-large-v3-turbo', revision='a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 359, '78f2d3dc65072211d957fc1b646c2d96e8e8f96dd45ceb2ac5f2643d0c5c05da'),
            Asset('config.json', 268, 'b34fc29e4e11e0a25e812775dd67f4dd16fc2c8eb43d28ae25ff7d660ecb6379'),
            Asset('weights.safetensors', 1613977612, '951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6'),
        )),
    'tiny-multi-cpu': ModelSpec(
        id='tiny-multi-cpu', name='Whisper Tiny Multilingual (CPU)', backend='cpu',
        repository='Systran/faster-whisper-tiny', revision='d90ca5fe260221311c53c58e660288d3deb8d356',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 1991, '29fb8444a02c1f133ab7e538525aa478ff68845964f21cf42500842b0e4a7b20'),
            Asset('config.json', 2249, 'a73a28cdfe1c43ccc7202fa333d1f89c202477271407ae9a7f19afa52039cac8'),
            Asset('model.bin', 75538270, 'dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1'),
            Asset('tokenizer.json', 2203239, 'fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab'),
            Asset('vocabulary.txt', 459861, '34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913'),
        )),
    'base-multi-cpu': ModelSpec(
        id='base-multi-cpu', name='Whisper Base Multilingual (CPU)', backend='cpu',
        repository='Systran/faster-whisper-base', revision='ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 1991, 'b922acef3616e27b1d416260b63ba7114c732f0315012006781af2da69cd1ebf'),
            Asset('config.json', 2309, '56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a'),
            Asset('model.bin', 145217532, 'd01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9'),
            Asset('tokenizer.json', 2203239, 'fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab'),
            Asset('vocabulary.txt', 459861, '34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913'),
        )),
    'small-multi-cpu': ModelSpec(
        id='small-multi-cpu', name='Whisper Small Multilingual (CPU)', backend='cpu',
        repository='Systran/faster-whisper-small', revision='536b0662742c02347bc0e980a01041f333bce120',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 1998, '329373481008c7c38654aff8ecdcf0163c211557cc7ba8e2ef6f2f84b4f75ec8'),
            Asset('config.json', 2370, 'b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828'),
            Asset('model.bin', 483546902, '3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671'),
            Asset('tokenizer.json', 2203239, 'fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab'),
            Asset('vocabulary.txt', 459861, '34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913'),
        )),
    'turbo-multi-cpu': ModelSpec(
        id='turbo-multi-cpu', name='Whisper Turbo Multilingual (CPU)', backend='cpu',
        repository='mobiuslabsgmbh/faster-whisper-large-v3-turbo', revision='0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf',
        language='multilingual', languages=None, license='MIT',
        purpose='Multilingual transcription; model support is not a measured language-accuracy guarantee.', assets=(
            Asset('README.md', 1445, 'b3068692728faed23580cce5cd569fc47ff76c690c032b2641ffd5554ea64d8f'),
            Asset('config.json', 2263, 'b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e'),
            Asset('model.bin', 1617884929, 'e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da'),
            Asset('preprocessor_config.json', 340, '7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711'),
            Asset('tokenizer.json', 2710337, '297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd'),
            Asset('vocabulary.json', 1068114, 'c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1'),
        )),
    'parakeet-v3-onnx': ModelSpec(
        id='parakeet-v3-onnx', name='Parakeet TDT v3 (ONNX int8)', backend='onnx',
        repository='istupakov/parakeet-tdt-0.6b-v3-onnx', revision='8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce',
        language='multilingual', languages=('bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'et', 'fi', 'fr', 'hr', 'hu', 'it', 'lt', 'lv', 'mt', 'nl', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sv', 'uk'), license='CC-BY-4.0',
        purpose='Local automatic language detection within the model language set; no forced-language or vocabulary-prompt support.', assets=(
            Asset('README.md', 1207, '95d330fef1070f22cc4d4e380fbf5913253b44f7b71fabae997f6cdf65fe1714'),
            Asset('config.json', 97, '666903c76b9798caf2c210afd4f6cd60b08a8dbf9800ec8d7a3bc0d2148ac466'),
            Asset('decoder_joint-model.int8.onnx', 18202004, 'eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70'),
            Asset('encoder-model.int8.onnx', 652183999, '6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09'),
            Asset('nemo128.onnx', 139764, 'a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f'),
            Asset('vocab.txt', 93939, 'd58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d'),
        )),
    'parakeet-v2-onnx': ModelSpec(
        id='parakeet-v2-onnx', name='Parakeet TDT v2 (ONNX int8)', backend='onnx',
        repository='istupakov/parakeet-tdt-0.6b-v2-onnx', revision='0bbb45a3365852604aef28b538a8f066f4ccaa85',
        language='en', languages=('en',), license='CC-BY-4.0',
        purpose='Local automatic language detection within the model language set; no forced-language or vocabulary-prompt support.', assets=(
            Asset('README.md', 1027, 'f46710815c425ebadbdbafe7c0337a09070b589f2b1d698568022b4f3f3ce12d'),
            Asset('config.json', 97, '666903c76b9798caf2c210afd4f6cd60b08a8dbf9800ec8d7a3bc0d2148ac466'),
            Asset('decoder_joint-model.int8.onnx', 8998286, 'a449f49acd68979d418651dd2dcb737cc0f1bf0225e009e29ee326354edbf7d3'),
            Asset('encoder-model.int8.onnx', 652184014, '3e0581fda6ab843888b51e56d7ee78b6d5bc3237ec113af1f732d1d5286aa155'),
            Asset('nemo128.onnx', 139764, 'a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f'),
            Asset('vocab.txt', 9384, 'ec182b70dd42113aff6c5372c75cac58c952443eb22322f57bbd7f53977d497d'),
        )),
})

"""Whisper Base language catalog and explicit script/locale preferences.

Base supports 99 language tokens. Listing a language is not a measured accuracy
claim; Cantonese's additional large-v3 token is intentionally excluded.
Catalog: https://github.com/openai/whisper/blob/main/whisper/tokenizer.py
"""
LANGUAGES = {'en': 'english', 'zh': 'chinese', 'de': 'german', 'es': 'spanish', 'ru': 'russian', 'ko': 'korean', 'fr': 'french', 'ja': 'japanese', 'pt': 'portuguese', 'tr': 'turkish', 'pl': 'polish', 'ca': 'catalan', 'nl': 'dutch', 'ar': 'arabic', 'sv': 'swedish', 'it': 'italian', 'id': 'indonesian', 'hi': 'hindi', 'fi': 'finnish', 'vi': 'vietnamese', 'he': 'hebrew', 'uk': 'ukrainian', 'el': 'greek', 'ms': 'malay', 'cs': 'czech', 'ro': 'romanian', 'da': 'danish', 'hu': 'hungarian', 'ta': 'tamil', 'no': 'norwegian', 'th': 'thai', 'ur': 'urdu', 'hr': 'croatian', 'bg': 'bulgarian', 'lt': 'lithuanian', 'la': 'latin', 'mi': 'maori', 'ml': 'malayalam', 'cy': 'welsh', 'sk': 'slovak', 'te': 'telugu', 'fa': 'persian', 'lv': 'latvian', 'bn': 'bengali', 'sr': 'serbian', 'az': 'azerbaijani', 'sl': 'slovenian', 'kn': 'kannada', 'et': 'estonian', 'mk': 'macedonian',
             'br': 'breton', 'eu': 'basque', 'is': 'icelandic', 'hy': 'armenian', 'ne': 'nepali', 'mn': 'mongolian', 'bs': 'bosnian', 'kk': 'kazakh', 'sq': 'albanian', 'sw': 'swahili', 'gl': 'galician', 'mr': 'marathi', 'pa': 'punjabi', 'si': 'sinhala', 'km': 'khmer', 'sn': 'shona', 'yo': 'yoruba', 'so': 'somali', 'af': 'afrikaans', 'oc': 'occitan', 'ka': 'georgian', 'be': 'belarusian', 'tg': 'tajik', 'sd': 'sindhi', 'gu': 'gujarati', 'am': 'amharic', 'yi': 'yiddish', 'lo': 'lao', 'uz': 'uzbek', 'fo': 'faroese', 'ht': 'haitian creole', 'ps': 'pashto', 'tk': 'turkmen', 'nn': 'nynorsk', 'mt': 'maltese', 'sa': 'sanskrit', 'lb': 'luxembourgish', 'my': 'myanmar', 'bo': 'tibetan', 'tl': 'tagalog', 'mg': 'malagasy', 'as': 'assamese', 'tt': 'tatar', 'haw': 'hawaiian', 'ln': 'lingala', 'ha': 'hausa', 'ba': 'bashkir', 'jw': 'javanese', 'su': 'sundanese'}
ENGLISH_VARIANTS = {"en-US": "English (United States)", "en-GB": "English (United Kingdom)", "en-IN": "English (India)"}
MULTILINGUAL_MESSAGE = 'Choose a compatible multilingual model for more languages. Model language support does not guarantee accuracy; mixed-language and Roman Hinglish output remain evaluation cases.'


def require_released_language(language, model_name):
    """Compatibility wrapper retained for existing config callers."""
    validate_language_selection(language, model_name)


def available_languages(model_name, backend=None):
    """Selectable languages, where None means automatic detection.

    Parakeet v3 automatically detects its25 supported languages; it has no forced
    language parameter, so the selectable control intentionally offers only Auto.
    """
    from fixoflow.models.catalog import CATALOG, compatible_backend
    if model_name.startswith('catalog:'):
        spec = CATALOG.get(model_name.removeprefix('catalog:'))
        if spec is None or not compatible_backend(spec, backend):
            return ()
        if spec.backend == 'onnx' and spec.language != 'en':
            return (None,)
        return ((None,) if spec.language != 'en' else ()) + spec.supported_languages
    if model_name == 'multilingual-base':
        return (None, *LANGUAGES)
    # Known English variants never become multilingual merely because they
    # contain a decoder API that accepts a language argument.
    if model_name in {'bundled-base.en','mlx-community/whisper-base.en-mlx','mlx-community/whisper-small.en-mlx'} or '.en' in model_name:
        return ('en',)
    # Explicit local folders can advertise a supported multilingual config.
    from pathlib import Path
    import json
    path = Path(model_name).expanduser()
    if path.is_dir():
        try:
            config = json.loads((path/'config.json').read_text())
            n_vocab = config.get('n_vocab')
            lang_ids = config.get('lang_ids')
            multilingual = ((type(n_vocab) is int and n_vocab >= 51865) or
                isinstance(lang_ids,list) and len(lang_ids)>=99 and len(set(lang_ids))==len(lang_ids)
                and all(type(x) is int and x>0 for x in lang_ids))
            return (None, *LANGUAGES) if multilingual else ('en',)
        except (ValueError,OSError,TypeError,AttributeError):
            return ('en',)
    # Unknown repository strings are not promoted to broad language support.
    return ('en',)


def validate_language_selection(language, model_name, backend=None):
    if language is not None and language not in LANGUAGES:
        raise ValueError('Choose a supported recognition language.')
    allowed = available_languages(model_name, backend)
    if not allowed:
        raise ValueError('Selected model is not compatible with this computer/backend.')
    if language not in allowed:
        if allowed == (None,):
            raise ValueError('This Parakeet model automatically detects its supported languages. Choose Automatic detection.')
        raise ValueError('Selected language is not supported by this model. Choose a compatible multilingual model.')


def language_prompt(language, english_variant="en-US"):
    if language == 'zh':
        return '以下是普通话的简体中文转录。保留原文，不翻译。'
    if language == 'hi':
        return 'यह हिंदी में देवनागरी लिपि का प्रतिलेखन है। English names stay in English.'
    if language == 'ja':
        return '日本語の文字起こしです。翻訳せず、元の言語で記録します。'
    if language == 'en':
        # Whisper conditions on transcript-like text; locale instructions can
        # be echoed as invented speech. All English varieties share a model.
        return ''
    return ''  # No English prose injected into other languages/auto detection.


def options(model_name='bundled-base.en', backend=None):
    return [{'value':'auto' if code is None else code,
             'label':'Automatic detection' if code is None else LANGUAGES[code].capitalize()}
            for code in available_languages(model_name, backend)]

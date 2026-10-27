"""Whisper Base language catalog and explicit script/locale preferences.

Base supports 99 language tokens. Listing a language is not a measured accuracy
claim; Cantonese's additional large-v3 token is intentionally excluded.
Catalog: https://github.com/openai/whisper/blob/main/whisper/tokenizer.py
"""
LANGUAGES = {'en': 'english', 'zh': 'chinese', 'de': 'german', 'es': 'spanish', 'ru': 'russian', 'ko': 'korean', 'fr': 'french', 'ja': 'japanese', 'pt': 'portuguese', 'tr': 'turkish', 'pl': 'polish', 'ca': 'catalan', 'nl': 'dutch', 'ar': 'arabic', 'sv': 'swedish', 'it': 'italian', 'id': 'indonesian', 'hi': 'hindi', 'fi': 'finnish', 'vi': 'vietnamese', 'he': 'hebrew', 'uk': 'ukrainian', 'el': 'greek', 'ms': 'malay', 'cs': 'czech', 'ro': 'romanian', 'da': 'danish', 'hu': 'hungarian', 'ta': 'tamil', 'no': 'norwegian', 'th': 'thai', 'ur': 'urdu', 'hr': 'croatian', 'bg': 'bulgarian', 'lt': 'lithuanian', 'la': 'latin', 'mi': 'maori', 'ml': 'malayalam', 'cy': 'welsh', 'sk': 'slovak', 'te': 'telugu', 'fa': 'persian', 'lv': 'latvian', 'bn': 'bengali', 'sr': 'serbian', 'az': 'azerbaijani', 'sl': 'slovenian', 'kn': 'kannada', 'et': 'estonian', 'mk': 'macedonian',
             'br': 'breton', 'eu': 'basque', 'is': 'icelandic', 'hy': 'armenian', 'ne': 'nepali', 'mn': 'mongolian', 'bs': 'bosnian', 'kk': 'kazakh', 'sq': 'albanian', 'sw': 'swahili', 'gl': 'galician', 'mr': 'marathi', 'pa': 'punjabi', 'si': 'sinhala', 'km': 'khmer', 'sn': 'shona', 'yo': 'yoruba', 'so': 'somali', 'af': 'afrikaans', 'oc': 'occitan', 'ka': 'georgian', 'be': 'belarusian', 'tg': 'tajik', 'sd': 'sindhi', 'gu': 'gujarati', 'am': 'amharic', 'yi': 'yiddish', 'lo': 'lao', 'uz': 'uzbek', 'fo': 'faroese', 'ht': 'haitian creole', 'ps': 'pashto', 'tk': 'turkmen', 'nn': 'nynorsk', 'mt': 'maltese', 'sa': 'sanskrit', 'lb': 'luxembourgish', 'my': 'myanmar', 'bo': 'tibetan', 'tl': 'tagalog', 'mg': 'malagasy', 'as': 'assamese', 'tt': 'tatar', 'haw': 'hawaiian', 'ln': 'lingala', 'ha': 'hausa', 'ba': 'bashkir', 'jw': 'javanese', 'su': 'sundanese'}
ENGLISH_VARIANTS = {"en-US": "English (United States)", "en-GB": "English (United Kingdom)", "en-IN": "English (India)"}
MULTILINGUAL_MESSAGE = 'Multilingual dictation is coming soon. This release supports English only; other languages and Hinglish are in accuracy research.'


def require_released_language(language, model_name):
    if language != 'en' or model_name == 'multilingual-base':
        raise ValueError(MULTILINGUAL_MESSAGE)


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


def options():
    # LANGUAGES remains an evaluation catalog, not a public availability claim.
    return [{'value': 'en', 'label': 'English'}]

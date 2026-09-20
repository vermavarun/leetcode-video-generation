"""Make machine-translated Hindi sound like how Indian developers actually speak.

Argos produces stiff, Sanskritised Hindi and mangles code identifiers
("k" -> "कश्मीर", "i" -> "मैं"). Two passes fix that:

  1. identifiers are masked before translation and restored afterwards
  2. formal vocabulary is swapped for the everyday Hinglish equivalent
"""

from __future__ import annotations

import re

# Placeholder shape verified to survive the en->hi model untouched.
MASK_PREFIX = "ZQ"
_MASK_RE = re.compile(rf"{MASK_PREFIX}\s?(\d+)")

# Single letters and short names that LeetCode statements use as variables.
VARIABLE_NAMES = {
    "n", "k", "m", "i", "j", "d", "t", "x", "y", "r", "c", "q", "p", "w",
    "nums", "num", "arr", "dist", "idx", "ans", "val", "len", "cnt", "dp",
    "subarray", "subarrays", "subarray's", "str", "ch", "res", "tmp", "mod",
}

# Code-shaped tokens: nums[0], s.length, minCost, my_var.
_CODE_TOKEN = re.compile(
    r"(?<![\w])(?:[A-Za-z_]\w*\[[^\]]{0,20}\]|[A-Za-z_]\w*\.\w+|[a-z]+[A-Z]\w*|[A-Za-z]+_\w+)(?![\w])"
)

# How to say an identifier out loud in Hindi. Unlisted names stay in Latin.
SPOKEN = {
    "n": "एन", "k": "के", "m": "एम", "i": "आई", "j": "जे", "d": "डी", "t": "टी",
    "x": "एक्स", "y": "वाई", "r": "आर", "c": "सी", "q": "क्यू", "p": "पी", "w": "डब्ल्यू",
    "s": "एस", "nums": "नम्स", "num": "नम", "arr": "ऐर", "dist": "डिस्ट",
    "idx": "इंडेक्स", "ans": "आंसर", "val": "वैल्यू", "cnt": "काउंट", "dp": "डीपी",
    "subarray": "सबऐरे", "subarrays": "सबऐरेज़", "str": "स्ट्रिंग", "res": "रिज़ल्ट",
    "mod": "मॉड", "ch": "कैरेक्टर",
}

# Operator wording the model reliably mangles. Masked before translation so it
# is never touched. Kept small: every mask costs sentence quality.
FORCED_PRE = {
    "less than or equal to": "से छोटा या बराबर",
    "greater than or equal to": "से बड़ा या बराबर",
    "not equal to": "के बराबर नहीं",
    "less than": "से छोटा",
    "greater than": "से बड़ा",
    "to the power": "की पावर",
    "time complexity": "टाइम कॉम्प्लेक्सिटी",
    "space complexity": "स्पेस कॉम्प्लेक्सिटी",
}

# English the model leaves behind. Swept up after translation, where it costs
# nothing in fluency.
FORCED_POST = {
    "sliding window": "स्लाइडिंग विंडो",
    "sorted sets": "सॉर्टेड सेट्स",
    "sorted set": "सॉर्टेड सेट",
    "binary search": "बाइनरी सर्च",
    "hash map": "हैश मैप",
    "linked list": "लिंक्ड लिस्ट",
    "prefix sum": "प्रीफिक्स सम",
    "two pointers": "टू पॉइंटर्स",
    "subarrays": "सबऐरेज़", "subarray": "सबऐरे",
    "substring": "सबस्ट्रिंग",
    "arrays": "ऐरेज़", "array": "ऐरे",
    "strings": "स्ट्रिंग्स", "string": "स्ट्रिंग",
    "elements": "एलिमेंट्स", "element": "एलिमेंट",
    "integers": "इंटीजर्स", "integer": "इंटीजर",
    "indices": "इंडेक्सेज़", "index": "इंडेक्स",
    "values": "वैल्यूज़", "value": "वैल्यू",
    "constraints": "कंस्ट्रेंट्स", "constraint": "कंस्ट्रेंट",
    "sorted": "सॉर्टेड", "window": "विंडो", "loop": "लूप",
    "pointer": "पॉइंटर", "node": "नोड", "stack": "स्टैक", "queue": "क्यू",
    "input": "इनपुट", "output": "आउटपुट",
    "sum": "सम", "cost": "कॉस्ट", "size": "साइज़", "length": "लंबाई",
    "count": "काउंट", "total": "टोटल", "first": "पहला", "last": "आखिरी",
    "fixed": "फिक्स", "sliding": "स्लाइडिंग",
    "largest": "सबसे बड़ा", "smallest": "सबसे छोटा",
    "remaining": "बाकी", "expired": "एक्सपायर्ड", "promote": "प्रमोट",
    "with": "के साथ", "into": "में", "its": "इसका", "set": "सेट", "sets": "सेट्स",
}


def _phrase_pattern(phrases) -> re.Pattern[str]:
    joined = "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{joined})(?!\w)", re.IGNORECASE)


_FORCED_PRE_RE = _phrase_pattern(FORCED_PRE)
_FORCED_POST_RE = _phrase_pattern(FORCED_POST)

# Formal / Sanskritised Hindi -> the word a developer would actually say.
_CASUAL_TERMS = [
    # Multi-word first so they win over the single-word rules below.
    ("समय जटिलता", "टाइम कॉम्प्लेक्सिटी"),
    ("अंतरिक्ष जटिलता", "स्पेस कॉम्प्लेक्सिटी"),
    ("स्थान जटिलता", "स्पेस कॉम्प्लेक्सिटी"),
    ("कम से कम या बराबर", "से छोटा या बराबर"),
    ("से अधिक या बराबर", "से बड़ा या बराबर"),
    # Data structures and core nouns.
    ("सरणियों", "ऐरेज़"), ("सरणियाँ", "ऐरेज़"), ("सरणी", "ऐरे"), ("व्यूह", "ऐरे"),
    ("शृंखला", "स्ट्रिंग"), ("श्रृंखला", "स्ट्रिंग"), ("माला", "स्ट्रिंग"),
    ("अनुक्रमणिका", "इंडेक्स"), ("सूचकांक", "इंडेक्स"),
    ("तत्वों", "एलिमेंट्स"), ("तत्व", "एलिमेंट"), ("अवयव", "एलिमेंट"),
    ("पूर्णांकों", "इंटीजर्स"), ("पूर्णांक", "इंटीजर"),
    ("वर्णों", "कैरेक्टर्स"), ("वर्ण", "कैरेक्टर"), ("अक्षरों", "कैरेक्टर्स"),
    ("सूची", "लिस्ट"), ("ढेर", "स्टैक"), ("कतार", "क्यू"), ("वृक्ष", "ट्री"),
    ("आलेख", "ग्राफ"), ("गाँठ", "नोड"), ("शीर्ष", "नोड"),
    ("कुंजी", "की"), ("मूल्यों", "वैल्यूज़"), ("मूल्य", "वैल्यू"),
    ("फलन", "फंक्शन"), ("प्रकार्य", "फंक्शन"),
    ("चर", "वेरिएबल"), ("पाश", "लूप"), ("खिड़की", "विंडो"),
    # Algorithm vocabulary.
    ("दृष्टिकोण", "अप्रोच"), ("उपागम", "अप्रोच"),
    ("छंटनी की गई", "सॉर्टेड"), ("छंटनी", "सॉर्टेड"),
    ("क्रमबद्ध किया गया", "सॉर्ट किया गया"), ("क्रमबद्ध", "सॉर्टेड"),
    ("जटिलता", "कॉम्प्लेक्सिटी"),
    ("बाधाओं", "कंस्ट्रेंट्स"), ("बाधाएं", "कंस्ट्रेंट्स"), ("बाधाएँ", "कंस्ट्रेंट्स"),
    ("बाधा", "कंस्ट्रेंट"), ("अनुसूचित", "इंडेक्स्ड"),
    ("प्रतिबंध", "कंस्ट्रेंट्स"),
    ("समाधान", "सलूशन"), ("समस्याओं", "प्रॉब्लम्स"), ("समस्या", "प्रॉब्लम"),
    ("न्यूनतम", "मिनिमम"), ("अधिकतम", "मैक्सिमम"),
    ("पुनरावृत्ति", "इटरेशन"), ("खोज", "सर्च"),
    ("राशि", "सम"), ("लागत", "कॉस्ट"), ("आकार", "साइज़"),
    ("स्थिति", "पोज़िशन"), ("उपसर्ग", "प्रीफिक्स"), ("गुणांक", "कोएफिशिएंट"),
    ("निवेश", "इनपुट"), ("निर्गम", "आउटपुट"), ("उत्पादन", "आउटपुट"),
    ("वर्णमाला", "अल्फाबेट"), ("संचालन", "ऑपरेशन"),
]

# Bookish connectives -> spoken ones.
_CASUAL_TONE = [
    ("यदि", "अगर"), ("किन्तु", "लेकिन"), ("परन्तु", "लेकिन"), ("परंतु", "लेकिन"),
    ("तथा", "और"), ("एवं", "और"), ("अतः", "तो"), ("अतएव", "तो"),
    ("प्रत्येक", "हर"), ("इस प्रकार", "ऐसे"), ("उपरोक्त", "ऊपर वाला"),
    ("निम्नलिखित", "नीचे दिया"), ("सर्वप्रथम", "सबसे पहले"),
    ("का उपयोग करेंगे", "यूज़ करेंगे"), ("का उपयोग करें", "यूज़ करें"),
    ("का उपयोग", "का यूज़"), ("उपयोग किया जाता है", "यूज़ होता है"),
    ("की आवश्यकता है", "की ज़रूरत है"), ("आवश्यक है", "ज़रूरी है"),
    ("प्राप्त करें", "निकाल लें"), ("सकारात्मक", "पॉज़िटिव"), ("नकारात्मक", "नेगेटिव"),
]

_CASUAL_RULES = [
    (re.compile(re.escape(src)), dst) for src, dst in _CASUAL_TERMS + _CASUAL_TONE
]


class Masker:
    """Hide identifiers from the translator, then speak them back in Devanagari."""

    def __init__(self, extra_terms: set[str] | None = None):
        names = VARIABLE_NAMES | {t for t in (extra_terms or set()) if len(t) >= 3}
        alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        # The non-capturing group matters: without it the word boundaries would
        # only apply to the first and last alternative.
        self._names = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)")

    def mask(self, text: str) -> tuple[str, dict[str, tuple[str, bool]]]:
        mapping: dict[str, tuple[str, bool]] = {}
        seen: dict[str, str] = {}

        def take(final: bool):
            def replace(match: re.Match[str]) -> str:
                original = match.group(0)
                value = FORCED_PRE[original.lower()] if final else original
                # Reuse one placeholder per distinct token; too many confuses the model.
                if original not in seen:
                    key = f"{MASK_PREFIX}{len(mapping)}"
                    mapping[key] = (value, final)
                    seen[original] = key
                return seen[original]

            return replace

        masked = _FORCED_PRE_RE.sub(take(True), text)
        masked = _CODE_TOKEN.sub(take(False), masked)
        masked = self._names.sub(take(False), masked)
        return masked, mapping

    @staticmethod
    def unmask(text: str, mapping: dict[str, tuple[str, bool]], *, speech: bool) -> str:
        def restore(match: re.Match[str]) -> str:
            value, final = mapping.get(f"{MASK_PREFIX}{match.group(1)}", ("", True))
            if final:
                return value
            return SPOKEN.get(value.lower(), value) if speech else value

        return _MASK_RE.sub(restore, text)


def casualize(text: str) -> str:
    text = _FORCED_POST_RE.sub(lambda m: FORCED_POST[m.group(0).lower()], text)
    for pattern, replacement in _CASUAL_RULES:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()

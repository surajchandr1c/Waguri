"""
Text Normalization Pipeline for the Abuse Detection & Auto-Moderation System.

Implements multi-stage normalization:
1. Unicode NFKC normalization
2. Zero-width character removal
3. Combining mark handling (Zalgo text)
4. Unicode homoglyph mapping (Cyrillic, Greek, fullwidth, etc.)
5. Lowercase conversion
6. Repeated character reduction (fuuuuuck -> fuck, shiiiiit -> shit)
7. Leetspeak substitution (f@ck -> fack, b1tch -> bitch, etc.)
8. Intra-word special character collapse (f.u.c.k -> fuck, f*u*c*k -> fuck)
9. Spaced-out letter sequence collapse (f u c k -> fuck, m a d a r c h o d -> madarchod)
10. Devanagari phonetic transliteration
11. Word boundary & token preservation (prevents false positives)
"""

import re
import unicodedata
from typing import List, Set, Tuple
from moderation.abuse.dictionaries import DEVANAGARI_TRANSLITERATION_MAP

# Zero-width, directional, and invisible formatting characters
ZERO_WIDTH_PATTERN = re.compile(
    r"[\u200B-\u200F"  # Zero-width space, non-joiner, joiner, LTR/RTL marks
    r"\u2028-\u202F"  # Line/paragraph separators, directional overrides
    r"\u2060-\u206F"  # Word joiner, invisible operators
    r"\uFEFF"          # Byte order mark
    r"\u00AD"          # Soft hyphen
    r"\u034F"          # Combining grapheme joiner
    r"\u180E"          # Mongolian vowel separator
    r"]+"
)

# Combining diacritical marks (Zalgo text)
COMBINING_MARKS_PATTERN = re.compile(
    r"[\u0300-\u036F\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]+"
)

# Common Unicode homoglyphs (Cyrillic, Greek, Math) to Latin equivalents
HOMOGLYPH_MAP = {
    # Cyrillic lookalikes
    "а": "a", "А": "A",
    "в": "b", "В": "B",
    "с": "c", "С": "C",
    "е": "e", "Е": "E",
    "к": "k", "К": "K",
    "м": "m", "М": "M",
    "н": "h", "Н": "H",
    "о": "o", "О": "O",
    "р": "p", "Р": "P",
    "т": "t", "Т": "T",
    "у": "y", "У": "Y",
    "х": "x", "Х": "X",
    "і": "i", "І": "I",
    "ј": "j", "Ј": "J",
    "ѕ": "s", "Ѕ": "S",
    "ѵ": "v", "Ѵ": "V",
    "ԁ": "d", "Ԃ": "D",
    "ԛ": "q", "Ԛ": "Q",
    # Greek lookalikes
    "α": "a", "Α": "A",
    "β": "b", "Β": "B",
    "ε": "e", "Ε": "E",
    "ι": "i", "Ι": "I",
    "κ": "k", "Κ": "K",
    "ο": "o", "Ο": "O",
    "ρ": "p", "Ρ": "P",
    "τ": "t", "Τ": "T",
    "υ": "u", "Υ": "Y",
    "χ": "x", "Χ": "X",
}

# Leetspeak substitution table
LEET_TABLE = {
    "@": "a",
    "4": "a",
    "3": "e",
    "1": "i",
    "!": "i",
    "|": "i",
    "0": "o",
    "5": "s",
    "$": "s",
    "7": "t",
    "+": "t",
    "8": "b",
}

# Regex to detect sequences of repeated identical characters (3 or more)
REPEATED_CHARS_PATTERN = re.compile(r"(.)\1{2,}", re.IGNORECASE)

# Regex to detect spaced-out letters (e.g. "f u c k", "m a d a r c h o d")
SPACED_LETTERS_PATTERN = re.compile(r"\b([a-zA-Z])(?:\s+([a-zA-Z])){2,}\b")

# Regex to detect intra-word punctuation/special character insertion (e.g. "f.u.c.k", "f*u*c*k", "f-u-c-k")
INTRA_WORD_SEPARATORS_PATTERN = re.compile(
    r"\b([a-zA-Z0-9@!$#*_.\-~]{1,2}(?:[\W_]+[a-zA-Z0-9@!$#*_.\-~]{1,2})+)\b"
)


class TextNormalizer:
    """Comprehensive multi-representation text normalization pipeline."""

    @staticmethod
    def remove_invisible_chars(text: str) -> str:
        """Strip zero-width, combining marks, and invisible formatting characters."""
        if not text:
            return ""
        # 1. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", text)
        # 2. Strip zero-width & directional characters
        normalized = ZERO_WIDTH_PATTERN.sub("", normalized)
        # 3. Strip combining diacritical marks (Zalgo)
        normalized = COMBINING_MARKS_PATTERN.sub("", normalized)
        return normalized

    @staticmethod
    def replace_homoglyphs(text: str) -> str:
        """Map visual homoglyphs (Cyrillic, Greek) to standard Latin characters."""
        if not text:
            return ""
        chars = [HOMOGLYPH_MAP.get(c, c) for c in text]
        return "".join(chars)

    @staticmethod
    def reduce_repeated_chars(text: str) -> str:
        """
        Reduce 3 or more repeated identical characters down to 1.
        e.g., 'fuuuuuck' -> 'fuck', 'shiiiiit' -> 'shit', 'bhossssdike' -> 'bhosdike'.
        """
        if not text:
            return ""
        return REPEATED_CHARS_PATTERN.sub(r"\1", text)

    @staticmethod
    def apply_leetspeak(text: str) -> str:
        """
        Convert common number and symbol substitutions into standard letters.
        e.g., 'f@ck' -> 'fack', 'b1tch' -> 'bitch', 'sh1t' -> 'shit'.
        """
        if not text:
            return ""
        chars = [LEET_TABLE.get(c, c) for c in text]
        return "".join(chars)

    @staticmethod
    def collapse_intra_word_separators(text: str) -> str:
        """
        Identify tokens with special characters inserted between letters (f.u.c.k, f*u*c*k)
        and collapse them while preserving surrounding whitespace.
        """
        if not text:
            return ""

        def replacer(match):
            raw = match.group(0)
            # Only collapse if characters are interspersed with punctuation
            collapsed = re.sub(r"[\W_]+", "", raw)
            return collapsed if len(collapsed) > 1 else raw

        return INTRA_WORD_SEPARATORS_PATTERN.sub(replacer, text)

    @staticmethod
    def collapse_spaced_letters(text: str) -> str:
        """
        Detect spaced-out single-letter sequences (e.g. 'f u c k', 'm a d a r c h o d')
        and collapse them into single words.
        """
        if not text:
            return ""

        def replacer(match):
            raw = match.group(0)
            # Collapse whitespace between isolated single letters
            collapsed = re.sub(r"\s+", "", raw)
            return collapsed

        return SPACED_LETTERS_PATTERN.sub(replacer, text)

    @staticmethod
    def transliterate_devanagari(text: str) -> str:
        """
        Transliterate known Devanagari abusive words or characters into Roman Hindi.
        """
        if not text:
            return ""
        res = text
        for dev, rom in DEVANAGARI_TRANSLITERATION_MAP.items():
            if dev in res:
                res = res.replace(dev, rom)
        return res

    @classmethod
    def normalize_pipeline(cls, text: str) -> dict:
        """
        Execute the full normalization pipeline, returning multiple normalized representations:
        - raw: Original unedited text
        - clean_nfkc: Invisible characters and homoglyphs cleaned, lowercased
        - reduced: Repeated characters reduced
        - leet_normalized: Leetspeak converted
        - collapsed_punct: Intra-word punctuation collapsed (f.u.c.k -> fuck)
        - collapsed_spaces: Spaced-out letters collapsed (f u c k -> fuck)
        - transliterated: Devanagari transliterated to Roman Hindi
        - tokens: Tokenized words across normalized representations
        """
        if not text:
            return {
                "raw": "",
                "clean_nfkc": "",
                "reduced": "",
                "leet_normalized": "",
                "collapsed_punct": "",
                "collapsed_spaces": "",
                "transliterated": "",
                "tokens": [],
            }

        # Step 1: NFKC & invisible characters removal
        clean_nfkc = cls.remove_invisible_chars(text)
        # Step 2: Homoglyph conversion & lowercase
        clean_nfkc = cls.replace_homoglyphs(clean_nfkc).lower()

        # Step 3: Devanagari transliteration
        transliterated = cls.transliterate_devanagari(clean_nfkc)

        # Step 4: Intra-word punctuation collapse (f.u.c.k -> fuck, f*u*c*k -> fuck)
        collapsed_punct = cls.collapse_intra_word_separators(transliterated)

        # Step 5: Spaced-out letters collapse (f u c k -> fuck)
        collapsed_spaces = cls.collapse_spaced_letters(collapsed_punct)

        # Step 6: Leetspeak conversion (@ -> a, 1 -> i, 3 -> e, 0 -> o)
        leet_normalized = cls.apply_leetspeak(collapsed_spaces)

        # Step 7: Repeated character reduction (fuuuuck -> fuck)
        reduced = cls.reduce_repeated_chars(leet_normalized)

        # Extract normalized tokens (words) preserving boundaries
        token_set: Set[str] = set()

        for stream in (clean_nfkc, transliterated, collapsed_punct, collapsed_spaces, leet_normalized, reduced):
            # Extract word tokens with regex
            words = re.findall(r"[\w]+", stream, re.UNICODE)
            for w in words:
                token_set.add(w)

        return {
            "raw": text,
            "clean_nfkc": clean_nfkc,
            "transliterated": transliterated,
            "collapsed_punct": collapsed_punct,
            "collapsed_spaces": collapsed_spaces,
            "leet_normalized": leet_normalized,
            "reduced": reduced,
            "tokens": list(token_set),
        }

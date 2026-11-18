"""
Advanced Abuse Detection Engine for Waguri Bot.

Coordinates:
- Multi-representation Text Normalization Pipeline
- 12 Categorized Dictionaries (Sexual abuse, harassment, vulgarity, assault, rape, CSAM, Hindi, Hinglish, threats, insults)
- Compiled Regex Pattern Detectors
- Common Bypass & Obfuscation Detectors (homoglyphs, leet, spaced-out, special characters)
- Controlled Fuzzy Matching
- Context-Aware Safe Exemption Evaluation
- Scoring & Action Classifier
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from moderation.abuse.dictionaries import (
    CATEGORIZED_DICTIONARIES,
    SAFE_CONTEXT_WORDS,
    SECOND_PERSON_PRONOUNS,
)
from moderation.abuse.normalizer import TextNormalizer
from moderation.abuse.patterns import (
    DIRECT_ATTACK_REGEXES,
    OBFUSCATED_CORE_REGEXES,
    PHYSICAL_ASSAULT_REGEXES,
    RAPE_HARASSMENT_REGEXES,
    SAFE_CONTEXT_REGEXES,
    SEXUAL_HARASSMENT_REGEXES,
    TARGETED_HARASSMENT_REGEXES,
    THREAT_REGEXES,
)
from moderation.abuse.scorer import AbuseAction, AbuseResult, AbuseScorer

logger = logging.getLogger("Waguri.AbuseDetector")


def fast_levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings efficiently."""
    if len(s1) < len(s2):
        return fast_levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


class AbuseDetector:
    """Production-grade multi-layer Abuse Detection Engine."""

    def __init__(self, scorer: Optional[AbuseScorer] = None):
        self.scorer = scorer or AbuseScorer()
        self.normalizer = TextNormalizer()

        # Pre-partition dictionaries into single-word and multi-word sets for O(1) lookups
        self._single_words: Dict[str, Set[str]] = {}
        self._multi_words: Dict[str, List[str]] = {}

        for cat, words in CATEGORIZED_DICTIONARIES.items():
            singles = set()
            multis = []
            for w in words:
                w_clean = w.lower().strip()
                if " " in w_clean:
                    multis.append(w_clean)
                else:
                    singles.add(w_clean)
            self._single_words[cat] = singles
            self._multi_words[cat] = multis

        # Candidates for controlled fuzzy matching (length >= 6)
        self._fuzzy_candidates: List[Tuple[str, str]] = []
        for cat in ("hindi_abusive", "general_abusive", "sexual_vulgarity"):
            for w in self._single_words.get(cat, set()):
                if len(w) >= 6:
                    self._fuzzy_candidates.append((w, cat))

    def check_message(
        self,
        text: str,
        custom_blocked_words: Optional[List[str]] = None,
        custom_allowed_words: Optional[List[str]] = None,
        settings: Optional[dict] = None,
    ) -> AbuseResult:
        """
        Analyze message text across all detection pipelines.
        Returns detailed AbuseResult with score and recommended action.
        """
        if not text or not text.strip():
            return AbuseResult(
                is_abusive=False,
                score=0,
                action=AbuseAction.ALLOW,
                category="clean",
                reason="Empty message",
            )

        # 0. Check per-group custom allowed words (Whitelisted words take precedence)
        raw_lower = text.lower()
        if custom_allowed_words:
            for allowed in custom_allowed_words:
                allowed_clean = allowed.strip().lower()
                if allowed_clean and re.search(rf"\b{re.escape(allowed_clean)}\b", raw_lower):
                    # Check if the entire message is basically just the whitelisted term
                    if len(raw_lower.strip()) <= len(allowed_clean) + 5:
                        return AbuseResult(
                            is_abusive=False,
                            score=0,
                            action=AbuseAction.ALLOW,
                            category="allowed",
                            matched_terms=[allowed],
                            is_exempted=True,
                            reason=f"Matched custom allowed keyword '{allowed}'",
                        )

        # 1. Check custom blocked words
        if custom_blocked_words:
            for blocked in custom_blocked_words:
                blocked_clean = blocked.strip().lower()
                if blocked_clean and re.search(rf"\b{re.escape(blocked_clean)}\b", raw_lower):
                    return self.scorer.evaluate(
                        base_tier="obfuscated_keyword" if " " in blocked_clean else "exact_keyword",
                        categories=["custom_blocked"],
                        matched_terms=[blocked],
                        is_obfuscated=False,
                        custom_bonus=20,
                    )

        # 2. Text Normalization Pipeline
        norm = self.normalizer.normalize_pipeline(text)
        tokens: List[str] = norm["tokens"]
        token_set = set(tokens)

        detected_categories: List[str] = []
        matched_terms: List[str] = []
        highest_base_tier: str = "exact_keyword"
        is_obfuscated: bool = False

        # Helper to record match
        def record_match(tier: str, cat: str, term: str, obfuscated: bool = False):
            nonlocal highest_base_tier, is_obfuscated
            if cat not in detected_categories:
                detected_categories.append(cat)
            if term not in matched_terms:
                matched_terms.append(term)
            if obfuscated:
                is_obfuscated = True

            tier_priority = [
                "minor_insult",
                "exact_keyword",
                "obfuscated_keyword",
                "targeted_harassment",
                "explicit_phrase",
                "physical_assault",
                "rape_harassment",
                "sexual_harassment",
                "explicit_threat",
                "child_exploitation",
            ]
            current_idx = tier_priority.index(highest_base_tier) if highest_base_tier in tier_priority else 0
            new_idx = tier_priority.index(tier) if tier in tier_priority else 0
            if new_idx > current_idx:
                highest_base_tier = tier

        # 3. Check Regex Patterns on various normalized streams
        streams_to_check = [
            norm["clean_nfkc"],
            norm["transliterated"],
            norm["collapsed_punct"],
            norm["collapsed_spaces"],
            norm["reduced"],
        ]

        # 3a. Child Sexual Exploitation Terminology (Critical Tier)
        for cat in ("child_exploitation",):
            for multi in self._multi_words.get(cat, []):
                for s in streams_to_check:
                    if re.search(rf"\b{re.escape(multi)}\b", s):
                        record_match("child_exploitation", cat, multi)
            for w in self._single_words.get(cat, set()):
                if w in token_set:
                    record_match("child_exploitation", cat, w)

        # 3b. Direct Threat Patterns
        for pattern in THREAT_REGEXES:
            for s in streams_to_check:
                m = pattern.search(s)
                if m:
                    record_match("explicit_threat", "threatening_language", m.group(0))

        # 3c. Rape Harassment Patterns
        for pattern in RAPE_HARASSMENT_REGEXES:
            for s in streams_to_check:
                m = pattern.search(s)
                if m:
                    record_match("rape_harassment", "rape_harassment", m.group(0))

        # 3d. Sexual Harassment Patterns
        for pattern in SEXUAL_HARASSMENT_REGEXES:
            for s in streams_to_check:
                m = pattern.search(s)
                if m:
                    record_match("sexual_harassment", "sexual_harassment", m.group(0))

        # 3e. Physical Assault Patterns
        for pattern in PHYSICAL_ASSAULT_REGEXES:
            for s in streams_to_check:
                m = pattern.search(s)
                if m:
                    record_match("physical_assault", "physical_assault", m.group(0))

        # 3f. Targeted Harassment Patterns
        for pattern in TARGETED_HARASSMENT_REGEXES:
            for s in streams_to_check:
                m = pattern.search(s)
                if m:
                    record_match("targeted_harassment", "targeted_harassment", m.group(0))

        # 3g. Obfuscated Core Word Patterns (f.u.c.k, m a d a r c h o d, etc.)
        for name, pattern in OBFUSCATED_CORE_REGEXES:
            m = pattern.search(norm["clean_nfkc"]) or pattern.search(norm["raw"])
            if m:
                record_match("obfuscated_keyword", "general_abusive", m.group(0), obfuscated=True)

        # 4. Dictionary Matching across Single Words and Multi-Word Phrases
        for cat, singles in self._single_words.items():
            # Check single word tokens in token set
            intersection = singles.intersection(token_set)
            if intersection:
                tier = "exact_keyword"
                if cat in ("sexual_harassment", "rape_harassment", "additional_harassment"):
                    tier = "sexual_harassment"
                elif cat in ("threatening_language", "additional_violence"):
                    tier = "explicit_threat"
                elif cat in ("physical_assault",):
                    tier = "physical_assault"
                for word in intersection:
                    # Check if token came from collapsed or leet streams (obfuscated)
                    is_obf = word not in re.findall(r"\w+", norm["clean_nfkc"])
                    record_match(tier, cat, word, obfuscated=is_obf)

        # Check multi-word dictionary phrases
        for cat, multis in self._multi_words.items():
            for phrase in multis:
                tier = "explicit_phrase"
                if cat in ("sexual_harassment", "rape_harassment", "additional_harassment"):
                    tier = "sexual_harassment"
                elif cat in ("threatening_language", "additional_violence"):
                    tier = "explicit_threat"
                elif cat in ("physical_assault",):
                    tier = "physical_assault"

                phrase_pattern = rf"(?<![a-zA-Z0-9]){re.escape(phrase)}(?![a-zA-Z0-9])"
                for s in streams_to_check:
                    if re.search(phrase_pattern, s):
                        record_match(tier, cat, phrase)
                        break

        # 5. Controlled Fuzzy Matching for Intentional Misspellings
        # Only checks tokens with length >= 6 against dictionary slurs with length >= 6
        for t in tokens:
            if len(t) < 6:
                continue
            for kw, cat in self._fuzzy_candidates:
                if abs(len(t) - len(kw)) <= 1:
                    dist = fast_levenshtein(t, kw)
                    if dist == 1:
                        record_match("obfuscated_keyword", cat, f"{t} (~{kw})", obfuscated=True)
                        break

        # If no abusive terms detected, return clean ALLOW
        if not matched_terms:
            return AbuseResult(
                is_abusive=False,
                score=0,
                action=AbuseAction.ALLOW,
                category="clean",
                reason="Clean content",
            )

        # 6. Context-Aware Evaluation (Safe context vs Direct Attack)
        is_safe_context = False
        # Check safe context regexes & words
        for pattern in SAFE_CONTEXT_REGEXES:
            if pattern.search(norm["clean_nfkc"]):
                is_safe_context = True
                break
        if not is_safe_context:
            for word in SAFE_CONTEXT_WORDS:
                if word in token_set or word in norm["clean_nfkc"]:
                    is_safe_context = True
                    break

        # Check direct attack regexes & pronouns
        is_direct_attack = False
        for pattern in DIRECT_ATTACK_REGEXES:
            if pattern.search(norm["clean_nfkc"]):
                is_direct_attack = True
                break
        if not is_direct_attack:
            if SECOND_PERSON_PRONOUNS.intersection(token_set):
                # If a second-person pronoun is combined with an insult, flag as direct attack
                is_direct_attack = True

        # 7. Compute final score through AbuseScorer
        return self.scorer.evaluate(
            base_tier=highest_base_tier,
            categories=detected_categories,
            matched_terms=matched_terms,
            is_obfuscated=is_obfuscated,
            is_safe_context=is_safe_context,
            is_direct_attack=is_direct_attack,
        )


# Global singleton instance for high-performance reuse
_global_detector: Optional[AbuseDetector] = None


def get_abuse_detector() -> AbuseDetector:
    """Retrieve or create the global singleton AbuseDetector."""
    global _global_detector
    if _global_detector is None:
        _global_detector = AbuseDetector()
    return _global_detector

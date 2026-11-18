"""
Context-Aware Scoring Engine and Moderation Action Classifier for Abuse Detection.

Calculates risk score based on detection severity, category, repetition, and context.
Applies exemptions for legitimate discussions, education, reporting, and safety warnings,
while preventing exemptions from shielding direct harassment or credible threats.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set


class AbuseAction(str, Enum):
    ALLOW = "allow"            # Score 0-29: Clean, pass through
    MONITOR = "monitor"        # Score 30-49: Low risk, log/review only
    WARN = "warn"              # Score 50-69: Delete message & issue warning
    MUTE_TEMP = "mute_temp"    # Score 70-89: Delete message & warning/temp mute
    MUTE_HEAVY = "mute_heavy"  # Score 90-100: Critical violation, delete + immediate mute


@dataclass
class AbuseResult:
    """Detailed evaluation result returned by the moderation engine."""
    is_abusive: bool
    score: int
    action: AbuseAction
    category: str
    matched_categories: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)
    is_obfuscated: bool = False
    is_exempted: bool = False
    reason: str = ""
    suggested_mute_seconds: int = 0


class AbuseScorer:
    """Calculates moderation score and maps to actionable thresholds."""

    # Default baseline scores by detection tier
    BASE_SCORES = {
        "child_exploitation": 100,
        "explicit_threat": 95,
        "sexual_harassment": 90,
        "rape_harassment": 90,
        "physical_assault": 85,
        "explicit_phrase": 75,
        "targeted_harassment": 75,
        "obfuscated_keyword": 65,
        "exact_keyword": 50,
        "minor_insult": 35,
    }

    # Action thresholds
    THRESHOLD_ALLOW = 29
    THRESHOLD_MONITOR = 49
    THRESHOLD_WARN = 69
    THRESHOLD_MUTE_TEMP = 89
    # 90+ is heavy moderation

    def __init__(
        self,
        warn_threshold: int = 50,
        mute_threshold: int = 85,
        additional_match_bonus: int = 15,
    ):
        self.warn_threshold = warn_threshold
        self.mute_threshold = mute_threshold
        self.additional_match_bonus = additional_match_bonus

    def evaluate(
        self,
        base_tier: str,
        categories: List[str],
        matched_terms: List[str],
        is_obfuscated: bool = False,
        is_safe_context: bool = False,
        is_direct_attack: bool = False,
        custom_bonus: int = 0,
    ) -> AbuseResult:
        """
        Compute total abuse score and determine appropriate moderation action.
        """
        # 1. Base score from primary detection tier
        score = self.BASE_SCORES.get(base_tier, 50)

        # 2. Add bonus for multiple matches or extra terms
        if len(matched_terms) > 1:
            score += min(30, (len(matched_terms) - 1) * self.additional_match_bonus)

        # Add custom severity adjustment
        score += custom_bonus

        # 3. Direct attack escalator: if an abusive term is accompanied by second-person attack ("you are a...")
        if is_direct_attack and score < 90:
            score = min(90, score + 15)

        # 4. Contextual exemption adjustment
        # Educational, safety, or reporting context reduces score ONLY if NOT a direct attack
        is_exempted = False
        if is_safe_context and not is_direct_attack:
            # Critical offenses (child exploitation, violent assault threats) cannot be exempted
            if base_tier not in ("child_exploitation", "explicit_threat", "rape_harassment"):
                score = max(20, score - 50)
                is_exempted = True

        # Clamp score between 0 and 100
        score = max(0, min(100, score))

        # 5. Determine action
        if is_exempted or score <= self.THRESHOLD_ALLOW:
            action = AbuseAction.ALLOW
            is_abusive = False
            suggested_mute = 0
        elif score <= self.THRESHOLD_MONITOR:
            action = AbuseAction.MONITOR
            is_abusive = False  # Logged/monitored, not deleted
            suggested_mute = 0
        elif score <= self.THRESHOLD_WARN:
            action = AbuseAction.WARN
            is_abusive = True
            suggested_mute = 0
        elif score <= self.THRESHOLD_MUTE_TEMP:
            action = AbuseAction.MUTE_TEMP
            is_abusive = True
            suggested_mute = 1800  # 30 minutes
        else:
            action = AbuseAction.MUTE_HEAVY
            is_abusive = True
            suggested_mute = 7200  # 2 hours

        # Human-friendly reason summary
        primary_cat = categories[0] if categories else "general_abuse"
        terms_display = ", ".join(f"'{t}'" for t in matched_terms[:3])
        if is_exempted:
            reason = f"Exempted legitimate/educational context (score: {score})"
        else:
            reason = f"Detected {primary_cat.replace('_', ' ')} (Score: {score}, Matches: {terms_display})"

        return AbuseResult(
            is_abusive=is_abusive,
            score=score,
            action=action,
            category=primary_cat,
            matched_categories=categories,
            matched_terms=matched_terms,
            is_obfuscated=is_obfuscated,
            is_exempted=is_exempted,
            reason=reason,
            suggested_mute_seconds=suggested_mute,
        )

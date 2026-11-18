"""
Compiled Regular Expressions and Phrase Detection Patterns for Abuse Detection.

All patterns are compiled at module import time for optimal runtime performance.
Regexes use word boundaries to avoid false positives on legitimate conversations.
"""

import re
from typing import List, Pattern, Tuple

# 1. Sexual Harassment Phrases
SEXUAL_HARASSMENT_REGEXES: List[Pattern] = [
    re.compile(r"\b(?:send|give)\s+(?:me\s+)?(?:your\s+)?(?:nudes?|boobs?|tits?|pussy|dick|cock|nude\s+pics?)\b", re.IGNORECASE),
    re.compile(r"\bshow\s+(?:me\s+)?(?:your\s+)?(?:boobs?|boobies|tits?|pussy|dick|cock|vagina|cleavage)\b", re.IGNORECASE),
    re.compile(r"\b(?:wanna\s+fuck|want\s+sex|have\s+sex\s+with\s+me|let'?s\s+fuck)\b", re.IGNORECASE),
    re.compile(r"\b(?:sex\s+(?:karegi|karega)|chudegi\s+kya|chudega\s+kya)\b", re.IGNORECASE),
    re.compile(r"\b(?:apni\s+)?(?:nangi\s+photo|nude\s+pic)\s+(?:bhej|dikha)\b", re.IGNORECASE),
    re.compile(r"\b(?:teri\s+le\s+lu(?:nga)?|bed\s+pe\s+aa|strip\s+for\s+me)\b", re.IGNORECASE),
    re.compile(r"\b(?:apna\s+rate\s+bata|kitne\s+me\s+aayegi|ek\s+raat\s+ka\s+kya\s+logi)\b", re.IGNORECASE),
]

# 2. Rape & Sexual Coercion Patterns
RAPE_HARASSMENT_REGEXES: List[Pattern] = [
    re.compile(r"\b(?:i\s+will|i'll|gonna|want\s+to)\s+rape\s+(?:you|her|him)\b", re.IGNORECASE),
    re.compile(r"\b(?:gang\s*bang|gang\s*rape|gang\s*raped)\b", re.IGNORECASE),
    re.compile(r"\bbalatkar\s+kar(?:unga|enge|du)\b", re.IGNORECASE),
    re.compile(r"\bterko\s+chod\s*(?:dunga|unga|enge)\b", re.IGNORECASE),
    re.compile(r"\bdeserves\s+to\s+be\s+raped\b", re.IGNORECASE),
]

# 3. Direct Threatening Language & Violent Intimidation Patterns
THREAT_REGEXES: List[Pattern] = [
    re.compile(r"\b(?:i\s+will|i'll|gonna|imma)\s+(?:kill|murder|slit\s+your\s+throat|strangle|shoot)\s+you\b", re.IGNORECASE),
    re.compile(r"\b(?:kill\s+yourself|go\s+die|hope\s+you\s+die|kys)\b", re.IGNORECASE),
    re.compile(r"\b(?:mar\s*ja\s*kutte|jaan\s+se\s+mar\s*(?:dunga|unga)|mar\s*dalunga)\b", re.IGNORECASE),
    re.compile(r"\b(?:ghar\s+(?:me\s+)?aake\s+marunga|zinda\s+nahi\s+chodunga)\b", re.IGNORECASE),
    re.compile(r"\b(?:haddi\s+tod\s+dunga|acid\s+(?:phek|fek)\s+dunga|goli\s+mar\s+dunga|chaku\s+mar\s+dunga)\b", re.IGNORECASE),
    re.compile(r"\b(?:i\s+know\s+where\s+you\s+live|doxx\s+you|leak\s+your\s+(?:address|info|nudes))\b", re.IGNORECASE),
    re.compile(r"\btujhe\s+khatam\s+kar\s+dunga\b", re.IGNORECASE),
]

# 4. Physical Assault Patterns
PHYSICAL_ASSAULT_REGEXES: List[Pattern] = [
    re.compile(r"\b(?:beat\s+you\s+to\s+death|break\s+your\s+(?:face|bones|teeth|jaw)|smash\s+your\s+skull)\b", re.IGNORECASE),
    re.compile(r"\b(?:chehra\s+bigad\s+dunga|mar\s+mar\s+ke\s+lal\s+kar\s+dunga)\b", re.IGNORECASE),
    re.compile(r"\b(?:beat\s+the\s+shit\s+out\s+of\s+you|rip\s+your\s+throat)\b", re.IGNORECASE),
]

# 5. Targeted Harassment Patterns
TARGETED_HARASSMENT_REGEXES: List[Pattern] = [
    re.compile(r"\b(?:you\s+are\s+a|u\s+r\s+a|you're\s+a)\s+(?:whore|slut|prostitute|bitch|bastard|madarchod|chutiya|randi|scumbag|loser)\b", re.IGNORECASE),
    re.compile(r"\b(?:call\s+girl|randikhana|worthless\s+piece\s+of\s+shit|waste\s+of\s+space)\b", re.IGNORECASE),
    re.compile(r"\b(?:kutte\s+ki\s+maut\s+marega|teri\s+aukaat\s+nahi\s+hai)\b", re.IGNORECASE),
    re.compile(r"\b(?:teri\s+maa\s+ki|tere\s+baap\s+ka|maa\s+ka\s+bhosda)\b", re.IGNORECASE),
]

# 6. Obfuscated Core Word Regexes (Catches spaced, punctuated, and symbol-substituted bypass variants)
OBFUSCATED_CORE_REGEXES: List[Tuple[str, Pattern]] = [
    ("fuck", re.compile(r"\bf[\W_]*[u@o0*!#a\u0430\u043e\u0443]?[\W_]*c[\W_]*k(?:ing|er|ed)?\b", re.IGNORECASE)),
    ("bitch", re.compile(r"\bb[\W_]*[i!1|*]?[\W_]*t[\W_]*c[\W_]*h(?:es|y)?\b", re.IGNORECASE)),
    ("bastard", re.compile(r"\bb[\W_]*[a@4*]?[\W_]*s[\W_]*t[\W_]*[a@4*]?[\W_]*r[\W_]*d\b", re.IGNORECASE)),
    ("cunt", re.compile(r"\bc[\W_]*[u@*!#0o]?[\W_]*n[\W_]*t\b", re.IGNORECASE)),
    ("pussy", re.compile(r"\bp[\W_]*[u@*!#0o]?[\W_]*s+[\W_]*y\b", re.IGNORECASE)),
    ("madarchod", re.compile(r"\bm[\W_]*[a@4*]?[\W_]*d[\W_]*[a@4*]?[\W_]*r[\W_]*c[\W_]*h[\W_]*[o0*]?[\W_]*d\b", re.IGNORECASE)),
    ("bhenchod", re.compile(r"\bb[\W_]*[he3*]{1,2}[\W_]*n[\W_]*c[\W_]*h[\W_]*[o0*]?[\W_]*d\b", re.IGNORECASE)),
    ("chutiya", re.compile(r"\bc[\W_]*h[\W_]*[u@*!0o]?[\W_]*t[\W_]*[i1!*]?[\W_]*y[\W_]*[a@4*]?\b", re.IGNORECASE)),
    ("bhosdike", re.compile(r"\bb[\W_]*h[\W_]*[o0*]?[\W_]*s[\W_]*[ad@4*]?[\W_]*[i1!*]?[\W_]*k[\W_]*[e3*]?\b", re.IGNORECASE)),
    ("randi", re.compile(r"\br[\W_]*[a@4*]?[\W_]*n[\W_]*d[\W_]*[i1!*]?\b", re.IGNORECASE)),
    ("gandu", re.compile(r"\bg[\W_]*[a@4*]*[\W_]*n[\W_]*d[\W_]*[u0*]?\b", re.IGNORECASE)),
    ("lauda", re.compile(r"\bl[\W_]*[ao0u*]{1,2}[\W_]*d[\W_]*[aeu*]?\b", re.IGNORECASE)),
]

# 7. Safe Context & Exemption Patterns (Educational, Reporting, Anti-Harassment, Awareness)
SAFE_CONTEXT_REGEXES: List[Pattern] = [
    re.compile(r"\b(?:report(?:ing|ed)?|cyberbullying\s+awareness|awareness\s+campaign|anti-abuse|abuse\s+prevention|harassment\s+policy)\b", re.IGNORECASE),
    re.compile(r"\b(?:complaint\s+filed|police\s+complaint|helpline\s+number|counseling\s+session|anti-rape\s+rally)\b", re.IGNORECASE),
    re.compile(r"\b(?:stop\s+saying|don't\s+call\s+me|was\s+banned\s+for|warned\s+for\s+saying|reported\s+for\s+saying)\b", re.IGNORECASE),
]

# 8. Second-Person Direct Attack Regexes (Disqualifies safe context exemptions)
DIRECT_ATTACK_REGEXES: List[Pattern] = [
    re.compile(r"\b(?:you\s+are|you're|u\s+r|teri|tera|tujhe|terko|tum\s+ek|ap\s+ek)\b", re.IGNORECASE),
    re.compile(r"\b(?:fuck\s+you|fuck\s+u|screw\s+you)\b", re.IGNORECASE),
]

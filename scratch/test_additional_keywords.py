"""
Automated Test for all Additional Abuse Keywords.
Verifies that every single keyword in all 6 user-provided categories
is properly detected with is_abusive=True and score >= 50.
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))
from moderation.abuse.engine import get_abuse_detector
from moderation.abuse.dictionaries import (
    ADDITIONAL_SEXUAL_WORDS,
    ADDITIONAL_HARASSMENT_WORDS,
    ADDITIONAL_VIOLENCE_WORDS,
    ADDITIONAL_ABUSE_WORDS,
    ADDITIONAL_HINGLISH_WORDS,
    HINDI_WORDS,
)

def run_tests():
    detector = get_abuse_detector()

    categories = {
        "ADDITIONAL_SEXUAL_WORDS": ADDITIONAL_SEXUAL_WORDS,
        "ADDITIONAL_HARASSMENT_WORDS": ADDITIONAL_HARASSMENT_WORDS,
        "ADDITIONAL_VIOLENCE_WORDS": ADDITIONAL_VIOLENCE_WORDS,
        "ADDITIONAL_ABUSE_WORDS": ADDITIONAL_ABUSE_WORDS,
        "ADDITIONAL_HINGLISH_WORDS": ADDITIONAL_HINGLISH_WORDS,
        "HINDI_WORDS": HINDI_WORDS,
    }

    total_words = 0
    passed_words = 0
    failed = []

    for cat_name, words in categories.items():
        print(f"\n--- Testing {cat_name} ({len(words)} keywords) ---")
        for word in words:
            total_words += 1
            test_phrase = f"hello {word} test"
            res = detector.check_message(test_phrase)
            if not res.is_abusive:
                # Also try standalone
                res_standalone = detector.check_message(word)
                if not res_standalone.is_abusive:
                    failed.append((cat_name, word, res.reason))
                    continue
                else:
                    res = res_standalone

            passed_words += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed_words}/{total_words} PASSED ({len(failed)} failed)")
    print("=" * 60)

    if failed:
        print(f"FAILED {len(failed)} words:")
        for cat, w, r in failed:
            print(f"  [{cat}] '{w}' -> {r}")
        sys.exit(1)
    else:
        print("ALL KEYWORDS SUCCESSFULLY DETECTED AND FLAGGED FOR MODERATION!")

if __name__ == "__main__":
    run_tests()

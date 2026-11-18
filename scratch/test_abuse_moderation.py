"""
Comprehensive Automated Test Suite for Abuse Detection & Auto-Moderation System.

Tests all 20 required criteria:
1. Normal conversation allowed
2. Exact abusive keywords detected
3. Words with spaces detected (f u c k, m a d a r c h o d)
4. Words with special characters detected (f.u.c.k, f*u*c*k)
5. Leetspeak detected (b1tch, f@ck)
6. Unicode manipulation detected (homoglyphs, zero-width)
7. Repeated characters detected (fuuuuuck, bhosssssdike)
8. Mixed-case words detected (FuCk, MaDaRcHoD)
9. Roman Hindi abusive words detected (madarchod, bhenchod, chutiya)
10. Devanagari abusive words detected (मादरचोद, चूतिया)
11. Mixed Hindi-English abuse detected (you fucking madarchod)
12. Multiword abusive phrases detected (kill yourself, send nudes, i will rape you)
13. Legitimate educational/reporting discussions not deleted
14. Group administrators exempted from moderation
15. Normal members cannot modify settings (/abuse on rejected)
16. Warning counts persist across bot executions
17. Edited messages handled correctly
18. Messages without text captions handled safely
19. Multiple simultaneous messages do not duplicate warnings
20. Existing bot commands and features remain functional
"""

import asyncio
import os
import sys
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telegram.constants import ChatMemberStatus, ChatType
from database import (
    add_user_abuse_warning,
    get_abuse_settings,
    get_group_settings,
    get_user_abuse_warnings_count,
    reset_user_abuse_warnings,
    update_abuse_settings,
)
from handlers.admin_check import invalidate_cache
from handlers.abuse_handler import (
    _processed_messages,
    abuse_command,
    handle_abuse_message,
)
from handlers.commands import help_command, start
from moderation.abuse import AbuseAction, get_abuse_detector


class TestAbuseDetectionSuite(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        invalidate_cache()
        _processed_messages.clear()
        self.detector = get_abuse_detector()
        self.test_chat_id = -1009988776655
        self.test_user_id = 123456789
        self.admin_user_id = 987654321
        reset_user_abuse_warnings(self.test_chat_id, self.test_user_id)
        update_abuse_settings(self.test_chat_id, abuse_detection_enabled=True, abuse_exempt_admins=False)

    def tearDown(self):
        invalidate_cache()
        _processed_messages.clear()
        reset_user_abuse_warnings(self.test_chat_id, self.test_user_id)

    def create_mock_update(
        self,
        text: str | None = None,
        caption: str | None = None,
        is_admin: bool = False,
        is_edited: bool = False,
        message_id: int = 1001,
        user_id: int | None = None,
    ):
        update = MagicMock()
        update.update_id = 55555

        chat = MagicMock()
        chat.id = self.test_chat_id
        chat.title = "Test Moderation Group"
        chat.type = ChatType.SUPERGROUP

        user = MagicMock()
        user.id = user_id or (self.admin_user_id if is_admin else self.test_user_id)
        user.username = "test_admin" if is_admin else "test_user"
        user.first_name = "AdminUser" if is_admin else "RegularUser"

        message = MagicMock()
        message.message_id = message_id
        message.chat = chat
        message.from_user = user
        message.text = text
        message.caption = caption
        message.reply_to_message = None
        message.sender_chat = None
        message.reply_text = AsyncMock()
        message.delete = AsyncMock()

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user
        update.edited_message = message if is_edited else None

        context = MagicMock()
        context.bot.id = 88888888
        context.bot.send_message = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.restrict_chat_member = AsyncMock(return_value=True)

        async def mock_get_admins(chat_id):
            admin_bot = MagicMock()
            admin_bot.user.id = context.bot.id
            admin_bot.status = ChatMemberStatus.ADMINISTRATOR
            admin_bot.can_delete_messages = True
            admin_bot.can_restrict_members = True

            admin_human = MagicMock()
            admin_human.user.id = self.admin_user_id
            admin_human.status = ChatMemberStatus.ADMINISTRATOR
            return [admin_bot, admin_human]

        async def mock_get_chat_member(chat_id, user_id):
            member = MagicMock()
            member.user.id = user_id
            if user_id == self.admin_user_id:
                member.status = ChatMemberStatus.ADMINISTRATOR
            else:
                member.status = ChatMemberStatus.MEMBER
            return member

        context.bot.get_chat_administrators = AsyncMock(side_effect=mock_get_admins)
        context.bot.get_chat_member = AsyncMock(side_effect=mock_get_chat_member)
        return update, context

    # 1. Normal conversation should not be deleted
    def test_01_normal_conversation_allowed(self):
        text = "Hello everyone, hope you are having a productive day with the project!"
        result = self.detector.check_message(text)
        self.assertFalse(result.is_abusive)
        self.assertEqual(result.action, AbuseAction.ALLOW)

    # 2. Exact abusive keywords should be detected
    def test_02_exact_abusive_keyword_detected(self):
        result = self.detector.check_message("you are a madarchod")
        self.assertTrue(result.is_abusive)
        self.assertGreaterEqual(result.score, 50)
        self.assertIn("madarchod", [t.lower() for t in result.matched_terms])

    # 3. Words with spaces should be detected
    def test_03_space_insertion_detected(self):
        result1 = self.detector.check_message("what the f u c k is wrong with you")
        self.assertTrue(result1.is_abusive)

        result2 = self.detector.check_message("teri m a d a r c h o d")
        self.assertTrue(result2.is_abusive)

    # 4. Words with special characters should be detected
    def test_04_special_characters_detected(self):
        result1 = self.detector.check_message("shut up you f.u.c.k.i.n.g clown")
        self.assertTrue(result1.is_abusive)

        result2 = self.detector.check_message("f*u*c*k this")
        self.assertTrue(result2.is_abusive)

    # 5. Leetspeak should be detected
    def test_05_leetspeak_detected(self):
        result1 = self.detector.check_message("stop acting like a b1tch")
        self.assertTrue(result1.is_abusive)

        result2 = self.detector.check_message("f@ck off")
        self.assertTrue(result2.is_abusive)

    # 6. Unicode manipulation should be detected
    def test_06_unicode_manipulation_detected(self):
        # Cyrillic lookalike for 'a' (\u0430)
        homoglyph_text = "shut up f\u0430ck"
        result = self.detector.check_message(homoglyph_text)
        self.assertTrue(result.is_abusive)

        # Zero-width space insertion
        zw_text = "m\u200Bad\u200Barchod"
        result_zw = self.detector.check_message(zw_text)
        self.assertTrue(result_zw.is_abusive)

    # 7. Repeated characters should be detected
    def test_07_repeated_characters_detected(self):
        result1 = self.detector.check_message("fuuuuuck you")
        self.assertTrue(result1.is_abusive)

        result2 = self.detector.check_message("bhosssssdike get lost")
        self.assertTrue(result2.is_abusive)

    # 8. Mixed-case words should be detected
    def test_08_mixed_case_words_detected(self):
        result1 = self.detector.check_message("You FuCkInG idiot")
        self.assertTrue(result1.is_abusive)

        result2 = self.detector.check_message("teri MaDaRcHoD")
        self.assertTrue(result2.is_abusive)

    # 9. Roman Hindi abusive words should be detected
    def test_09_roman_hindi_detected(self):
        words = ["chutiya", "bhenchod", "harami", "randi", "gandu"]
        for w in words:
            res = self.detector.check_message(f"tere jaise {w}")
            self.assertTrue(res.is_abusive, f"Failed to detect Roman Hindi slur: {w}")

    # 10. Devanagari abusive words should be detected
    def test_10_devanagari_detected(self):
        words = ["मादरचोद", "बहनचोद", "चूतिया", "गांडू"]
        for w in words:
            res = self.detector.check_message(f"तू एक {w} है")
            self.assertTrue(res.is_abusive, f"Failed to detect Devanagari slur: {w}")

    # 11. Mixed Hindi-English abuse should be detected
    def test_11_mixed_hindi_english_detected(self):
        result = self.detector.check_message("you fucking madarchod don't message here")
        self.assertTrue(result.is_abusive)
        self.assertGreaterEqual(result.score, 70)

    # 12. Multiword abusive phrases should be detected
    def test_12_multiword_phrases_detected(self):
        phrases = [
            "kill yourself now",
            "send nudes please",
            "i will rape you",
            "beat you to death",
        ]
        for p in phrases:
            res = self.detector.check_message(p)
            self.assertTrue(res.is_abusive, f"Failed to detect phrase: {p}")
            self.assertGreaterEqual(res.score, 75)

    # 13. Legitimate educational/reporting discussions not deleted
    def test_13_educational_reporting_safe_context(self):
        educational = "Our organization held a conference for cyberbullying awareness and how to report abuse online."
        res = self.detector.check_message(educational)
        self.assertFalse(res.is_abusive)
        self.assertEqual(res.action, AbuseAction.ALLOW)

    # 14. Group administrators should be exempted from moderation when exempt_admins is enabled
    async def test_14_admin_exemptions(self):
        update_abuse_settings(self.test_chat_id, abuse_exempt_admins=True)
        update, context = self.create_mock_update(text="you are a madarchod", is_admin=True)
        await handle_abuse_message(update, context)
        # Message delete should NOT be called for an exempt admin
        update.effective_message.delete.assert_not_called()

    # 14b. Abusive words are deleted by default (even during testing)
    async def test_14b_abusive_words_deleted_by_default(self):
        update_abuse_settings(self.test_chat_id, abuse_exempt_admins=False)
        update, context = self.create_mock_update(text="you are a madarchod", is_admin=True)
        await handle_abuse_message(update, context)
        update.effective_message.delete.assert_called_once()

    # 15. Normal members cannot modify settings
    async def test_15_non_admin_cannot_change_settings(self):
        update, context = self.create_mock_update(text="/abuse on", is_admin=False)
        context.args = ["on"]
        await abuse_command(update, context)
        update.effective_message.reply_text.assert_called_once()
        call_text = update.effective_message.reply_text.call_args[0][0]
        self.assertIn("Access Denied", call_text)

    # 16. Warning counts persist across bot executions
    def test_16_warning_counts_persist(self):
        reset_user_abuse_warnings(self.test_chat_id, self.test_user_id)
        w1 = add_user_abuse_warning(self.test_chat_id, self.test_user_id, "Abuse 1")
        w2 = add_user_abuse_warning(self.test_chat_id, self.test_user_id, "Abuse 2")
        self.assertEqual(w1, 1)
        self.assertEqual(w2, 2)
        count = get_user_abuse_warnings_count(self.test_chat_id, self.test_user_id)
        self.assertEqual(count, 2)

    # 17. Edited messages should be handled correctly
    async def test_17_edited_message_handling(self):
        update, context = self.create_mock_update(
            text="edited text: you fucking madarchod",
            is_admin=False,
            is_edited=True,
            message_id=9901,
        )
        await handle_abuse_message(update, context)
        update.effective_message.delete.assert_called_once()

    # 18. Messages without text captions should not cause errors
    async def test_18_messages_without_text(self):
        update, context = self.create_mock_update(text=None, caption=None, is_admin=False)
        await handle_abuse_message(update, context)
        update.effective_message.delete.assert_not_called()

    # 19. Multiple simultaneous messages should not produce duplicate warnings
    async def test_19_concurrency_no_duplicate_warnings(self):
        reset_user_abuse_warnings(self.test_chat_id, self.test_user_id)
        update, context = self.create_mock_update(
            text="you are a madarchod",
            is_admin=False,
            message_id=8888,
        )
        # Call handle_abuse_message twice with identical message_id
        await handle_abuse_message(update, context)
        await handle_abuse_message(update, context)
        # Only 1 warning should be registered due to deduplication
        count = get_user_abuse_warnings_count(self.test_chat_id, self.test_user_id)
        self.assertEqual(count, 1)

    # 20. Existing bot commands continue working
    async def test_20_existing_commands_functional(self):
        update, context = self.create_mock_update(text="/start", is_admin=False)
        await start(update, context)
        self.assertTrue(update.effective_message.reply_text.called or context.bot.send_message.called)

        update2, context2 = self.create_mock_update(text="/help", is_admin=False)
        await help_command(update2, context2)
        self.assertTrue(update2.effective_message.reply_text.called or context2.bot.send_message.called)

    # 21. 1st violation issues warning, 2nd violation mutes user according to set time
    async def test_21_first_violation_warns_second_violation_mutes(self):
        reset_user_abuse_warnings(self.test_chat_id, self.test_user_id)
        update_abuse_settings(self.test_chat_id, abuse_mute_duration_minutes=45, abuse_warning_limit=1)

        # 1st violation
        update1, context1 = self.create_mock_update(text="you are a madarchod", is_admin=False, message_id=1001)
        await handle_abuse_message(update1, context1)

        # 1st time: message deleted + warning notice sent + NOT muted yet
        update1.effective_message.delete.assert_called_once()
        self.assertTrue(context1.bot.send_message.called)
        sent_warn_text = context1.bot.send_message.call_args[1].get("text") or context1.bot.send_message.call_args[0][1]
        self.assertIn("Warning [1/2]", sent_warn_text)
        context1.bot.restrict_chat_member.assert_not_called()

        # 2nd violation
        update2, context2 = self.create_mock_update(text="fuck you", is_admin=False, message_id=1002)
        await handle_abuse_message(update2, context2)

        # 2nd time: message deleted + user MUTED according to set time (45 mins)
        update2.effective_message.delete.assert_called_once()
        context2.bot.restrict_chat_member.assert_called_once()
        restrict_call = context2.bot.restrict_chat_member.call_args
        self.assertEqual(restrict_call[1]["chat_id"], self.test_chat_id)
        self.assertEqual(restrict_call[1]["user_id"], self.test_user_id)
        # Check until_date is roughly 45 minutes from now
        until = restrict_call[1]["until_date"]
        self.assertAlmostEqual(until, time.time() + (45 * 60), delta=10)


if __name__ == "__main__":
    unittest.main()

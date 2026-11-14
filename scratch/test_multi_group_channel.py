"""Comprehensive Test Suite for Multi-Group & Multi-Channel Waguri Bot.

Verifies all 14 scenarios from Section 15:
1. Add bot to Group A and Group B.
2. Configure Group A: enable anti-link, disable anti-spam.
3. Configure Group B: disable anti-link, enable anti-spam.
4. Send a link in Group A -> Should be deleted.
5. Send a link in Group B -> Should NOT be deleted.
6. Send repeated messages in Group A -> Should NOT trigger spam warnings.
7. Send repeated messages in Group B -> Should trigger warnings and restriction.
8. Verify Group A settings remain unchanged when Group B is modified.
9. Verify /settings panel works independently in each group.
10. Add bot to a Channel.
11. Send post with a link -> Should be deleted.
12. Verify /stats displays correct isolated data for each group.
13. Restart the bot -> Verify all group settings are retained from SQLite.
14. Verify simultaneous activity in multiple groups does not cause race conditions or cross-talk.
"""

import asyncio
import gc
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.constants import ChatMemberStatus, ChatType, MessageEntityType

import config
import database
from handlers.admin_check import invalidate_cache
from handlers.anti_link import handle_channel_post, handle_group_message
from handlers.anti_spam import handle_anti_spam
from handlers.feature_commands import disable_command, enable_command, features_command, stats_command
from handlers.registration import handle_my_chat_member
from handlers.settings_panel import settings_callback_handler, settings_command

TEST_DB_PATH = os.path.abspath("test_multi_waguri.db")


def cleanup_test_db():
    gc.collect()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


class TestMultiGroupAndChannel(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        cleanup_test_db()
        config.DATABASE_PATH = TEST_DB_PATH
        database.init_db(TEST_DB_PATH)
        invalidate_cache()

    async def asyncTearDown(self):
        cleanup_test_db()
        invalidate_cache()

    # -------------------------------------------------------------------------
    # Helper to mock a chat member update (adding/removing bot)
    # -------------------------------------------------------------------------
    def create_my_chat_member_update(self, chat_id: int, chat_title: str, chat_type: str, old_status: str, new_status: str):
        update = MagicMock()
        update.my_chat_member = MagicMock()
        update.my_chat_member.chat.id = chat_id
        update.my_chat_member.chat.title = chat_title
        update.my_chat_member.chat.type = chat_type

        update.my_chat_member.old_chat_member.status = old_status
        update.my_chat_member.new_chat_member.status = new_status
        return update

    # -------------------------------------------------------------------------
    # Helper to mock a message update
    # -------------------------------------------------------------------------
    def create_message_update(self, chat_id: int, chat_title: str, chat_type: str, user_id: int, text: str, is_admin: bool = False, update_id: int = 100):
        update = MagicMock()
        update.update_id = update_id

        chat = MagicMock()
        chat.id = chat_id
        chat.title = chat_title
        chat.type = chat_type

        user = MagicMock()
        user.id = user_id
        user.username = f"user_{user_id}"
        user.first_name = f"User{user_id}"

        message = MagicMock()
        message.message_id = update_id
        message.chat = chat
        message.from_user = user
        message.text = text
        message.caption = None
        message.entities = []
        message.caption_entities = []
        message.sender_chat = None
        message.delete = AsyncMock()
        message.reply_text = AsyncMock()

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user
        update.channel_post = None

        context = MagicMock()
        context.bot.id = 999999
        context.bot.send_message = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.restrict_chat_member = AsyncMock(return_value=True)

        # Mock bot's own permissions as admin
        bot_member_mock = MagicMock()
        bot_member_mock.user.id = context.bot.id
        bot_member_mock.status = ChatMemberStatus.ADMINISTRATOR
        bot_member_mock.can_delete_messages = True
        bot_member_mock.can_restrict_members = True

        # Mock sender membership
        member_mock = MagicMock()
        member_mock.user.id = user_id
        member_mock.status = ChatMemberStatus.ADMINISTRATOR if is_admin else ChatMemberStatus.MEMBER

        admins = [bot_member_mock]
        if is_admin:
            admins.append(member_mock)

        context.bot.get_chat_administrators = AsyncMock(return_value=admins)

        async def get_chat_member_side_effect(*args, **kwargs):
            u_id = kwargs.get("user_id") or (args[1] if len(args) > 1 else None)
            if u_id == context.bot.id:
                return bot_member_mock
            if is_admin and u_id == user_id:
                return member_mock
            regular = MagicMock()
            regular.user.id = u_id
            regular.status = ChatMemberStatus.MEMBER
            return regular

        context.bot.get_chat_member = AsyncMock(side_effect=get_chat_member_side_effect)

        return update, context

    # -------------------------------------------------------------------------
    # SCENARIOS 1-8: Two Independent Groups, Link & Spam Isolation
    # -------------------------------------------------------------------------
    async def test_scenarios_1_to_8_group_isolation(self):
        # 1. Add bot to Group A and Group B
        group_a_id = -100111
        group_b_id = -100222

        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock()

        upd_a = self.create_my_chat_member_update(group_a_id, "Group Alpha", ChatType.SUPERGROUP, ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER)
        await handle_my_chat_member(upd_a, ctx)

        upd_b = self.create_my_chat_member_update(group_b_id, "Group Beta", ChatType.SUPERGROUP, ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER)
        await handle_my_chat_member(upd_b, ctx)

        # Verify welcome message sent to both groups
        self.assertEqual(ctx.bot.send_message.call_count, 2)

        # 2. Configure Group A: enable anti-link, disable anti-spam
        database.update_group_feature(group_a_id, "anti_link_enabled", True)
        database.update_group_feature(group_a_id, "anti_spam_enabled", False)

        # 3. Configure Group B: disable anti-link, enable anti-spam
        database.update_group_feature(group_b_id, "anti_link_enabled", False)
        database.update_group_feature(group_b_id, "anti_spam_enabled", True)

        settings_a = database.get_group_settings(group_a_id)
        settings_b = database.get_group_settings(group_b_id)

        self.assertTrue(settings_a["anti_link_enabled"])
        self.assertFalse(settings_a["anti_spam_enabled"])
        self.assertFalse(settings_b["anti_link_enabled"])
        self.assertTrue(settings_b["anti_spam_enabled"])

        # 4. Send a link in Group A -> Should be deleted
        upd_link_a, ctx_link_a = self.create_message_update(group_a_id, "Group Alpha", ChatType.SUPERGROUP, user_id=101, text="Check out https://scam-site.com", is_admin=False, update_id=1)
        await handle_group_message(upd_link_a, ctx_link_a)
        upd_link_a.effective_message.delete.assert_awaited_once()

        # 5. Send a link in Group B -> Should NOT be deleted
        upd_link_b, ctx_link_b = self.create_message_update(group_b_id, "Group Beta", ChatType.SUPERGROUP, user_id=201, text="Check out https://scam-site.com", is_admin=False, update_id=2)
        await handle_group_message(upd_link_b, ctx_link_b)
        upd_link_b.effective_message.delete.assert_not_called()

        # 6. Send repeated messages in Group A -> Should NOT trigger spam warnings
        for i in range(1, 5):
            upd_spam_a, ctx_spam_a = self.create_message_update(group_a_id, "Group Alpha", ChatType.SUPERGROUP, user_id=102, text="Buy cheap tokens now!", is_admin=False, update_id=10 + i)
            await handle_anti_spam(upd_spam_a, ctx_spam_a)
            # Group A anti_spam is disabled, so no delete or warning should occur
            upd_spam_a.effective_message.delete.assert_not_called()
            ctx_spam_a.bot.send_message.assert_not_called()

        # 7. Send repeated messages in Group B -> Should trigger warnings and restriction
        user_b = 202
        # Message 1: Allowed, no warning
        u1, c1 = self.create_message_update(group_b_id, "Group Beta", ChatType.SUPERGROUP, user_id=user_b, text="Buy cheap tokens now!", is_admin=False, update_id=31)
        await handle_anti_spam(u1, c1)
        u1.effective_message.delete.assert_not_called()
        c1.bot.send_message.assert_not_called()

        # Message 2: Deleted + Warning 1
        u2, c2 = self.create_message_update(group_b_id, "Group Beta", ChatType.SUPERGROUP, user_id=user_b, text="Buy cheap tokens now!", is_admin=False, update_id=32)
        await handle_anti_spam(u2, c2)
        u2.effective_message.delete.assert_awaited_once()
        c2.bot.send_message.assert_awaited_once()
        self.assertIn("Warning 1/2", c2.bot.send_message.call_args[1]["text"])

        # Message 3: Deleted + Warning 2
        u3, c3 = self.create_message_update(group_b_id, "Group Beta", ChatType.SUPERGROUP, user_id=user_b, text="Buy cheap tokens now!", is_admin=False, update_id=33)
        await handle_anti_spam(u3, c3)
        u3.effective_message.delete.assert_awaited_once()
        c3.bot.send_message.assert_awaited_once()
        self.assertIn("Warning 2/2", c3.bot.send_message.call_args[1]["text"])

        # Message 4: Deleted + 24h Restriction + Spam cleanup
        u4, c4 = self.create_message_update(group_b_id, "Group Beta", ChatType.SUPERGROUP, user_id=user_b, text="Buy cheap tokens now!", is_admin=False, update_id=34)
        await handle_anti_spam(u4, c4)
        u4.effective_message.delete.assert_awaited_once()
        c4.bot.restrict_chat_member.assert_awaited_once()
        c4.bot.send_message.assert_awaited_once()
        self.assertIn("restricted for 24 hours", c4.bot.send_message.call_args[1]["text"])

        # 8. Verify Group A settings remain unchanged when Group B is modified
        settings_a_after = database.get_group_settings(group_a_id)
        self.assertTrue(settings_a_after["anti_link_enabled"])
        self.assertFalse(settings_a_after["anti_spam_enabled"])

    # -------------------------------------------------------------------------
    # SCENARIO 9: Independent /settings Panel
    # -------------------------------------------------------------------------
    async def test_scenario_9_settings_panel_independence(self):
        group_1 = -100333
        group_2 = -100444

        # Group 1 admin opens /settings
        upd_1, ctx_1 = self.create_message_update(group_1, "Group One", ChatType.SUPERGROUP, user_id=501, text="/settings", is_admin=True, update_id=50)
        await settings_command(upd_1, ctx_1)
        upd_1.effective_message.reply_text.assert_awaited_once()
        reply_markup_1 = upd_1.effective_message.reply_text.call_args[1]["reply_markup"]

        # Group 2 admin opens /settings
        upd_2, ctx_2 = self.create_message_update(group_2, "Group Two", ChatType.SUPERGROUP, user_id=502, text="/settings", is_admin=True, update_id=51)
        await settings_command(upd_2, ctx_2)
        upd_2.effective_message.reply_text.assert_awaited_once()
        reply_markup_2 = upd_2.effective_message.reply_text.call_args[1]["reply_markup"]

        # Verify buttons contain respective group IDs in callback_data
        btn_1 = reply_markup_1.inline_keyboard[0][0].callback_data
        btn_2 = reply_markup_2.inline_keyboard[0][0].callback_data
        self.assertEqual(btn_1, f"cfg:{group_1}:toggle_link")
        self.assertEqual(btn_2, f"cfg:{group_2}:toggle_link")

        # Admin toggles link in Group 1 via callback query
        query_update = MagicMock()
        query = MagicMock()
        query.data = f"cfg:{group_1}:toggle_link"
        query.message.chat.id = group_1
        query.from_user.id = 501
        query.edit_message_text = AsyncMock()
        query.answer = AsyncMock()
        query_update.callback_query = query
        query_update.effective_chat = query.message.chat
        query_update.effective_user = query.from_user

        ctx_cb = MagicMock()
        ctx_cb.bot.id = 999999
        admin_member = MagicMock()
        admin_member.user.id = 501
        admin_member.status = ChatMemberStatus.ADMINISTRATOR
        ctx_cb.bot.get_chat_member = AsyncMock(return_value=admin_member)
        ctx_cb.bot.get_chat_administrators = AsyncMock(return_value=[admin_member])

        await settings_callback_handler(query_update, ctx_cb)

        # Verify Group 1 toggled to OFF, but Group 2 remains ON
        self.assertFalse(database.get_group_settings(group_1)["anti_link_enabled"])
        self.assertTrue(database.get_group_settings(group_2)["anti_link_enabled"])

    # -------------------------------------------------------------------------
    # SCENARIOS 10-11: Multi-Channel Support & Channel Post Link Deletion
    # -------------------------------------------------------------------------
    async def test_scenarios_10_and_11_channel_support(self):
        channel_id = -100555
        ctx = MagicMock()

        # 10. Add bot to a Channel
        upd_chan = self.create_my_chat_member_update(channel_id, "News Channel", ChatType.CHANNEL, ChatMemberStatus.LEFT, ChatMemberStatus.ADMINISTRATOR)
        await handle_my_chat_member(upd_chan, ctx)

        settings = database.get_group_settings(channel_id)
        self.assertEqual(settings["chat_type"], "channel")
        self.assertTrue(settings["is_active"])
        self.assertTrue(settings["anti_link_enabled"])

        # 11. Send post with a link -> Should be deleted without warnings/restrictions
        chan_post_update = MagicMock()
        chan_post_update.update_id = 70
        post = MagicMock()
        post.message_id = 701
        post.text = "Join our sponsor telegram channel: https://t.me/spam_promo"
        post.caption = None
        post.entities = []
        post.caption_entities = []
        post.delete = AsyncMock()

        chat = MagicMock()
        chat.id = channel_id
        chat.title = "News Channel"
        chat.type = ChatType.CHANNEL

        chan_post_update.channel_post = post
        chan_post_update.effective_message = post
        chan_post_update.effective_chat = chat

        await handle_channel_post(chan_post_update, ctx)
        post.delete.assert_awaited_once()

        # Verify stat incremented
        stats = database.get_group_stats(channel_id)
        self.assertEqual(stats["links_deleted"], 1)

    # -------------------------------------------------------------------------
    # SCENARIO 12: Isolated /stats for Each Group & Channel
    # -------------------------------------------------------------------------
    async def test_scenario_12_stats_isolation(self):
        g1 = -100771
        g2 = -100772

        database.increment_stat(g1, "links_deleted", 5, "Group 1")
        database.increment_stat(g1, "spam_deleted", 3, "Group 1")
        database.increment_stat(g2, "links_deleted", 1, "Group 2")
        database.increment_stat(g2, "spam_deleted", 12, "Group 2")

        stats_1 = database.get_group_stats(g1)
        stats_2 = database.get_group_stats(g2)

        self.assertEqual(stats_1["links_deleted"], 5)
        self.assertEqual(stats_1["spam_deleted"], 3)
        self.assertEqual(stats_2["links_deleted"], 1)
        self.assertEqual(stats_2["spam_deleted"], 12)

        # Test /stats command output for admin in Group 1
        upd, ctx = self.create_message_update(g1, "Group 1", ChatType.SUPERGROUP, user_id=901, text="/stats", is_admin=True, update_id=80)
        await stats_command(upd, ctx)
        upd.effective_message.reply_text.assert_awaited_once()
        reply_text = upd.effective_message.reply_text.call_args[0][0]
        self.assertIn("Links Deleted:</b> 5", reply_text)
        self.assertIn("Spam Messages Deleted:</b> 3", reply_text)
        self.assertNotIn("12", reply_text)

    # -------------------------------------------------------------------------
    # SCENARIO 13: SQLite Persistence Across Bot Restart
    # -------------------------------------------------------------------------
    async def test_scenario_13_restart_persistence(self):
        group_id = -100888
        database.update_group_feature(group_id, "anti_link_enabled", False)
        database.update_group_feature(group_id, "warning_system_enabled", False)
        database.update_group_numeric_setting(group_id, "spam_window_seconds", 45)
        database.update_group_numeric_setting(group_id, "warning_limit", 3)

        # Simulate bot restart by calling init_db again
        database.init_db(TEST_DB_PATH)

        persisted = database.get_group_settings(group_id)
        self.assertFalse(persisted["anti_link_enabled"])
        self.assertFalse(persisted["warning_system_enabled"])
        self.assertEqual(persisted["spam_window_seconds"], 45)
        self.assertEqual(persisted["warning_limit"], 3)

    # -------------------------------------------------------------------------
    # SCENARIO 14: Simultaneous Activity in Multiple Groups (Concurrency)
    # -------------------------------------------------------------------------
    async def test_scenario_14_concurrency_no_crosstalk(self):
        num_groups = 5
        groups = [-100900 - i for i in range(num_groups)]

        # Concurrently register all groups
        async def register(gid, i):
            ctx = MagicMock()
            ctx.bot.send_message = AsyncMock()
            upd = self.create_my_chat_member_update(gid, f"Concurrent Group {i}", ChatType.SUPERGROUP, ChatMemberStatus.LEFT, ChatMemberStatus.MEMBER)
            await handle_my_chat_member(upd, ctx)

        await asyncio.gather(*(register(g, idx) for idx, g in enumerate(groups)))

        # Concurrently toggle settings in alternating groups
        async def configure(gid, idx):
            enable_link = (idx % 2 == 0)
            database.update_group_feature(gid, "anti_link_enabled", enable_link)

        await asyncio.gather(*(configure(g, idx) for idx, g in enumerate(groups)))

        # Verify no cross-talk in settings
        for idx, gid in enumerate(groups):
            s = database.get_group_settings(gid)
            expected_link = (idx % 2 == 0)
            self.assertEqual(s["anti_link_enabled"], expected_link, f"Mismatch in group {gid}")

    # -------------------------------------------------------------------------
    # Extra: Test /enable and /disable commands with authorization check
    # -------------------------------------------------------------------------
    async def test_enable_and_disable_commands(self):
        gid = -100999
        # 1. Regular member attempts /enable antilink -> Rejected
        upd_reg, ctx_reg = self.create_message_update(gid, "Group Test", ChatType.SUPERGROUP, user_id=991, text="/enable antilink", is_admin=False, update_id=90)
        ctx_reg.args = ["antilink"]
        await enable_command(upd_reg, ctx_reg)
        upd_reg.effective_message.reply_text.assert_awaited_once_with("You need administrator privileges to use this command.")

        # 2. Administrator executes /disable antilink -> Success
        upd_adm, ctx_adm = self.create_message_update(gid, "Group Test", ChatType.SUPERGROUP, user_id=992, text="/disable antilink", is_admin=True, update_id=91)
        ctx_adm.args = ["antilink"]
        await disable_command(upd_adm, ctx_adm)
        self.assertFalse(database.get_group_settings(gid)["anti_link_enabled"])

        # 3. Administrator executes /enable antilink -> Success
        upd_adm2, ctx_adm2 = self.create_message_update(gid, "Group Test", ChatType.SUPERGROUP, user_id=992, text="/enable antilink", is_admin=True, update_id=92)
        ctx_adm2.args = ["antilink"]
        await enable_command(upd_adm2, ctx_adm2)
        self.assertTrue(database.get_group_settings(gid)["anti_link_enabled"])


if __name__ == "__main__":
    unittest.main()

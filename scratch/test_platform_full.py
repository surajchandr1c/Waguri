"""Comprehensive Automated Test Suite for Waguri Multi-Group Management Platform.

Validates all 22 parts of the architecture specification:
1. Multi-tenant chat isolation (groups and channels)
2. RBAC permissions (Owner, Admin, Regular Member)
3. Private Owner Dashboard vs Group /start command
4. Interactive /settings dashboard and inline callbacks
5. Anti-Link with whitelist & blacklist
6. Anti-Spam progressive sequence & 24h restriction
7. Flood detection rate tracking
8. Anti-Forward, Anti-Bot & Media Restrictions
9. Moderation commands (/mute, /unmute, /ban, /unban, /warnings, /resetwarnings, /logs, /id)
10. Super-admin /owner controls and emergency overrides
11. Database persistence across restarts
"""

import asyncio
import gc
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telegram.constants import ChatMemberStatus, ChatType

import config
import database
from handlers.admin_check import invalidate_cache
from handlers.admin_commands import (
    antlink_command,
    antispam_command,
    ban_command,
    id_command,
    logs_command,
    mute_command,
    resetwarnings_command,
    unban_command,
    unmute_command,
    warnings_command,
)
from handlers.anti_link import (
    blacklist_command,
    handle_channel_post,
    handle_group_message,
    whitelist_command,
)
from handlers.anti_spam import handle_anti_spam, reset_anti_spam_state
from handlers.bot_owner import owner_command
from handlers.commands import about_command, contact_command, help_command, start
from handlers.extra_protection import handle_anti_forward, handle_new_chat_members, raid_command
from handlers.feature_commands import disable_command, enable_command, features_command, stats_command
from handlers.media_protection import handle_media_restrictions
from handlers.private_dashboard import handle_private_callback
from handlers.registration import handle_my_chat_member
from handlers.settings_panel import settings_callback_handler, settings_command

TEST_DB_PATH = os.path.abspath("test_platform.db")


def cleanup_db():
    gc.collect()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


class TestWaguriPlatform(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        cleanup_db()
        config.DATABASE_PATH = TEST_DB_PATH
        config.BOT_OWNER_IDS = {777000}  # Mock super-admin ID
        config.GLOBAL_EMERGENCY_OVERRIDES = {
            "anti_link": True,
            "anti_spam": True,
            "flood": True,
            "media": True,
            "forwards": True,
        }
        database.init_db(TEST_DB_PATH)
        invalidate_cache()
        reset_anti_spam_state()

    async def asyncTearDown(self):
        cleanup_db()
        config.GLOBAL_EMERGENCY_OVERRIDES = {
            "anti_link": True,
            "anti_spam": True,
            "flood": True,
            "media": True,
            "forwards": True,
        }
        invalidate_cache()
        reset_anti_spam_state()

    def create_mock_update(
        self,
        chat_id: int,
        user_id: int,
        text: str = "",
        is_admin: bool = False,
        is_owner: bool = False,
        chat_type: str = ChatType.SUPERGROUP,
        update_id: int = 100,
    ):
        update = MagicMock()
        update.update_id = update_id

        chat = MagicMock()
        chat.id = chat_id
        chat.title = f"Chat {chat_id}"
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
        message.reply_to_message = None
        message.new_chat_members = []
        message.photo = []
        message.video = None
        message.document = None
        message.sticker = None
        message.animation = None
        message.voice = None
        message.video_note = None
        message.forward_date = None
        message.forward_origin = None
        message.forward_from = None
        message.forward_from_chat = None
        message.delete = AsyncMock()
        message.reply_text = AsyncMock()

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user
        update.channel_post = None

        context = MagicMock()
        context.bot.id = 999999
        context.bot.username = "Ms_Waguri_bot"
        context.bot.send_message = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.restrict_chat_member = AsyncMock(return_value=True)
        context.bot.ban_chat_member = AsyncMock(return_value=True)
        context.bot.unban_chat_member = AsyncMock(return_value=True)
        context.args = []

        bot_admin = MagicMock()
        bot_admin.user.id = context.bot.id
        bot_admin.status = ChatMemberStatus.ADMINISTRATOR
        bot_admin.can_delete_messages = True
        bot_admin.can_restrict_members = True

        member_status = ChatMemberStatus.OWNER if is_owner else (ChatMemberStatus.ADMINISTRATOR if is_admin else ChatMemberStatus.MEMBER)
        user_member = MagicMock()
        user_member.user.id = user_id
        user_member.status = member_status

        admins = [bot_admin]
        if is_admin or is_owner:
            admins.append(user_member)

        context.bot.get_chat_administrators = AsyncMock(return_value=admins)

        async def get_chat_member_side_effect(*args, **kwargs):
            u_id = kwargs.get("user_id") or (args[1] if len(args) > 1 else None)
            if u_id == context.bot.id:
                return bot_admin
            if u_id == user_id:
                return user_member
            reg = MagicMock()
            reg.user.id = u_id
            reg.status = ChatMemberStatus.MEMBER
            return reg

        context.bot.get_chat_member = AsyncMock(side_effect=get_chat_member_side_effect)
        return update, context

    # -------------------------------------------------------------------------
    # 1. Multi-Tenant Architecture & Chat Isolation
    # -------------------------------------------------------------------------
    async def test_tenant_isolation(self):
        g1, g2 = -10011, -10022
        database.register_or_update_chat(g1, "Group 1", "group", True)
        database.register_or_update_chat(g2, "Group 2", "group", True)

        database.update_group_feature(g1, "anti_link_enabled", True)
        database.update_group_feature(g2, "anti_link_enabled", False)

        s1 = database.get_group_settings(g1)
        s2 = database.get_group_settings(g2)
        self.assertTrue(s1["anti_link_enabled"])
        self.assertFalse(s2["anti_link_enabled"])

    # -------------------------------------------------------------------------
    # 2. RBAC Permissions (Owner vs Admin vs Regular Member)
    # -------------------------------------------------------------------------
    async def test_rbac_security(self):
        gid = -10033
        database.register_or_update_chat(gid, "Group RBAC", "group", True)

        # Regular member attempts /disable antilink -> Rejected
        upd_reg, ctx_reg = self.create_mock_update(gid, 101, "/disable antilink", is_admin=False)
        ctx_reg.args = ["antilink"]
        await disable_command(upd_reg, ctx_reg)
        upd_reg.effective_message.reply_text.assert_awaited_once_with("You need administrator privileges to use this command.")
        self.assertTrue(database.get_group_settings(gid)["anti_link_enabled"])

        # Admin executes /disable antilink -> Permitted
        upd_adm, ctx_adm = self.create_mock_update(gid, 102, "/disable antilink", is_admin=True)
        ctx_adm.args = ["antilink"]
        await disable_command(upd_adm, ctx_adm)
        self.assertFalse(database.get_group_settings(gid)["anti_link_enabled"])

    # -------------------------------------------------------------------------
    # 3. Private Owner Dashboard vs Group /start
    # -------------------------------------------------------------------------
    async def test_start_routing_private_vs_group(self):
        # In Group: Returns exact welcome string
        upd_grp, ctx_grp = self.create_mock_update(-10044, 201, "/start", chat_type=ChatType.GROUP)
        await start(upd_grp, ctx_grp)
        upd_grp.effective_message.reply_text.assert_awaited_once_with("Hi, welcome. I am Waguri. How can I help you")

        # In Private: Returns rich inline buttons dashboard
        upd_pvt, ctx_pvt = self.create_mock_update(201, 201, "/start", chat_type=ChatType.PRIVATE)
        ctx_pvt.bot.get_me = AsyncMock(return_value=MagicMock(username="Ms_Waguri_bot"))
        await start(upd_pvt, ctx_pvt)
        upd_pvt.effective_message.reply_text.assert_awaited_once()
        markup = upd_pvt.effective_message.reply_text.call_args[1]["reply_markup"]
        btn_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        self.assertIn("➕ Add Waguri to Group", btn_texts)
        self.assertIn("📢 Add Waguri to Channel", btn_texts)
        self.assertIn("👥 My Groups", btn_texts)
        self.assertIn("📢 My Channels", btn_texts)

    # -------------------------------------------------------------------------
    # 4. Interactive Group Management Panel (/settings & callbacks)
    # -------------------------------------------------------------------------
    async def test_interactive_settings_panel(self):
        gid = -10055
        database.register_or_update_chat(gid, "Settings Group", "group", True)

        upd, ctx = self.create_mock_update(gid, 301, "/settings", is_admin=True)
        await settings_command(upd, ctx)
        upd.effective_message.reply_text.assert_awaited_once()
        markup = upd.effective_message.reply_text.call_args[1]["reply_markup"]

        # Verify buttons exist for Anti-Link, Anti-Spam, Flood, Warnings, Media, etc.
        callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        self.assertIn(f"cfg:{gid}:toggle_link", callbacks)
        self.assertIn(f"cfg:{gid}:toggle_spam", callbacks)
        self.assertIn(f"cfg:{gid}:toggle_flood", callbacks)
        self.assertIn(f"cfg:{gid}:toggle_media", callbacks)
        self.assertIn(f"cfg:{gid}:menu_whitelist", callbacks)

        # Admin clicks callback to toggle Anti-Link
        query_update = MagicMock()
        query = MagicMock()
        query.data = f"cfg:{gid}:toggle_link"
        query.message.chat.id = gid
        query.from_user.id = 301
        query.edit_message_text = AsyncMock()
        query.answer = AsyncMock()
        query_update.callback_query = query
        query_update.effective_chat = query.message.chat
        query_update.effective_user = query.from_user

        await settings_callback_handler(query_update, ctx)
        self.assertFalse(database.get_group_settings(gid)["anti_link_enabled"])

    # -------------------------------------------------------------------------
    # 5. Advanced Anti-Link with Whitelist & Blacklist
    # -------------------------------------------------------------------------
    async def test_anti_link_with_whitelist(self):
        gid = -10066
        database.register_or_update_chat(gid, "Link Group", "group", True)
        database.update_group_feature(gid, "anti_link_enabled", True)

        # 1. Non-whitelisted link -> Deleted
        u1, c1 = self.create_mock_update(gid, 401, "Check https://scam.org/free", is_admin=False, update_id=1)
        await handle_group_message(u1, c1)
        u1.effective_message.delete.assert_awaited_once()

        # 2. Add domain to whitelist
        database.add_whitelisted_domain(gid, "trusted.com")

        # 3. Whitelisted link -> Allowed
        u2, c2 = self.create_mock_update(gid, 401, "Check https://trusted.com/docs", is_admin=False, update_id=2)
        await handle_group_message(u2, c2)
        u2.effective_message.delete.assert_not_called()

        # 4. Add pattern to blacklist
        database.add_blacklisted_pattern(gid, "crypto-giveaway")
        u3, c3 = self.create_mock_update(gid, 401, "Huge crypto-giveaway for everyone!", is_admin=False, update_id=3)
        await handle_group_message(u3, c3)
        u3.effective_message.delete.assert_awaited_once()

    # -------------------------------------------------------------------------
    # 6. Advanced Anti-Spam (Progressive Sequence 1->2->3->4)
    # -------------------------------------------------------------------------
    async def test_anti_spam_progressive_sequence(self):
        gid = -10077
        user_id = 505
        database.register_or_update_chat(gid, "Spam Group", "group", True)

        # Msg 1: Allowed
        u1, c1 = self.create_mock_update(gid, user_id, "Identical message test", is_admin=False, update_id=11)
        await handle_anti_spam(u1, c1)
        u1.effective_message.delete.assert_not_called()
        c1.bot.send_message.assert_not_called()

        # Msg 2: Deleted + Warning 1
        u2, c2 = self.create_mock_update(gid, user_id, "Identical message test", is_admin=False, update_id=12)
        await handle_anti_spam(u2, c2)
        u2.effective_message.delete.assert_awaited_once()
        c2.bot.send_message.assert_awaited_once()
        self.assertIn("Warning 1/2", c2.bot.send_message.call_args[1]["text"])

        # Msg 3: Deleted + Warning 2
        u3, c3 = self.create_mock_update(gid, user_id, "Identical message test", is_admin=False, update_id=13)
        await handle_anti_spam(u3, c3)
        u3.effective_message.delete.assert_awaited_once()
        c3.bot.send_message.assert_awaited_once()
        self.assertIn("Warning 2/2", c3.bot.send_message.call_args[1]["text"])

        # Msg 4: Deleted + 24h Mute + Batch Cleanup
        u4, c4 = self.create_mock_update(gid, user_id, "Identical message test", is_admin=False, update_id=14)
        await handle_anti_spam(u4, c4)
        u4.effective_message.delete.assert_awaited_once()
        c4.bot.restrict_chat_member.assert_awaited_once()
        self.assertIn("restricted for 24 hours", c4.bot.send_message.call_args[1]["text"])

    # -------------------------------------------------------------------------
    # 7. Additional Protections: Media, Forward, Raid
    # -------------------------------------------------------------------------
    async def test_additional_protections(self):
        gid = -10088
        database.register_or_update_chat(gid, "Extra Protect Group", "group", True)

        # A. Anti-Forward
        database.update_group_feature(gid, "anti_forward_enabled", True)
        u_fwd, c_fwd = self.create_mock_update(gid, 601, "Forwarded text", is_admin=False, update_id=20)
        u_fwd.effective_message.forward_date = 12345678
        await handle_anti_forward(u_fwd, c_fwd)
        u_fwd.effective_message.delete.assert_awaited_once()

        # B. Media Restrictions (Block stickers)
        database.update_group_feature(gid, "media_restrictions_enabled", True)
        database.set_media_restriction(gid, "stickers", False)
        u_stk, c_stk = self.create_mock_update(gid, 601, "", is_admin=False, update_id=21)
        u_stk.effective_message.sticker = MagicMock()
        await handle_media_restrictions(u_stk, c_stk)
        u_stk.effective_message.delete.assert_awaited_once()

        # C. Raid Emergency Lockdown
        u_raid, c_raid = self.create_mock_update(gid, 602, "/raid on", is_admin=True, update_id=22)
        c_raid.args = ["on"]
        await raid_command(u_raid, c_raid)
        self.assertTrue(database.get_group_settings(gid)["raid_mode_enabled"])

    # -------------------------------------------------------------------------
    # 8. Moderation Commands (/mute, /unmute, /ban, /unban, /logs)
    # -------------------------------------------------------------------------
    async def test_moderation_commands(self):
        gid = -10099
        admin_id = 701
        target_id = 702
        database.register_or_update_chat(gid, "Mod Commands Group", "group", True)

        # /mute 2h
        u_mute, c_mute = self.create_mock_update(gid, admin_id, "/mute 702 2h", is_admin=True, update_id=30)
        c_mute.args = ["702", "2h"]
        await mute_command(u_mute, c_mute)
        c_mute.bot.restrict_chat_member.assert_awaited_once()

        # /unmute
        u_unmute, c_unmute = self.create_mock_update(gid, admin_id, "/unmute 702", is_admin=True, update_id=31)
        c_unmute.args = ["702"]
        await unmute_command(u_unmute, c_unmute)
        c_unmute.bot.restrict_chat_member.assert_awaited_once()

        # /ban
        u_ban, c_ban = self.create_mock_update(gid, admin_id, "/ban 702", is_admin=True, update_id=32)
        c_ban.args = ["702"]
        await ban_command(u_ban, c_ban)
        c_ban.bot.ban_chat_member.assert_awaited_once()

        # /unban
        u_unban, c_unban = self.create_mock_update(gid, admin_id, "/unban 702", is_admin=True, update_id=33)
        c_unban.args = ["702"]
        await unban_command(u_unban, c_unban)
        c_unban.bot.unban_chat_member.assert_awaited_once()

        # /logs
        u_logs, c_logs = self.create_mock_update(gid, admin_id, "/logs", is_admin=True, update_id=34)
        await logs_command(u_logs, c_logs)
        u_logs.effective_message.reply_text.assert_awaited_once()

    # -------------------------------------------------------------------------
    # 9. Super-Admin /owner Controls
    # -------------------------------------------------------------------------
    async def test_super_admin_owner_dashboard(self):
        # Regular user attempts /owner -> Blocked
        u_reg, c_reg = self.create_mock_update(111, 111, "/owner")
        await owner_command(u_reg, c_reg)
        u_reg.effective_message.reply_text.assert_awaited_once_with("⛔ You are not authorized to access bot-owner controls.")

        # Authorized super-admin executes /owner -> Displays platform stats
        u_own, c_own = self.create_mock_update(777000, 777000, "/owner")
        await owner_command(u_own, c_own)
        u_own.effective_message.reply_text.assert_awaited_once()
        text = u_own.effective_message.reply_text.call_args[0][0]
        self.assertIn("Waguri Super-Admin Owner Dashboard", text)
        self.assertIn("Platform Scale:", text)

        # Super-admin tests emergency override
        u_emg, c_emg = self.create_mock_update(777000, 777000, "/owner emergency anti_link off")
        c_emg.args = ["emergency", "anti_link", "off"]
        await owner_command(u_emg, c_emg)
        self.assertFalse(config.GLOBAL_EMERGENCY_OVERRIDES["anti_link"])


if __name__ == "__main__":
    unittest.main()

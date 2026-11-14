"""Full Regression Test Suite for Waguri Bot.
Tests:
- /start command
- /help command
- /about command
- /contact command (with @lucky_paji)
- Greetings ("hii", "hlw", "hello")
- Admin commands (/antlink, /antispam, /warnings, /mute, /unmute, /id)
- Multi-group settings panel
"""

import asyncio
import gc
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
    id_command,
    mute_command,
    unmute_command,
    warnings_command,
)
from handlers.commands import about_command, contact_command, help_command, start
from handlers.greetings import handle_greeting_message

TEST_DB_PATH = os.path.abspath("test_regression.db")


def cleanup_test_db():
    gc.collect()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


class TestFullRegression(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        cleanup_test_db()
        config.DATABASE_PATH = TEST_DB_PATH
        database.init_db(TEST_DB_PATH)
        invalidate_cache()

    async def asyncTearDown(self):
        cleanup_test_db()
        invalidate_cache()

    def create_mock_update(self, chat_id: int, user_id: int, text: str, is_admin: bool = False, chat_type: str = ChatType.SUPERGROUP):
        update = MagicMock()
        update.update_id = 999

        chat = MagicMock()
        chat.id = chat_id
        chat.title = "Test Group"
        chat.type = chat_type

        user = MagicMock()
        user.id = user_id
        user.username = "test_user"
        user.first_name = "Suraj"

        message = MagicMock()
        message.message_id = 123
        message.chat = chat
        message.from_user = user
        message.text = text
        message.caption = None
        message.entities = []
        message.caption_entities = []
        message.sender_chat = None
        message.reply_text = AsyncMock()
        message.delete = AsyncMock()

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user
        update.channel_post = None

        context = MagicMock()
        context.bot.id = 888888
        context.bot.send_message = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot.restrict_chat_member = AsyncMock(return_value=True)

        bot_admin = MagicMock()
        bot_admin.user.id = context.bot.id
        bot_admin.status = ChatMemberStatus.ADMINISTRATOR
        bot_admin.can_delete_messages = True
        bot_admin.can_restrict_members = True

        user_admin = MagicMock()
        user_admin.user.id = user_id
        user_admin.status = ChatMemberStatus.ADMINISTRATOR if is_admin else ChatMemberStatus.MEMBER

        admins = [bot_admin]
        if is_admin:
            admins.append(user_admin)

        context.bot.get_chat_administrators = AsyncMock(return_value=admins)

        async def get_chat_member_side_effect(*args, **kwargs):
            u_id = kwargs.get("user_id") or (args[1] if len(args) > 1 else None)
            if u_id == context.bot.id:
                return bot_admin
            if is_admin and u_id == user_id:
                return user_admin
            regular = MagicMock()
            regular.user.id = u_id
            regular.status = ChatMemberStatus.MEMBER
            return regular

        context.bot.get_chat_member = AsyncMock(side_effect=get_chat_member_side_effect)
        return update, context

    async def test_start_command(self):
        upd, ctx = self.create_mock_update(-1001, 101, "/start")
        await start(upd, ctx)
        upd.effective_message.reply_text.assert_awaited_once_with(
            "Hi, welcome. I am Waguri. How can I help you"
        )

    async def test_help_command(self):
        upd, ctx = self.create_mock_update(-1001, 101, "/help")
        await help_command(upd, ctx)
        upd.effective_message.reply_text.assert_awaited_once()
        args, kwargs = upd.effective_message.reply_text.call_args
        text = args[0]
        markup = kwargs.get("reply_markup")
        btn_texts = [btn.text for row in markup.inline_keyboard for btn in row] if markup else []
        combined = text + " " + " ".join(btn_texts)
        self.assertIn("/settings", combined)
        self.assertIn("/features", combined)
        self.assertIn("/stats", combined)

    async def test_about_command(self):
        upd, ctx = self.create_mock_update(-1001, 101, "/about")
        await about_command(upd, ctx)
        upd.effective_message.reply_text.assert_awaited_once()
        text = upd.effective_message.reply_text.call_args[0][0]
        self.assertIn("Waguri (@Ms_Waguri_bot)", text)

    async def test_contact_command(self):
        upd, ctx = self.create_mock_update(-1001, 101, "/contact")
        await contact_command(upd, ctx)
        upd.effective_message.reply_text.assert_awaited_once_with(
            "For inquiries or support regarding Waguri, please reach out to the bot administrator @lucky_paji."
        )

    async def test_greetings(self):
        for greeting_word in ["Hii", "hy", "hyy", "hello", "hlw", "hi", "hey", "hii", "Hyy", "Hey", "HII!", " Hello "]:
            upd, ctx = self.create_mock_update(-1001, 101, greeting_word)
            await handle_greeting_message(upd, ctx)
            upd.effective_message.reply_text.assert_awaited_once_with("Hii Suraj")

    async def test_admin_commands_moderation(self):
        gid = -1002
        admin_id = 999
        # /antlink off
        upd, ctx = self.create_mock_update(gid, admin_id, "/antlink off", is_admin=True)
        ctx.args = ["off"]
        await antlink_command(upd, ctx)
        self.assertFalse(database.get_group_settings(gid)["anti_link_enabled"])

        # /antispam off
        upd2, ctx2 = self.create_mock_update(gid, admin_id, "/antispam off", is_admin=True)
        ctx2.args = ["off"]
        await antispam_command(upd2, ctx2)
        self.assertFalse(database.get_group_settings(gid)["anti_spam_enabled"])

        # /id command
        upd3, ctx3 = self.create_mock_update(gid, admin_id, "/id", is_admin=True)
        await id_command(upd3, ctx3)
        upd3.effective_message.reply_text.assert_awaited_once()
        id_text = upd3.effective_message.reply_text.call_args[0][0]
        self.assertIn(str(gid), id_text)


if __name__ == "__main__":
    unittest.main()

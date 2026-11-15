import asyncio
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["BOT_TOKEN"] = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567"
os.environ["BOT_OWNER_IDS"] = "111111,222222"
os.environ["DATABASE_PATH"] = "scratch/test_help.db"

import config
config.BOT_TOKEN = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567"
config.BOT_OWNER_IDS = [111111, 222222]
config.DATABASE_PATH = "scratch/test_help.db"

from telegram import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import Application, ContextTypes

from database import (
    init_db,
    save_or_update_business_connection,
    update_personal_reply_settings,
)
from handlers.commands import help_command
from handlers.help_menu import (
    HELP_COMMANDS_TEXT,
    build_main_help_markup,
    help_callback_handler,
    interactive_help_command,
)
from handlers.private_dashboard import handle_private_callback


class TestHelpMenuClean(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        config.DATABASE_PATH = os.path.abspath("scratch/test_help.db")
        if os.path.exists(config.DATABASE_PATH):
            try:
                os.remove(config.DATABASE_PATH)
            except Exception:
                pass
        init_db()

        self.chat_id = -10099998888
        self.admin_user_id = 111111
        self.bot_user_id = 999999

        self.bot = AsyncMock()
        self.bot.id = self.bot_user_id
        self.bot.username = "Ms_Waguri_bot"

        async def mock_get_chat_member(chat_id, user_id):
            m = MagicMock()
            m.user = MagicMock(id=user_id, username=f"user_{user_id}", first_name=f"User {user_id}")
            if user_id == self.admin_user_id:
                m.status = ChatMemberStatus.OWNER
            elif user_id == self.bot_user_id:
                m.status = ChatMemberStatus.ADMINISTRATOR
                m.can_delete_messages = True
                m.can_restrict_members = True
            else:
                m.status = ChatMemberStatus.MEMBER
            return m

        self.bot.get_chat_member = mock_get_chat_member

    async def asyncTearDown(self):
        if hasattr(config, "DATABASE_PATH") and os.path.exists(config.DATABASE_PATH):
            try:
                os.remove(config.DATABASE_PATH)
            except Exception:
                pass

    async def test_help_command_renders_all_sections_without_buttons(self):
        """Verify /help sends complete command reference directly in chat with no inline buttons."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message)
        chat = MagicMock(spec=Chat)
        chat.id = self.chat_id
        chat.type = ChatType.SUPERGROUP
        user = MagicMock(spec=User)
        user.id = self.admin_user_id

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user

        context = MagicMock()
        context.bot = self.bot

        await help_command(update, context)

        message.reply_text.assert_called_once()
        args, kwargs = message.reply_text.call_args
        text = args[0]

        # Verify header and all required sections exist
        self.assertIn("Waguri Bot Commands & Help", text)
        self.assertIn("General Commands:", text)
        self.assertIn("Group Management Commands:", text)
        self.assertIn("Moderation & Penalties:", text)
        self.assertIn("Personal Auto-Reply", text)
        self.assertIn("Supported Placeholders:", text)
        self.assertIn("Advanced Features:", text)

        # Verify key commands are documented
        self.assertIn("/start", text)
        self.assertIn("/help", text)
        self.assertIn("/about", text)
        self.assertIn("/contact", text)
        self.assertIn("/settings", text)
        self.assertIn("/features", text)
        self.assertIn("/antlink", text)
        self.assertIn("/antispam", text)
        self.assertIn("/personal", text)
        self.assertIn("/autoreply_on", text)
        self.assertIn("/autoreply_off", text)
        self.assertIn("/setmessage", text)
        self.assertIn("/preview", text)
        self.assertIn("/mystatus", text)
        self.assertIn("/resetmessage", text)
        self.assertIn("/exclude_user", text)
        self.assertIn("/include_user", text)
        self.assertIn("/business_stats", text)

        # Verify NO inline keyboard buttons attached to /help in chat
        self.assertNotIn("reply_markup", kwargs)

    async def test_navigation_and_close(self):
        """Test returning to main menu and closing help menu."""
        update = MagicMock(spec=Update)
        query = AsyncMock(spec=CallbackQuery)
        msg = AsyncMock(spec=Message)
        msg.chat = MagicMock(id=self.chat_id, type=ChatType.SUPERGROUP)
        query.message = msg
        update.callback_query = query
        update.effective_chat = msg.chat
        update.effective_user = MagicMock(id=self.admin_user_id)

        context = MagicMock()
        context.bot = self.bot

        # Return to main menu
        query.data = f"cmd:{self.chat_id}:main"
        await help_callback_handler(update, context)
        self.assertIn("Waguri Bot Commands & Help", query.edit_message_text.call_args[0][0])

        # Close
        query.data = f"cmd:{self.chat_id}:close"
        await help_callback_handler(update, context)
        msg.delete.assert_called_once()

    async def test_private_dashboard_help_navigation(self):
        """In private dashboard, clicking Help opens full menu with back button."""
        update = MagicMock(spec=Update)
        query = AsyncMock(spec=CallbackQuery)
        query.data = "pvt:help"
        update.callback_query = query
        update.effective_user = MagicMock(id=12345, full_name="Private User")

        context = MagicMock()
        context.bot = self.bot

        await handle_private_callback(update, context)

        query.edit_message_text.assert_called_once()
        args, kwargs = query.edit_message_text.call_args
        self.assertIn("Waguri Bot Commands & Help", args[0])
        self.assertIn("General Commands:", args[0])
        self.assertIn("Personal Auto-Reply", args[0])
        # In private chat, bottom button is Back to Main Menu
        btn_texts = [btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row]
        self.assertTrue(any("Back to Main Menu" in t for t in btn_texts))


if __name__ == "__main__":
    unittest.main()

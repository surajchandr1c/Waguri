import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Configure test environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_PATH"] = "scratch/test_help.db"
os.environ["TELEGRAM_BOT_TOKEN"] = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ_12345678"

import config
config.DATABASE_PATH = "scratch/test_help.db"

from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.constants import ChatMemberStatus, ChatType
from database import (
    get_group_settings,
    get_whitelisted_domains,
    init_db,
    register_or_update_chat,
    set_group_anti_link,
)
from handlers.admin_check import invalidate_cache
from handlers.commands import help_command
from handlers.help_menu import (
    build_command_options_markup,
    build_main_help_markup,
    help_callback_handler,
    interactive_help_command,
)
from handlers.private_dashboard import handle_private_callback


class TestHelpMenuInteractive(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        config.DATABASE_PATH = os.path.abspath("scratch/test_help.db")
        if os.path.exists(config.DATABASE_PATH):
            try:
                os.remove(config.DATABASE_PATH)
            except Exception:
                pass
        init_db(config.DATABASE_PATH)
        invalidate_cache()

        self.chat_id = -10099998888
        self.admin_user_id = 111111
        self.member_user_id = 222222

        register_or_update_chat(self.chat_id, "Interactive Help Group", "supergroup")

        self.bot = AsyncMock()
        self.bot.id = 999999

        # Mock get_chat_member
        async def mock_get_chat_member(chat_id, user_id):
            mock_member = MagicMock()
            if user_id == self.admin_user_id:
                mock_member.status = ChatMemberStatus.ADMINISTRATOR
            else:
                mock_member.status = ChatMemberStatus.MEMBER
            mock_member.user = MagicMock(id=user_id)
            return mock_member

        self.bot.get_chat_member.side_effect = mock_get_chat_member

        # Mock get_chat_administrators
        admin_member = MagicMock()
        admin_member.user = MagicMock(id=self.admin_user_id)
        admin_member.status = ChatMemberStatus.ADMINISTRATOR
        admin_member.can_delete_messages = True
        admin_member.can_restrict_members = True

        bot_member = MagicMock()
        bot_member.user = MagicMock(id=self.bot.id)
        bot_member.status = ChatMemberStatus.ADMINISTRATOR
        bot_member.can_delete_messages = True
        bot_member.can_restrict_members = True

        self.bot.get_chat_administrators.return_value = [admin_member, bot_member]

    async def asyncTearDown(self):
        invalidate_cache()
        if hasattr(config, "DATABASE_PATH") and os.path.exists(config.DATABASE_PATH):
            try:
                os.remove(config.DATABASE_PATH)
            except Exception:
                pass

    async def test_help_command_renders_buttons(self):
        """Verify /help sends interactive menu with direct and option buttons."""
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
        self.assertIn("Waguri Bot Commands & Help", args[0])
        self.assertIn("reply_markup", kwargs)
        markup = kwargs["reply_markup"]

        # Check for expected command buttons
        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        self.assertTrue(any("/about" in t for t in button_texts))
        self.assertTrue(any("/contact" in t for t in button_texts))
        self.assertTrue(any("/id" in t for t in button_texts))
        self.assertTrue(any("/antlink ▾" in t for t in button_texts))
        self.assertTrue(any("/antispam ▾" in t for t in button_texts))
        self.assertTrue(any("/enable ▾" in t for t in button_texts))
        self.assertTrue(any("/disable ▾" in t for t in button_texts))
        self.assertTrue(any("/whitelist ▾" in t for t in button_texts))
        self.assertTrue(any("/mute ▾" in t for t in button_texts))

    async def test_direct_command_execution_about_contact_id(self):
        """Clicking direct command executes immediately and updates message."""
        update = MagicMock(spec=Update)
        query = AsyncMock(spec=CallbackQuery)
        msg = AsyncMock(spec=Message)
        msg.chat = MagicMock(id=self.chat_id, type=ChatType.SUPERGROUP)
        query.message = msg
        update.callback_query = query
        update.effective_chat = msg.chat
        update.effective_user = MagicMock(id=self.member_user_id, full_name="Regular Member", username="regmember")

        context = MagicMock()
        context.bot = self.bot

        # 1. /about
        query.data = f"cmd:{self.chat_id}:run:about"
        await help_callback_handler(update, context)
        query.edit_message_text.assert_called()
        self.assertIn("About Waguri", query.edit_message_text.call_args[0][0])
        query.answer.assert_called_with("Executed /about")

        # 2. /contact
        query.data = f"cmd:{self.chat_id}:run:contact"
        await help_callback_handler(update, context)
        self.assertIn("@lucky_paji", query.edit_message_text.call_args[0][0])
        query.answer.assert_called_with("Executed /contact")

        # 3. /id
        query.data = f"cmd:{self.chat_id}:run:id"
        await help_callback_handler(update, context)
        self.assertIn(str(self.member_user_id), query.edit_message_text.call_args[0][0])
        query.answer.assert_called_with("Executed /id")

    async def test_options_command_opens_submenu(self):
        """Clicking options command (marked ▾) displays sub-options menu."""
        update = MagicMock(spec=Update)
        query = AsyncMock(spec=CallbackQuery)
        msg = AsyncMock(spec=Message)
        msg.chat = MagicMock(id=self.chat_id, type=ChatType.SUPERGROUP)
        query.message = msg
        update.callback_query = query
        update.effective_chat = msg.chat
        update.effective_user = MagicMock(id=self.admin_user_id, full_name="Admin")

        context = MagicMock()
        context.bot = self.bot

        # /antlink options
        query.data = f"cmd:{self.chat_id}:opt:antlink"
        await help_callback_handler(update, context)
        args, kwargs = query.edit_message_text.call_args
        self.assertIn("Command Options: /antlink", args[0])
        sub_buttons = [btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row]
        self.assertTrue(any("Enable" in b for b in sub_buttons))
        self.assertTrue(any("Disable" in b for b in sub_buttons))

        # /enable options
        query.data = f"cmd:{self.chat_id}:opt:enable"
        await help_callback_handler(update, context)
        args, kwargs = query.edit_message_text.call_args
        self.assertIn("Command Options: /enable", args[0])
        enable_buttons = [btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row]
        self.assertTrue(any("antilink" in b for b in enable_buttons))
        self.assertTrue(any("antispam" in b for b in enable_buttons))
        self.assertTrue(any("flood" in b for b in enable_buttons))

    async def test_option_selection_executes_and_confirms(self):
        """Selecting an option executes the command and confirms."""
        update = MagicMock(spec=Update)
        query = AsyncMock(spec=CallbackQuery)
        msg = AsyncMock(spec=Message)
        msg.chat = MagicMock(id=self.chat_id, type=ChatType.SUPERGROUP)
        query.message = msg
        update.callback_query = query
        update.effective_chat = msg.chat
        update.effective_user = MagicMock(id=self.admin_user_id, full_name="Admin")

        context = MagicMock()
        context.bot = self.bot

        # 1. Turn anti-link off
        query.data = f"cmd:{self.chat_id}:exec:antlink:off"
        await help_callback_handler(update, context)
        self.assertFalse(get_group_settings(self.chat_id)["anti_link_enabled"])
        self.assertIn("DISABLED", query.edit_message_text.call_args[0][0])

        # 2. Turn anti-link on
        query.data = f"cmd:{self.chat_id}:exec:antlink:on"
        await help_callback_handler(update, context)
        self.assertTrue(get_group_settings(self.chat_id)["anti_link_enabled"])
        self.assertIn("ENABLED", query.edit_message_text.call_args[0][0])

        # 3. Add domain to whitelist
        query.data = f"cmd:{self.chat_id}:exec:whitelist:add_google"
        await help_callback_handler(update, context)
        self.assertIn("google.com", get_whitelisted_domains(self.chat_id))

        # 4. View whitelist
        query.data = f"cmd:{self.chat_id}:exec:whitelist:list"
        await help_callback_handler(update, context)
        self.assertIn("google.com", query.edit_message_text.call_args[0][0])

    async def test_regular_member_rbac_rejection(self):
        """Regular members cannot open options or execute admin commands."""
        update = MagicMock(spec=Update)
        query = AsyncMock(spec=CallbackQuery)
        msg = AsyncMock(spec=Message)
        msg.chat = MagicMock(id=self.chat_id, type=ChatType.SUPERGROUP)
        query.message = msg
        update.callback_query = query
        update.effective_chat = msg.chat
        update.effective_user = MagicMock(id=self.member_user_id, full_name="Member")

        context = MagicMock()
        context.bot = self.bot

        # Try to open /antlink options as regular member
        query.data = f"cmd:{self.chat_id}:opt:antlink"
        await help_callback_handler(update, context)
        query.answer.assert_called_with("⛔ You need administrator privileges to view moderation options.", show_alert=True)

        # Try to execute /antlink off as regular member
        set_group_anti_link(self.chat_id, True)
        query.data = f"cmd:{self.chat_id}:exec:antlink:off"
        await help_callback_handler(update, context)
        query.answer.assert_called_with("⛔ You need administrator privileges to use this command.", show_alert=True)
        # Verify setting was not altered
        self.assertTrue(get_group_settings(self.chat_id)["anti_link_enabled"])

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
        """In private dashboard, clicking Help opens interactive menu."""
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
        # In private chat, bottom button is Back to Main Menu
        btn_texts = [btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row]
        self.assertTrue(any("Back to Main Menu" in t for t in btn_texts))


if __name__ == "__main__":
    unittest.main()

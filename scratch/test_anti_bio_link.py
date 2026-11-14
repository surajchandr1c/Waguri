import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["DATABASE_PATH"] = "scratch/test_bio.db"
os.environ["TELEGRAM_BOT_TOKEN"] = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ_12345678"

import config
config.DATABASE_PATH = "scratch/test_bio.db"

from telegram import Chat, Message, Update, User
from telegram.constants import ChatMemberStatus, ChatType
from database import (
    add_whitelisted_domain,
    get_connection,
    get_group_settings,
    get_group_stats,
    get_user_warnings_count,
    init_db,
    register_or_update_chat,
    set_group_anti_bio_link,
    update_group_numeric_setting,
)
from handlers.admin_check import invalidate_cache
from handlers.admin_commands import antibiolink_command, cleanservice_command
from handlers.extra_protection import handle_service_message
from handlers.feature_commands import features_command
from handlers.anti_link import (
    check_user_bio_link,
    handle_group_message,
    invalidate_bio_cache,
)


class TestAntiBioLink(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        config.DATABASE_PATH = os.path.abspath("scratch/test_bio.db")
        if os.path.exists(config.DATABASE_PATH):
            try:
                os.remove(config.DATABASE_PATH)
            except Exception:
                pass
        init_db(config.DATABASE_PATH)
        with get_connection(config.DATABASE_PATH) as conn:
            conn.execute("DELETE FROM chat_warnings")
            conn.execute("DELETE FROM user_restrictions")
            conn.execute("DELETE FROM chat_moderation_logs")
            conn.execute("DELETE FROM chat_statistics")
            conn.execute("DELETE FROM chat_settings")
            conn.execute("DELETE FROM chats")
            conn.commit()
        invalidate_cache()
        invalidate_bio_cache()

        self.chat_id = -10055554444
        self.admin_user_id = 111111
        self.spammer_user_id = 222222
        self.clean_user_id = 333333

        register_or_update_chat(self.chat_id, "Test Bio Group", "supergroup")

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

        # Mock bot permissions
        bot_member = MagicMock()
        bot_member.user = MagicMock(id=self.bot.id)
        bot_member.status = ChatMemberStatus.ADMINISTRATOR
        bot_member.can_delete_messages = True
        bot_member.can_restrict_members = True

        admin_member = MagicMock()
        admin_member.user = MagicMock(id=self.admin_user_id)
        admin_member.status = ChatMemberStatus.ADMINISTRATOR

        self.bot.get_chat_administrators.return_value = [admin_member, bot_member]

        # Mock get_chat for bio retrieval
        async def mock_get_chat(user_id):
            chat_full = MagicMock()
            if user_id == self.spammer_user_id:
                chat_full.bio = "Join my crypto signals channel: https://t.me/cryptospam"
            elif user_id == self.admin_user_id:
                chat_full.bio = "Official admin: https://t.me/admin"
            elif user_id == self.clean_user_id:
                chat_full.bio = "Hello, I am a regular developer."
            else:
                chat_full.bio = None
            return chat_full

        self.bot.get_chat.side_effect = mock_get_chat

    async def asyncTearDown(self):
        invalidate_cache()
        invalidate_bio_cache()
        if hasattr(config, "DATABASE_PATH") and os.path.exists(config.DATABASE_PATH):
            try:
                os.remove(config.DATABASE_PATH)
            except Exception:
                pass

    async def test_bio_link_detection_and_caching(self):
        """Verify check_user_bio_link correctly identifies links and caches results."""
        has_link, url = await check_user_bio_link(self.spammer_user_id, self.bot)
        self.assertTrue(has_link)
        self.assertIn("t.me/cryptospam", url)

        # Call again to test cache hit (get_chat called only once)
        has_link2, url2 = await check_user_bio_link(self.spammer_user_id, self.bot)
        self.assertTrue(has_link2)
        self.assertEqual(url, url2)
        self.assertEqual(self.bot.get_chat.call_count, 1)

        # Clean user test
        has_link_clean, _ = await check_user_bio_link(self.clean_user_id, self.bot)
        self.assertFalse(has_link_clean)

    async def test_spammer_with_bio_link_message_deleted_and_warned(self):
        """User with bio link sends innocent message -> message deleted + warning issued."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message)
        message.message_id = 1001
        message.text = "Hello everyone, how are you?"
        message.caption = None
        message.entities = []
        message.caption_entities = []
        message.sender_chat = None

        chat = MagicMock(spec=Chat)
        chat.id = self.chat_id
        chat.type = ChatType.SUPERGROUP
        chat.title = "Test Bio Group"

        user = MagicMock(spec=User)
        user.id = self.spammer_user_id
        user.first_name = "Spammer"
        user.username = "spammer99"
        user.is_bot = False

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user

        context = MagicMock()
        context.bot = self.bot

        await handle_group_message(update, context)

        # Message deleted
        message.delete.assert_awaited_once()

        # Warning issued in chat
        context.bot.send_message.assert_awaited_once()
        sent_warn_text = context.bot.send_message.call_args[1]["text"]
        self.assertIn("Bio Link Warning", sent_warn_text)
        self.assertIn("Spammer", sent_warn_text)

        # Warning recorded in database
        warn_count = get_user_warnings_count(self.chat_id, self.spammer_user_id)
        self.assertEqual(warn_count, 1)

        # Stats incremented
        stats = get_group_stats(self.chat_id)
        self.assertGreaterEqual(stats["links_deleted"], 1)
        self.assertGreaterEqual(stats["warnings_issued"], 1)

    async def test_clean_user_message_allowed(self):
        """User without bio link sends message -> kept intact, no warning."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message)
        message.message_id = 1002
        message.text = "Just talking about coding"
        message.caption = None
        message.entities = []
        message.caption_entities = []
        message.sender_chat = None

        chat = MagicMock(spec=Chat)
        chat.id = self.chat_id
        chat.type = ChatType.SUPERGROUP
        chat.title = "Test Bio Group"

        user = MagicMock(spec=User)
        user.id = self.clean_user_id
        user.first_name = "CleanUser"
        user.username = "clean"
        user.is_bot = False

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user

        context = MagicMock()
        context.bot = self.bot

        await handle_group_message(update, context)

        message.delete.assert_not_awaited()
        context.bot.send_message.assert_not_awaited()
        self.assertEqual(get_user_warnings_count(self.chat_id, self.clean_user_id), 0)

    async def test_admin_with_bio_link_is_exempt(self):
        """Admin with bio link sends message -> kept intact (exempt from moderation)."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message)
        message.message_id = 1003
        message.text = "Admin announcement"
        message.caption = None
        message.entities = []
        message.caption_entities = []
        message.sender_chat = None

        chat = MagicMock(spec=Chat)
        chat.id = self.chat_id
        chat.type = ChatType.SUPERGROUP
        chat.title = "Test Bio Group"

        user = MagicMock(spec=User)
        user.id = self.admin_user_id
        user.first_name = "Admin"
        user.username = "superadmin"
        user.is_bot = False

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user

        context = MagicMock()
        context.bot = self.bot

        await handle_group_message(update, context)

        message.delete.assert_not_awaited()
        context.bot.send_message.assert_not_awaited()

    async def test_antibiolink_command_toggle(self):
        """Admin can toggle /antibiolink on and off."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message)
        chat = MagicMock(spec=Chat, id=self.chat_id, type=ChatType.SUPERGROUP, title="Test Group")
        user = MagicMock(spec=User, id=self.admin_user_id)

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user

        context = MagicMock()
        context.bot = self.bot

        # Turn off
        context.args = ["off"]
        await antibiolink_command(update, context)
        self.assertFalse(get_group_settings(self.chat_id)["anti_bio_link_enabled"])

        # Turn on
        context.args = ["on"]
        await antibiolink_command(update, context)
        self.assertTrue(get_group_settings(self.chat_id)["anti_bio_link_enabled"])

    async def test_bio_link_warning_limit_auto_restriction(self):
        """User with bio link reaches warning limit (default 2) and gets restricted."""
        # Set warning limit to 2
        update_group_numeric_setting(self.chat_id, "warning_limit", 2)
        from database import update_group_feature
        update_group_feature(self.chat_id, "auto_restrict_enabled", True)

        # Message 1
        up1 = MagicMock(spec=Update)
        msg1 = AsyncMock(spec=Message, message_id=2001, text="First msg", caption=None, entities=[], caption_entities=[], sender_chat=None)
        chat = MagicMock(spec=Chat, id=self.chat_id, type=ChatType.SUPERGROUP, title="Test Group")
        user = MagicMock(spec=User, id=self.spammer_user_id, first_name="Spammer", username="spammer99", is_bot=False)
        up1.effective_message, up1.effective_chat, up1.effective_user = msg1, chat, user

        ctx1 = MagicMock(bot=self.bot)
        await handle_group_message(up1, ctx1)
        self.assertEqual(get_user_warnings_count(self.chat_id, self.spammer_user_id), 1)

        # Message 2 -> Reaches limit of 2 warnings -> message deleted + auto restricted
        up2 = MagicMock(spec=Update)
        msg2 = AsyncMock(spec=Message, message_id=2002, text="Second msg", caption=None, entities=[], caption_entities=[], sender_chat=None)
        up2.effective_message, up2.effective_chat, up2.effective_user = msg2, chat, user

        ctx2 = MagicMock(bot=self.bot)
        await handle_group_message(up2, ctx2)

        msg2.delete.assert_awaited_once()
        self.assertEqual(get_user_warnings_count(self.chat_id, self.spammer_user_id), 2)

        # Verify restrict_chat_member was called
        self.bot.restrict_chat_member.assert_awaited()
        stats = get_group_stats(self.chat_id)
        self.assertGreaterEqual(stats["restrictions_applied"], 1)

    async def test_clean_service_message_deleted(self):
        """Service message (e.g. pinned message, topic change) is deleted when clean_service is enabled."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message, message_id=3001, new_chat_members=[])
        chat = MagicMock(spec=Chat, id=self.chat_id, type=ChatType.SUPERGROUP, title="Test Group")
        update.effective_message = message
        update.effective_chat = chat

        context = MagicMock(bot=self.bot)

        # Default clean_service_enabled is True
        await handle_service_message(update, context)
        message.delete.assert_awaited_once()

    async def test_clean_service_disabled_preserves_service_message(self):
        """When clean_service is disabled, service messages are not deleted."""
        from database import set_group_clean_service
        set_group_clean_service(self.chat_id, False)

        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message, message_id=3002, new_chat_members=[])
        chat = MagicMock(spec=Chat, id=self.chat_id, type=ChatType.SUPERGROUP, title="Test Group")
        update.effective_message = message
        update.effective_chat = chat

        context = MagicMock(bot=self.bot)

        await handle_service_message(update, context)
        message.delete.assert_not_awaited()

    async def test_cleanservice_command_toggle(self):
        """Admin can toggle /cleanservice on and off."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message)
        chat = MagicMock(spec=Chat, id=self.chat_id, type=ChatType.SUPERGROUP, title="Test Group")
        user = MagicMock(spec=User, id=self.admin_user_id)

        update.effective_message = message
        update.effective_chat = chat
        update.effective_user = user

        context = MagicMock(bot=self.bot)

        # Turn off
        context.args = ["off"]
        await cleanservice_command(update, context)
        self.assertFalse(get_group_settings(self.chat_id)["clean_service_enabled"])

        # Turn on
        context.args = ["on"]
        await cleanservice_command(update, context)
        self.assertTrue(get_group_settings(self.chat_id)["clean_service_enabled"])

    async def test_new_member_join_with_bio_link(self):
        """When a user with a bio link joins, their join message is deleted and warning is issued."""
        update = MagicMock(spec=Update)
        message = AsyncMock(spec=Message, message_id=4001)
        chat = MagicMock(spec=Chat, id=self.chat_id, type=ChatType.SUPERGROUP, title="Test Group")

        new_user = MagicMock(spec=User, id=self.spammer_user_id, first_name="Spammer", username="spammer99", is_bot=False)
        message.new_chat_members = [new_user]
        message.from_user = new_user

        update.effective_message = message
        update.effective_chat = chat

        context = MagicMock(bot=self.bot)

        await handle_service_message(update, context)

        # Message deleted
        message.delete.assert_awaited()
        # Warning recorded
        self.assertEqual(get_user_warnings_count(self.chat_id, self.spammer_user_id), 1)


if __name__ == "__main__":
    unittest.main()

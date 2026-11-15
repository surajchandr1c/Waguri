import asyncio
from datetime import datetime, timezone
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["DATABASE_PATH"] = "scratch/test_business_autoreply.db"
os.environ["TELEGRAM_BOT_TOKEN"] = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ_12345678"

import config
config.DATABASE_PATH = "scratch/test_business_autoreply.db"

from telegram import (
    BusinessBotRights,
    BusinessConnection,
    Chat,
    Message,
    Update,
    User,
)
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError

from database import (
    DEFAULT_PERSONAL_REPLY_TEMPLATE,
    add_excluded_user,
    check_and_claim_cooldown_reply,
    check_and_claim_first_contact,
    get_active_business_connection_for_user,
    get_business_connection,
    get_connection,
    get_daily_replies_count,
    get_excluded_users_list,
    get_global_business_stats,
    get_personal_reply_settings,
    get_personal_reply_template,
    get_user_business_connections,
    get_user_business_stats,
    has_replied_to_sender,
    init_db,
    is_user_excluded,
    remove_excluded_user,
    reset_personal_reply_template,
    save_or_update_business_connection,
    set_personal_reply_template,
    update_personal_reply_settings,
)
from handlers.personal_autoreply import (
    autoreply_off_command,
    autoreply_on_command,
    build_personal_settings_markup,
    exclude_user_command,
    handle_business_connection,
    handle_business_message,
    handle_deleted_business_messages,
    handle_edited_business_message,
    handle_private_reply_message_input,
    include_user_command,
    mystatus_command,
    personal_callback_handler,
    personal_command,
    preview_command,
    render_personal_template,
    resetmessage_command,
    setmessage_command,
)


class TestPersonalAutoReply(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = os.path.abspath("scratch/test_business_autoreply.db")
        config.DATABASE_PATH = self.db_path
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        init_db(self.db_path)

        # Pre-clean tables
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM business_reply_logs")
            conn.execute("DELETE FROM business_first_contacts")
            conn.execute("DELETE FROM personal_reply_templates")
            conn.execute("DELETE FROM personal_reply_settings")
            conn.execute("DELETE FROM business_connections")
            conn.commit()

        # Mock Bot & Application Context
        self.bot = AsyncMock()
        bot_user = User(id=999999999, first_name="Waguri", is_bot=True, username="Ms_Waguri_bot")
        self.bot.get_me = AsyncMock(return_value=bot_user)
        self.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))

        self.context = MagicMock()
        self.context.bot = self.bot
        self.context.user_data = {}
        self.context.args = []

    # =========================================================================
    # 1. Multi-User Connection & Independence Tests
    # =========================================================================

    async def test_multi_user_connection_independence(self):
        """Verify each user can connect their own Telegram Business account with independent settings."""
        user_a = User(id=1001, first_name="Alice", is_bot=False, username="alice_biz")
        user_b = User(id=2002, first_name="Bob", is_bot=False, username="bob_biz")

        # User A connects
        rights_a = BusinessBotRights(can_reply=True)
        bc_a = BusinessConnection(
            id="conn_alice_1",
            user=user_a,
            user_chat_id=1001,
            date=datetime.now(timezone.utc),
            is_enabled=True,
            rights=rights_a,
        )
        update_a = Update(update_id=1, business_connection=bc_a)
        await handle_business_connection(update_a, self.context)

        # User B connects
        rights_b = BusinessBotRights(can_reply=True)
        bc_b = BusinessConnection(
            id="conn_bob_2",
            user=user_b,
            user_chat_id=2002,
            date=datetime.now(timezone.utc),
            is_enabled=True,
            rights=rights_b,
        )
        update_b = Update(update_id=2, business_connection=bc_b)
        await handle_business_connection(update_b, self.context)

        # Verify DB records
        conn_a_db = get_business_connection("conn_alice_1", db_path=self.db_path)
        conn_b_db = get_business_connection("conn_bob_2", db_path=self.db_path)

        self.assertIsNotNone(conn_a_db)
        self.assertIsNotNone(conn_b_db)
        self.assertEqual(conn_a_db["user_id"], 1001)
        self.assertEqual(conn_b_db["user_id"], 2002)

        # Modify User A settings; ensure User B settings are untouched
        update_personal_reply_settings(1001, is_enabled=0, daily_limit=50, db_path=self.db_path)

        settings_a = get_personal_reply_settings(1001, db_path=self.db_path)
        settings_b = get_personal_reply_settings(2002, db_path=self.db_path)

        self.assertEqual(settings_a["is_enabled"], 0)
        self.assertEqual(settings_a["daily_limit"], 50)
        self.assertEqual(settings_b["is_enabled"], 1)  # Unaffected!
        self.assertEqual(settings_b["daily_limit"], 100)  # Unaffected!

    async def test_different_custom_messages_per_user(self):
        """Verify each user has their own custom message and never uses the bot owner's or another user's."""
        # Set custom message for User A
        set_personal_reply_template(1001, "Hello from Alice! I am currently consulting clients.", db_path=self.db_path)
        # Set custom message for User B
        set_personal_reply_template(2002, "Bob here. Please email me at bob@example.com", db_path=self.db_path)

        msg_a = get_personal_reply_template(1001, db_path=self.db_path)
        msg_b = get_personal_reply_template(2002, db_path=self.db_path)
        msg_c = get_personal_reply_template(3003, db_path=self.db_path)  # Unset user

        self.assertIn("Alice", msg_a)
        self.assertIn("Bob", msg_b)
        self.assertNotEqual(msg_a, msg_b)
        self.assertEqual(msg_c, DEFAULT_PERSONAL_REPLY_TEMPLATE)
        self.assertNotIn("Alice", msg_c)
        self.assertNotIn("Bob", msg_c)

    # =========================================================================
    # 2. First-Time Sender Detection & Repeat Sender Suppression
    # =========================================================================

    async def test_first_time_sender_detection_and_repeat_suppression(self):
        """
        Verify that:
        - When Person B messages User A for the first time, auto-reply is sent.
        - When Person B messages User A again, auto-reply is SUPPRESSED.
        - When Person C messages User A, auto-reply IS sent.
        """
        # Setup User A connection
        user_a = User(id=1001, first_name="Alice", is_bot=False)
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)
        set_personal_reply_template(1001, "Hi {first_name}! Alice is currently busy. Will reply soon.", db_path=self.db_path)

        # 1. Person B sends first message to User A
        person_b = User(id=5001, first_name="BobClient", is_bot=False, username="bobby")
        chat_b = Chat(id=5001, type=ChatType.PRIVATE)
        msg_1 = Message(
            message_id=101,
            date=datetime.now(timezone.utc),
            chat=chat_b,
            from_user=person_b,
            text="Hello Alice, do you have time?",
            business_connection_id="conn_a",
        )
        update_1 = Update(update_id=10, business_message=msg_1)

        await handle_business_message(update_1, self.context)

        # Verify reply was sent
        self.assertEqual(self.bot.send_message.call_count, 1)
        args, kwargs = self.bot.send_message.call_args
        self.assertEqual(kwargs["chat_id"], 5001)
        self.assertEqual(kwargs["business_connection_id"], "conn_a")
        self.assertIn("BobClient", kwargs["text"])

        # 2. Person B sends second message to User A
        msg_2 = Message(
            message_id=102,
            date=datetime.now(timezone.utc),
            chat=chat_b,
            from_user=person_b,
            text="Also, are you free tomorrow?",
            business_connection_id="conn_a",
        )
        update_2 = Update(update_id=11, business_message=msg_2)

        await handle_business_message(update_2, self.context)

        # Call count MUST remain 1! Repeat sender is suppressed!
        self.assertEqual(self.bot.send_message.call_count, 1)

        # 3. Person B sends third message to User A
        msg_3 = Message(
            message_id=103,
            date=datetime.now(timezone.utc),
            chat=chat_b,
            from_user=person_b,
            text="Never mind, just let me know.",
            business_connection_id="conn_a",
        )
        update_3 = Update(update_id=12, business_message=msg_3)

        await handle_business_message(update_3, self.context)

        # Still 1!
        self.assertEqual(self.bot.send_message.call_count, 1)

        # 4. Person C sends a message to User A -> Should receive auto-reply!
        person_c = User(id=6001, first_name="CharlieClient", is_bot=False, username="charlie")
        chat_c = Chat(id=6001, type=ChatType.PRIVATE)
        msg_c = Message(
            message_id=201,
            date=datetime.now(timezone.utc),
            chat=chat_c,
            from_user=person_c,
            text="Hi Alice, I need an invoice.",
            business_connection_id="conn_a",
        )
        update_c = Update(update_id=13, business_message=msg_c)

        await handle_business_message(update_c, self.context)

        # Call count increases to 2!
        self.assertEqual(self.bot.send_message.call_count, 2)
        _, kwargs_c = self.bot.send_message.call_args
        self.assertEqual(kwargs_c["chat_id"], 6001)
        self.assertIn("CharlieClient", kwargs_c["text"])

    async def test_two_users_receiving_messages_from_same_sender(self):
        """
        Verify isolation when Person X messages both User A and User B:
        - Person X -> User A: receives User A's custom reply.
        - Person X -> User B: receives User B's custom reply.
        """
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)
        save_or_update_business_connection("conn_b", 2002, 2002, True, True, db_path=self.db_path)

        set_personal_reply_template(1001, "Alice's Auto-Reply for {first_name}", db_path=self.db_path)
        set_personal_reply_template(2002, "Bob's Auto-Reply for {first_name}", db_path=self.db_path)

        person_x = User(id=7777, first_name="Xavier", is_bot=False)

        # Xavier messages User A
        msg_to_a = Message(
            message_id=301,
            date=datetime.now(timezone.utc),
            chat=Chat(id=7777, type=ChatType.PRIVATE),
            from_user=person_x,
            text="Hello Alice!",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=30, business_message=msg_to_a), self.context)

        self.assertEqual(self.bot.send_message.call_count, 1)
        _, kwargs_a = self.bot.send_message.call_args
        self.assertIn("Alice's Auto-Reply for Xavier", kwargs_a["text"])
        self.assertEqual(kwargs_a["business_connection_id"], "conn_a")

        # Xavier messages User B
        msg_to_b = Message(
            message_id=302,
            date=datetime.now(timezone.utc),
            chat=Chat(id=7777, type=ChatType.PRIVATE),
            from_user=person_x,
            text="Hello Bob!",
            business_connection_id="conn_b",
        )
        await handle_business_message(Update(update_id=31, business_message=msg_to_b), self.context)

        self.assertEqual(self.bot.send_message.call_count, 2)
        _, kwargs_b = self.bot.send_message.call_args
        self.assertIn("Bob's Auto-Reply for Xavier", kwargs_b["text"])
        self.assertEqual(kwargs_b["business_connection_id"], "conn_b")

    async def test_business_owner_and_bot_messages_ignored(self):
        """Verify messages sent by the business owner themselves or by other bots never trigger auto-reply."""
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)

        # 1. Business account owner types a message to client
        owner_msg = Message(
            message_id=401,
            date=datetime.now(timezone.utc),
            chat=Chat(id=5001, type=ChatType.PRIVATE),
            from_user=User(id=1001, first_name="Alice (Owner)", is_bot=False),
            text="Hey there, I am typing to you now.",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=40, business_message=owner_msg), self.context)

        # 2. A bot messages
        bot_msg = Message(
            message_id=402,
            date=datetime.now(timezone.utc),
            chat=Chat(id=5001, type=ChatType.PRIVATE),
            from_user=User(id=8888, first_name="SomeBot", is_bot=True),
            text="Automatic notification",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=41, business_message=bot_msg), self.context)

        # No replies sent
        self.assertEqual(self.bot.send_message.call_count, 0)

    # =========================================================================
    # 3. Connection State Updates & Reconnection
    # =========================================================================

    async def test_disconnect_and_reconnect(self):
        """Verify handling of business_connection updates when disconnecting and reconnecting."""
        user = User(id=1001, first_name="Alice", is_bot=False)

        # Initial connect
        bc_on = BusinessConnection(
            id="conn_a",
            user=user,
            user_chat_id=1001,
            date=datetime.now(timezone.utc),
            is_enabled=True,
            rights=BusinessBotRights(can_reply=True),
        )
        await handle_business_connection(Update(update_id=50, business_connection=bc_on), self.context)

        conn = get_business_connection("conn_a", db_path=self.db_path)
        self.assertEqual(conn["is_enabled"], 1)

        # Disconnect
        bc_off = BusinessConnection(
            id="conn_a",
            user=user,
            user_chat_id=1001,
            date=datetime.now(timezone.utc),
            is_enabled=False,
            rights=BusinessBotRights(can_reply=False),
        )
        await handle_business_connection(Update(update_id=51, business_connection=bc_off), self.context)

        conn = get_business_connection("conn_a", db_path=self.db_path)
        self.assertEqual(conn["is_enabled"], 0)

        # Client messages while disconnected -> ignored!
        client_msg = Message(
            message_id=501,
            date=datetime.now(timezone.utc),
            chat=Chat(id=9001, type=ChatType.PRIVATE),
            from_user=User(id=9001, first_name="Client1", is_bot=False),
            text="Hello while disconnected",
            business_connection_id="conn_a",
        )
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=52, business_message=client_msg), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # Reconnect
        bc_reconnect = BusinessConnection(
            id="conn_a",
            user=user,
            user_chat_id=1001,
            date=datetime.now(timezone.utc),
            is_enabled=True,
            rights=BusinessBotRights(can_reply=True),
        )
        await handle_business_connection(Update(update_id=53, business_connection=bc_reconnect), self.context)

        conn = get_business_connection("conn_a", db_path=self.db_path)
        self.assertEqual(conn["is_enabled"], 1)

        # Client messages after reconnect -> reply sent!
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=54, business_message=client_msg), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)

    # =========================================================================
    # 4. Auto-Reply ON / OFF Toggles
    # =========================================================================

    async def test_autoreply_on_and_off_toggles(self):
        """Test /autoreply_off and /autoreply_on command handlers."""
        user = User(id=1001, first_name="Alice", is_bot=False)
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)

        message = AsyncMock()
        update = Update(update_id=60, message=message)
        update._effective_user = user
        update._effective_message = message

        # Turn OFF
        await autoreply_off_command(update, self.context)
        settings = get_personal_reply_settings(1001, db_path=self.db_path)
        self.assertEqual(settings["is_enabled"], 0)
        message.reply_text.assert_called_with(unittest.mock.ANY, parse_mode=ParseMode.HTML)

        # Message arrives while disabled -> no reply sent
        client_msg = Message(
            message_id=601,
            date=datetime.now(timezone.utc),
            chat=Chat(id=9002, type=ChatType.PRIVATE),
            from_user=User(id=9002, first_name="Client2", is_bot=False),
            text="Hello?",
            business_connection_id="conn_a",
        )
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=61, business_message=client_msg), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # Turn ON
        await autoreply_on_command(update, self.context)
        settings = get_personal_reply_settings(1001, db_path=self.db_path)
        self.assertEqual(settings["is_enabled"], 1)

        # Message arrives now -> reply sent!
        await handle_business_message(Update(update_id=62, business_message=client_msg), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)

    # =========================================================================
    # 5. Database Persistence After Restart
    # =========================================================================

    async def test_database_persistence_after_restart(self):
        """Verify that all settings, contacts, templates, and logs persist across simulated restarts."""
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)
        set_personal_reply_template(1001, "Persisted message for {first_name}", db_path=self.db_path)
        check_and_claim_first_contact(1001, 5555, "client_p", "Paul", db_path=self.db_path)

        # Verify initial state
        self.assertTrue(has_replied_to_sender(1001, 5555, db_path=self.db_path))

        # Simulate bot restart by calling init_db again on same file
        init_db(self.db_path)

        # Check that records are still present
        conn = get_business_connection("conn_a", db_path=self.db_path)
        self.assertIsNotNone(conn)
        self.assertEqual(conn["user_id"], 1001)

        tmpl = get_personal_reply_template(1001, db_path=self.db_path)
        self.assertEqual(tmpl, "Persisted message for {first_name}")

        self.assertTrue(has_replied_to_sender(1001, 5555, db_path=self.db_path))

        # Paul sends message after restart -> MUST BE SUPPRESSED because history persisted!
        msg_paul = Message(
            message_id=701,
            date=datetime.now(timezone.utc),
            chat=Chat(id=5555, type=ChatType.PRIVATE),
            from_user=User(id=5555, first_name="Paul", is_bot=False),
            text="Second message after restart",
            business_connection_id="conn_a",
        )
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=70, business_message=msg_paul), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

    # =========================================================================
    # 6. Permission Failures & Telegram API Error Handling
    # =========================================================================

    async def test_permission_failures_and_api_errors(self):
        """Verify behavior when can_reply is missing and when Telegram API throws errors."""
        # 1. can_reply is False
        save_or_update_business_connection("conn_no_reply", 1001, 1001, True, False, db_path=self.db_path)
        msg_1 = Message(
            message_id=801,
            date=datetime.now(timezone.utc),
            chat=Chat(id=3333, type=ChatType.PRIVATE),
            from_user=User(id=3333, first_name="Client3", is_bot=False),
            text="Hello",
            business_connection_id="conn_no_reply",
        )
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=80, business_message=msg_1), self.context)
        # Never calls send_message when can_reply is False
        self.assertEqual(self.bot.send_message.call_count, 0)

        # 2. send_message raises Forbidden
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)
        self.bot.send_message.side_effect = Forbidden("Bot was blocked or rights revoked")

        msg_2 = Message(
            message_id=802,
            date=datetime.now(timezone.utc),
            chat=Chat(id=4444, type=ChatType.PRIVATE),
            from_user=User(id=4444, first_name="Client4", is_bot=False),
            text="Hello Forbidden",
            business_connection_id="conn_a",
        )
        # Should catch gracefully and log failure without crashing
        await handle_business_message(Update(update_id=81, business_message=msg_2), self.context)

        stats = get_user_business_stats(1001, db_path=self.db_path)
        self.assertEqual(stats["total_failed_replies"], 1)

        # 3. send_message raises BadRequest due to formatting -> retries plain text
        self.bot.send_message.reset_mock()
        self.bot.send_message.side_effect = [
            BadRequest("Can't parse entities: unclosed tag"),
            MagicMock(message_id=888),
        ]
        msg_3 = Message(
            message_id=803,
            date=datetime.now(timezone.utc),
            chat=Chat(id=5556, type=ChatType.PRIVATE),
            from_user=User(id=5556, first_name="Client5", is_bot=False),
            text="Hello Parse Error",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=82, business_message=msg_3), self.context)

        # Retried with parse_mode=None!
        self.assertEqual(self.bot.send_message.call_count, 2)
        second_call_kwargs = self.bot.send_message.call_args_list[1][1]
        self.assertIsNone(second_call_kwargs["parse_mode"])

    # =========================================================================
    # 7. Advanced Settings: Cooldown, Daily Limits, Exclusions, Delay
    # =========================================================================

    async def test_cooldown_mode(self):
        """Verify cooldown mode when first_time_only is turned OFF."""
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)
        update_personal_reply_settings(1001, first_time_only=0, cooldown_seconds=3600, db_path=self.db_path)

        client = User(id=8801, first_name="CoolClient", is_bot=False)
        chat = Chat(id=8801, type=ChatType.PRIVATE)

        # Message 1 -> Sent
        msg_1 = Message(
            message_id=901,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=client,
            text="Message 1",
            business_connection_id="conn_a",
        )
        self.bot.send_message.reset_mock()
        self.bot.send_message.side_effect = None
        await handle_business_message(Update(update_id=90, business_message=msg_1), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)

        # Message 2 immediately -> Suppressed (Cooldown active)
        msg_2 = Message(
            message_id=902,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=client,
            text="Message 2",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=91, business_message=msg_2), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)

        # Fast forward cooldown in DB: set replied_at to 4000s ago
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE business_first_contacts SET replied_at = ? WHERE business_user_id = 1001 AND sender_id = 8801",
                (datetime.now(timezone.utc).timestamp() - 4000,),
            )
            conn.commit()

        # Message 3 -> Cooldown passed, should send reply!
        msg_3 = Message(
            message_id=903,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=client,
            text="Message 3 after cooldown",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=92, business_message=msg_3), self.context)
        self.assertEqual(self.bot.send_message.call_count, 2)

    async def test_per_user_daily_reply_limits(self):
        """Verify that per-user daily reply limit is respected."""
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)
        update_personal_reply_settings(1001, daily_limit=2, db_path=self.db_path)

        self.bot.send_message.reset_mock()
        self.bot.send_message.side_effect = None

        # Client 1
        msg_1 = Message(
            message_id=1001,
            date=datetime.now(timezone.utc),
            chat=Chat(id=1111, type=ChatType.PRIVATE),
            from_user=User(id=1111, first_name="C1", is_bot=False),
            text="Hello 1",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=101, business_message=msg_1), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)

        # Client 2
        msg_2 = Message(
            message_id=1002,
            date=datetime.now(timezone.utc),
            chat=Chat(id=2222, type=ChatType.PRIVATE),
            from_user=User(id=2222, first_name="C2", is_bot=False),
            text="Hello 2",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=102, business_message=msg_2), self.context)
        self.assertEqual(self.bot.send_message.call_count, 2)

        # Client 3 -> Exceeds daily limit (2/2)! Suppressed!
        msg_3 = Message(
            message_id=1003,
            date=datetime.now(timezone.utc),
            chat=Chat(id=3333, type=ChatType.PRIVATE),
            from_user=User(id=3333, first_name="C3", is_bot=False),
            text="Hello 3",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=103, business_message=msg_3), self.context)
        self.assertEqual(self.bot.send_message.call_count, 2)

    async def test_excluded_users_and_chats(self):
        """Verify excluded users are prevented from receiving auto-replies."""
        save_or_update_business_connection("conn_a", 1001, 1001, True, True, db_path=self.db_path)
        add_excluded_user(1001, 7788, db_path=self.db_path)
        add_excluded_user(1001, "spammer_user", db_path=self.db_path)

        self.bot.send_message.reset_mock()
        self.bot.send_message.side_effect = None

        # Excluded by user ID
        msg_ex_id = Message(
            message_id=1101,
            date=datetime.now(timezone.utc),
            chat=Chat(id=7788, type=ChatType.PRIVATE),
            from_user=User(id=7788, first_name="BlockedID", is_bot=False),
            text="Hello",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=111, business_message=msg_ex_id), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # Excluded by username
        msg_ex_user = Message(
            message_id=1102,
            date=datetime.now(timezone.utc),
            chat=Chat(id=9999, type=ChatType.PRIVATE),
            from_user=User(id=9999, first_name="BlockedUsername", is_bot=False, username="spammer_user"),
            text="Hello",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=112, business_message=msg_ex_user), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # Non-excluded user
        msg_ok = Message(
            message_id=1103,
            date=datetime.now(timezone.utc),
            chat=Chat(id=5555, type=ChatType.PRIVATE),
            from_user=User(id=5555, first_name="Allowed", is_bot=False),
            text="Hello",
            business_connection_id="conn_a",
        )
        await handle_business_message(Update(update_id=113, business_message=msg_ok), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)

    # =========================================================================
    # 8. User Dashboard Commands: /personal, /setmessage, /preview, /mystatus, /resetmessage
    # =========================================================================

    async def test_dashboard_commands(self):
        """Test user dashboard commands and text input capture."""
        user = User(id=1001, first_name="Alice", is_bot=False)
        chat = Chat(id=1001, type=ChatType.PRIVATE)
        message = AsyncMock()

        update = Update(update_id=200, message=message)
        update._effective_user = user
        update._effective_chat = chat
        update._effective_message = message

        # 1. /personal
        await personal_command(update, self.context)
        message.reply_text.assert_called()
        text_arg = message.reply_text.call_args[0][0]
        self.assertIn("Personal Auto-Reply Dashboard", text_arg)

        # 2. /setmessage with args
        message.reply_text.reset_mock()
        self.context.args = ["Custom", "hello", "from", "{first_name}!"]
        await setmessage_command(update, self.context)
        self.assertEqual(get_personal_reply_template(1001, db_path=self.db_path), "Custom hello from {first_name}!")

        # 3. /preview
        message.reply_text.reset_mock()
        await preview_command(update, self.context)
        preview_text = message.reply_text.call_args[0][0]
        self.assertIn("Auto-Reply Message Preview", preview_text)
        self.assertIn("Alex", preview_text)

        # 4. /mystatus
        message.reply_text.reset_mock()
        await mystatus_command(update, self.context)
        status_text = message.reply_text.call_args[0][0]
        self.assertIn("Personal Auto-Reply Status Report", status_text)

        # 5. /resetmessage
        message.reply_text.reset_mock()
        await resetmessage_command(update, self.context)
        self.assertEqual(get_personal_reply_template(1001, db_path=self.db_path), DEFAULT_PERSONAL_REPLY_TEMPLATE)

        # 6. Interactive typing in private chat
        self.context.user_data["awaiting_personal_reply_msg"] = True
        msg_interactive = AsyncMock()
        msg_interactive.text = "Typed directly in chat: Hello {first_name}!"
        up_interactive = Update(update_id=201, message=msg_interactive)
        up_interactive._effective_user = user
        up_interactive._effective_chat = chat
        up_interactive._effective_message = msg_interactive

        await handle_private_reply_message_input(up_interactive, self.context)
        self.assertEqual(get_personal_reply_template(1001, db_path=self.db_path), "Typed directly in chat: Hello {first_name}!")
        self.assertFalse(self.context.user_data.get("awaiting_personal_reply_msg", False))

    # =========================================================================
    # 9. Concurrency & Constraint-Based Race Condition Prevention
    # =========================================================================

    async def test_concurrency_race_condition_prevention(self):
        """
        Verify that multiple concurrent calls to check_and_claim_first_contact
        for the same user and sender result in exactly ONE successful claim.
        """
        user_id = 9999
        sender_id = 8888

        # Run 10 parallel claims simultaneously
        async def claim():
            return check_and_claim_first_contact(user_id, sender_id, db_path=self.db_path)

        results = await asyncio.gather(*[claim() for _ in range(10)])

        # Exactly 1 True, all other 9 False!
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 9)

    # =========================================================================
    # 10. Edited & Deleted Business Messages
    # =========================================================================

    async def test_edited_and_deleted_messages(self):
        """Verify edited and deleted business message updates are handled gracefully without sending auto-replies."""
        # Edited business message
        msg_edit = Message(
            message_id=3001,
            date=datetime.now(timezone.utc),
            chat=Chat(id=123, type=ChatType.PRIVATE),
            from_user=User(id=456, first_name="Bob", is_bot=False),
            text="Edited message text",
            business_connection_id="conn_a",
        )
        self.bot.send_message.reset_mock()
        await handle_edited_business_message(Update(update_id=301, edited_business_message=msg_edit), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # Deleted business messages
        del_update = Update(
            update_id=302,
            deleted_business_messages=MagicMock(
                chat=Chat(id=123, type=ChatType.PRIVATE),
                business_connection_id="conn_a",
                message_ids=[3001, 3002],
            ),
        )
        await handle_deleted_business_messages(del_update, self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

    # =========================================================================
    # 11. Multi-User Validation with at least Three Separate Accounts (Phase 2 Req)
    # =========================================================================

    async def test_three_accounts_full_lifecycle(self):
        """
        Comprehensive test with at least three separate Telegram Business accounts:
        - Account 1: Alice (ID: 1001, conn_alice)
        - Account 2: Bob (ID: 2002, conn_bob)
        - Account 3: Charlie (ID: 3003, conn_charlie)

        Verifies:
        1. Multi-user independent connections.
        2. Unique custom message templates per account.
        3. First-time sender detection and reply dispatch with the correct template.
        4. Repeat sender suppression for each account.
        5. The same sender messaging all 3 accounts receives each account's distinct template once.
        6. Disconnection and permission revocation handling (no replies when disabled or can_reply=False).
        7. Reconnection and permission restoration.
        8. Bot restart persistence (database survives restart, first-contact state and settings preserved).
        """
        alice_id, bob_id, charlie_id = 1001, 2002, 3003
        conn_alice, conn_bob, conn_charlie = "conn_alice", "conn_bob", "conn_charlie"

        # 1. Connect all 3 accounts
        for uid, cid, uname, fname in [
            (alice_id, conn_alice, "alice_design", "Alice"),
            (bob_id, conn_bob, "bob_consulting", "Bob"),
            (charlie_id, conn_charlie, "charlie_dev", "Charlie"),
        ]:
            save_or_update_business_connection(
                connection_id=cid,
                user_id=uid,
                user_chat_id=uid,
                is_enabled=True,
                can_reply=True,
                account_username=uname,
                account_first_name=fname,
                db_path=self.db_path,
            )

        # 2. Configure 3 distinct custom reply templates
        set_personal_reply_template(alice_id, "Hello {first_name}! Alice's design studio is closed.", db_path=self.db_path)
        set_personal_reply_template(bob_id, "Hi {first_name}! Bob's consulting agency received your inquiry.", db_path=self.db_path)
        set_personal_reply_template(charlie_id, "Hey {first_name}! Charlie is currently coding.", db_path=self.db_path)

        # Verify templates are strictly isolated
        self.assertIn("design studio", get_personal_reply_template(alice_id, db_path=self.db_path))
        self.assertIn("consulting agency", get_personal_reply_template(bob_id, db_path=self.db_path))
        self.assertIn("coding", get_personal_reply_template(charlie_id, db_path=self.db_path))

        # 3. Sender Dave (4004) messages Alice
        dave = User(id=4004, first_name="Dave", is_bot=False)
        self.bot.send_message.reset_mock()
        msg_dave_alice = Message(
            message_id=5001,
            date=datetime.now(timezone.utc),
            chat=Chat(id=4004, type=ChatType.PRIVATE),
            from_user=dave,
            text="Hi Alice",
            business_connection_id=conn_alice,
        )
        await handle_business_message(Update(update_id=501, business_message=msg_dave_alice), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)
        self.assertIn("Alice's design studio", self.bot.send_message.call_args[1]["text"])
        self.assertEqual(self.bot.send_message.call_args[1]["business_connection_id"], conn_alice)

        # Dave messages Alice a 2nd time -> Suppressed
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=502, business_message=msg_dave_alice), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # 4. Same sender Dave (4004) messages Bob -> Bob's template sent once
        self.bot.send_message.reset_mock()
        msg_dave_bob = Message(
            message_id=5003,
            date=datetime.now(timezone.utc),
            chat=Chat(id=4004, type=ChatType.PRIVATE),
            from_user=dave,
            text="Hi Bob",
            business_connection_id=conn_bob,
        )
        await handle_business_message(Update(update_id=503, business_message=msg_dave_bob), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)
        self.assertIn("Bob's consulting agency", self.bot.send_message.call_args[1]["text"])
        self.assertEqual(self.bot.send_message.call_args[1]["business_connection_id"], conn_bob)

        # Dave messages Bob a 2nd time -> Suppressed
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=504, business_message=msg_dave_bob), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # 5. Same sender Dave (4004) messages Charlie -> Charlie's template sent once
        self.bot.send_message.reset_mock()
        msg_dave_charlie = Message(
            message_id=5005,
            date=datetime.now(timezone.utc),
            chat=Chat(id=4004, type=ChatType.PRIVATE),
            from_user=dave,
            text="Hi Charlie",
            business_connection_id=conn_charlie,
        )
        await handle_business_message(Update(update_id=505, business_message=msg_dave_charlie), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)
        self.assertIn("Charlie is currently coding", self.bot.send_message.call_args[1]["text"])
        self.assertEqual(self.bot.send_message.call_args[1]["business_connection_id"], conn_charlie)

        # Dave messages Charlie a 2nd time -> Suppressed
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=506, business_message=msg_dave_charlie), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # 6. Disconnection and permission changes
        # Bob's account revokes can_reply
        save_or_update_business_connection(
            connection_id=conn_bob,
            user_id=bob_id,
            user_chat_id=bob_id,
            is_enabled=True,
            can_reply=False,  # Revoked!
            db_path=self.db_path,
        )
        # New sender Eve (6006) messages Bob -> No reply because can_reply is False
        eve = User(id=6006, first_name="Eve", is_bot=False)
        self.bot.send_message.reset_mock()
        msg_eve_bob = Message(
            message_id=5007,
            date=datetime.now(timezone.utc),
            chat=Chat(id=6006, type=ChatType.PRIVATE),
            from_user=eve,
            text="Hello Bob",
            business_connection_id=conn_bob,
        )
        await handle_business_message(Update(update_id=507, business_message=msg_eve_bob), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # Bob re-grants can_reply permission
        save_or_update_business_connection(
            connection_id=conn_bob,
            user_id=bob_id,
            user_chat_id=bob_id,
            is_enabled=True,
            can_reply=True,  # Restored!
            db_path=self.db_path,
        )
        # Eve messages Bob again -> Now Bob replies!
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=508, business_message=msg_eve_bob), self.context)
        self.assertEqual(self.bot.send_message.call_count, 1)
        self.assertIn("Bob's consulting agency", self.bot.send_message.call_args[1]["text"])

        # 7. Disconnection event: Charlie completely disconnects
        save_or_update_business_connection(
            connection_id=conn_charlie,
            user_id=charlie_id,
            user_chat_id=charlie_id,
            is_enabled=False,  # Disconnected
            can_reply=False,
            db_path=self.db_path,
        )
        frank = User(id=7007, first_name="Frank", is_bot=False)
        self.bot.send_message.reset_mock()
        msg_frank_charlie = Message(
            message_id=5009,
            date=datetime.now(timezone.utc),
            chat=Chat(id=7007, type=ChatType.PRIVATE),
            from_user=frank,
            text="Hello Charlie",
            business_connection_id=conn_charlie,
        )
        await handle_business_message(Update(update_id=509, business_message=msg_frank_charlie), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # 8. Bot restart simulation: database persistence check
        # Close connection, re-initialize db, query settings and sender histories
        init_db(self.db_path)
        # Verify Alice's sender history persists: Dave (4004) is still recorded as replied
        self.assertTrue(has_replied_to_sender(alice_id, 4004, db_path=self.db_path))
        self.assertTrue(has_replied_to_sender(bob_id, 4004, db_path=self.db_path))
        self.assertTrue(has_replied_to_sender(charlie_id, 4004, db_path=self.db_path))
        # Dave messages Alice after "restart" -> Still suppressed
        self.bot.send_message.reset_mock()
        await handle_business_message(Update(update_id=510, business_message=msg_dave_alice), self.context)
        self.assertEqual(self.bot.send_message.call_count, 0)

        # All 3 users maintain their independent statistics
        stats_alice = get_user_business_stats(alice_id, db_path=self.db_path)
        stats_bob = get_user_business_stats(bob_id, db_path=self.db_path)
        stats_charlie = get_user_business_stats(charlie_id, db_path=self.db_path)
        self.assertEqual(stats_alice["total_contacts"], 1)  # Dave
        self.assertEqual(stats_bob["total_contacts"], 2)    # Dave + Eve
        self.assertEqual(stats_charlie["total_contacts"], 1) # Dave


if __name__ == "__main__":
    unittest.main()

import re
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from src import listener, reply_tracking as tracking

NOW = datetime.now(timezone.utc).replace(microsecond=0)
MENU = {"generated_at": (NOW - timedelta(hours=1)).isoformat(), "summaries": []}
SUBJECT = "Re: PulseK12 Menu — Week of " + datetime.fromisoformat(MENU["generated_at"]).strftime("%b %d, %Y")


class Mailbox:
    def __init__(self, initialized=True):
        self.folders = {tracking.INITIALIZED} if initialized else set()
        self.messages = {}
        self.criteria = []

    def add(self, uid, seen=False, labels=(), age=0, subject=SUBJECT, sender="editor@example.com"):
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg.set_content("1, 3")
        self.messages[uid] = {"seen": seen, "labels": set(labels), "raw": msg.as_bytes(), "date": NOW - timedelta(minutes=age)}

    def select(self, folder):
        return "OK", [b"1"]

    def list(self, reference, folder):
        return "OK", [folder.encode()] if folder in self.folders else [None]

    def create(self, folder):
        self.folders.add(folder)
        return "OK", []

    def uid(self, action, *args):
        if action == "search":
            criteria = args[1]
            self.criteria.append(criteria)
            excluded = re.findall(r'NOT X-GM-LABELS "([^"]+)"', criteria)
            required = re.findall(r'(?<!NOT )X-GM-LABELS "([^"]+)"', criteria)
            ids = [uid for uid, msg in self.messages.items()
                   if not any(label in msg["labels"] for label in excluded)
                   and all(label in msg["labels"] for label in required)
                   and (" SEEN" not in criteria or msg["seen"])]
            return "OK", [b" ".join(ids)]
        uid = args[0]
        msg = self.messages[uid]
        if action == "fetch":
            metadata = ('1 (INTERNALDATE "' + msg["date"].strftime("%d-%b-%Y %H:%M:%S %z") + '")').encode()
            return "OK", [(metadata, msg["raw"])]
        if action == "store":
            label = args[2].strip('()"')
            if args[1] == "+X-GM-LABELS":
                msg["labels"].add(label)
            elif args[1] == "-X-GM-LABELS":
                msg["labels"].discard(label)
            return "OK", []
        raise AssertionError(action)


class ReplyLifecycleTests(unittest.TestCase):
    def replies(self, mail):
        with patch.object(listener, "get_target_sender", return_value="editor@example.com"):
            return listener.check_for_replies(mail, MENU)

    def test_read_reply_is_processed_after_initialization(self):
        mail = Mailbox()
        mail.add(b"42", seen=True)
        self.assertEqual(len(self.replies(mail)), 1)
        self.assertNotIn("UNSEEN", mail.criteria[-1])

    def test_unread_processed_reply_is_not_replayed(self):
        mail = Mailbox()
        mail.add(b"42", labels=[tracking.PROCESSED])
        self.assertEqual(self.replies(mail), [])

    def test_first_run_skips_old_read_messages_but_keeps_unread(self):
        mail = Mailbox(initialized=False)
        mail.add(b"41", seen=True)
        mail.add(b"42", seen=False)
        self.assertEqual([r["email_id"] for r in self.replies(mail)], [b"42"])
        self.assertIn(tracking.LEGACY, mail.messages[b"41"]["labels"])
        mail.add(b"43", seen=True)
        self.assertEqual([r["email_id"] for r in self.replies(mail)], [b"42", b"43"])

    def test_reply_arriving_before_current_menu_is_ignored(self):
        mail = Mailbox()
        mail.add(b"42", age=120)
        self.assertEqual(self.replies(mail), [])

    def test_old_menu_numbers_are_ignored_even_when_arrival_is_new(self):
        mail = Mailbox()
        mail.add(b"42", subject="Re: PulseK12 Menu — Week of " + (NOW - timedelta(days=8)).strftime("%b %d, %Y"))
        self.assertEqual(self.replies(mail), [])

    def test_substring_sender_match_is_not_accepted(self):
        mail = Mailbox()
        mail.add(b"42", sender="other-editor@example.com")
        self.assertEqual(self.replies(mail), [])

    def test_interrupted_send_requires_review_without_replay(self):
        mail = Mailbox()
        mail.add(b"42")
        tracking.start_send(mail, b"42")
        with self.assertRaisesRegex(RuntimeError, "uncertain outcome"):
            self.replies(mail)

    def test_successful_send_is_durable_even_if_mark_read_fails(self):
        mail = Mailbox()
        mail.add(b"42")
        tracking.start_send(mail, b"42")
        tracking.finish_send(mail, b"42")
        self.assertEqual(self.replies(mail), [])
        self.assertNotIn(tracking.PROCESSING, mail.messages[b"42"]["labels"])

    def test_label_failure_stops_send_claim(self):
        mail = MagicMock()
        mail.uid.return_value = ("NO", [b"denied"])
        with self.assertRaises(RuntimeError):
            tracking.start_send(mail, b"42")

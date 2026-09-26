import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from email.message import EmailMessage

from src import listener


class ListenerRegressionTests(unittest.TestCase):
    def test_connection_failure_exits_nonzero(self):
        with patch.object(listener, "run_listener", return_value={"errors": ["IMAP unavailable"], "emails_found": 0}), self.assertRaises(SystemExit) as exit_result:
            listener.main()
        self.assertEqual(exit_result.exception.code, 1)

    def test_partial_failure_exits_nonzero(self):
        with patch.object(listener, "run_listener", return_value={"errors": ["send failed"], "emails_found": 2, "emails_processed": 1}), self.assertRaises(SystemExit) as exit_result:
            listener.main()
        self.assertEqual(exit_result.exception.code, 1)

    def test_tracker_included_in_reply(self):
        data = {"summaries": [], "state_tracker": {"synthesis": {"topic_title": "School funding", "whats_happening": "Verified state actions."}}}
        result = listener.process_combined_reply({"selections": [], "urls": []}, data)
        self.assertIn("50-STATE TOPIC TRACKER", result["content"])
        self.assertIn("Verified state actions.", result["content"])

    def test_search_failure_is_not_empty_success(self):
        mail = MagicMock()
        mail.select.return_value = ("OK", [b"0"])
        mail.uid.return_value = ("NO", [b"Unavailable"])
        mail.list.return_value = ("OK", [b"tracking label exists"])
        mail.search.return_value = ("NO", [b"Unavailable"])
        with patch.object(listener, "get_target_sender", return_value="editor@example.com"), self.assertRaises(RuntimeError):
            listener.check_for_replies(mail)


if __name__ == "__main__":
    unittest.main()

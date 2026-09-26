import unittest
from unittest.mock import MagicMock, patch
from contextlib import ExitStack

from src import listener


class ListenerDeliveryTests(unittest.TestCase):
    def run_delivery(self, send_success=True, claim_error=None):
        events = []
        reply = {"email_id": b"42", "subject": "PulseK12", "from": "editor@example.com", "urls": ["https://example.com"], "has_urls": True}
        with ExitStack() as stack:
            stack.enter_context(patch.object(listener, "load_summaries", return_value={}))
            stack.enter_context(patch.object(listener, "connect_to_gmail", return_value=MagicMock()))
            stack.enter_context(patch.object(listener, "check_for_replies", return_value=[reply]))
            stack.enter_context(patch.object(listener, "process_combined_reply", return_value={"success": True, "content": "Verified response"}))
            def claim(*args):
                events.append("claim")
                if claim_error:
                    raise RuntimeError(claim_error)
            stack.enter_context(patch.object(listener, "start_send", side_effect=claim))
            stack.enter_context(patch.object(listener, "send_url_summary_response", side_effect=lambda **kw: events.append("send") or {"success": send_success, "error": "SMTP error"}))
            stack.enter_context(patch.object(listener, "finish_send", side_effect=lambda *args: events.append("complete")))
            stack.enter_context(patch.object(listener, "mark_as_read", side_effect=lambda *args: events.append("read")))
            stack.enter_context(patch.object(listener, "record_editor_feedback", return_value={}))
            result = listener.run_listener()
        return events, result

    def test_delivery_is_claimed_then_completed_after_send(self):
        events, result = self.run_delivery()
        self.assertEqual(events, ["claim", "send", "complete", "read"])
        self.assertEqual(result["emails_processed"], 1)

    def test_no_send_if_claim_cannot_be_saved(self):
        events, result = self.run_delivery(claim_error="label failed")
        self.assertEqual(events, ["claim"])
        self.assertTrue(result["errors"])

    def test_failed_send_is_not_marked_processed_or_read(self):
        events, result = self.run_delivery(send_success=False)
        self.assertEqual(events, ["claim", "send"])
        self.assertTrue(result["errors"])

    def test_blank_summary_is_reported_as_failure_not_a_story(self):
        with patch("src.scraper.get_firecrawl_client", return_value=MagicMock()), patch("src.scraper.scrape_article", return_value={"success": True, "title": "Schools improve tutoring", "content": "Evidence " * 100}), patch("src.summarizer.summarize_article", return_value={"success": True, "headline": "", "summary": ""}):
            result = listener.process_url_submission(["https://www.chalkbeat.org/story"])
        self.assertEqual(result["results"], [])
        self.assertEqual(result["failed_count"], 1)

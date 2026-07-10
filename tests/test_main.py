import unittest
from unittest.mock import patch

from src.main import run_pipeline


def make_articles(count):
    return [
        {
            "title": f"Article {index}",
            "url": f"https://example.com/{index}",
            "source": "Test Source",
            "category": "teaching",
            "is_local": False,
            "total_score": 1.0,
            "full_content": "Article content",
        }
        for index in range(count)
    ]


def make_summaries(complete, failed):
    summaries = [
        {
            "success": True,
            "headline": f"Complete headline {index}",
            "summary": "A complete summary with enough meaningful content to pass validation.",
            "systemic_error": False,
        }
        for index in range(complete)
    ]
    summaries.extend(
        {
            "success": False,
            "headline": "Failed headline",
            "summary": "",
            "error": "temporary failure",
            "systemic_error": False,
        }
        for _ in range(failed)
    )
    return summaries


class MainPipelineTests(unittest.TestCase):
    def test_preflight_failure_stops_before_fetching(self):
        with patch("src.main.preflight_anthropic", side_effect=RuntimeError("no credits")):
            with patch("src.main.fetch_all_feeds") as fetch_mock:
                result = run_pipeline(send_email=False)

        self.assertFalse(result["success"])
        self.assertIn("Anthropic preflight failed", result["error"])
        fetch_mock.assert_not_called()

    def test_quality_gate_prevents_save_and_email(self):
        articles = make_articles(15)
        summaries = make_summaries(complete=14, failed=1)

        with patch("src.main.preflight_anthropic", return_value="claude-test-model"), \
             patch("src.main.fetch_all_feeds", return_value=articles), \
             patch("src.main.filter_by_date", side_effect=lambda items, **_: items), \
             patch("src.main.count_feed_appearances", side_effect=lambda items: items), \
             patch("src.main.deduplicate_articles", side_effect=lambda items: items), \
             patch("src.main.filter_relevant_articles", side_effect=lambda items: items), \
             patch("src.main.load_feedback_profile", return_value={"event_count": 0}), \
             patch("src.main.classify_all_articles", side_effect=lambda items, **_: items), \
             patch("src.main.select_balanced_menu", side_effect=lambda items, target_count, **_: items[:target_count]), \
             patch("src.main.print_distribution"), \
             patch("src.main.scrape_articles", side_effect=lambda items, **_: items), \
             patch("src.main.summarize_all_articles", return_value=summaries), \
             patch("src.main.save_summaries") as save_mock, \
             patch("src.main.send_newsletter") as send_mock:
            result = run_pipeline(target_articles=15, send_email=True)

        self.assertFalse(result["success"])
        self.assertEqual(result["stats"]["summarized"], 14)
        self.assertFalse(result["stats"]["quality_gate_passed"])
        save_mock.assert_not_called()
        send_mock.assert_not_called()

    def test_systemic_summary_error_prevents_save_and_email(self):
        articles = make_articles(15)
        summaries = [
            {
                "success": False,
                "headline": "Failed headline",
                "summary": "",
                "error": "not_found_error: model is unavailable",
                "systemic_error": True,
            }
        ]

        with patch("src.main.preflight_anthropic", return_value="claude-test-model"), \
             patch("src.main.fetch_all_feeds", return_value=articles), \
             patch("src.main.filter_by_date", side_effect=lambda items, **_: items), \
             patch("src.main.count_feed_appearances", side_effect=lambda items: items), \
             patch("src.main.deduplicate_articles", side_effect=lambda items: items), \
             patch("src.main.filter_relevant_articles", side_effect=lambda items: items), \
             patch("src.main.load_feedback_profile", return_value={"event_count": 0}), \
             patch("src.main.classify_all_articles", side_effect=lambda items, **_: items), \
             patch("src.main.select_balanced_menu", side_effect=lambda items, target_count, **_: items[:target_count]), \
             patch("src.main.print_distribution"), \
             patch("src.main.scrape_articles", side_effect=lambda items, **_: items), \
             patch("src.main.summarize_all_articles", return_value=summaries), \
             patch("src.main.save_summaries") as save_mock, \
             patch("src.main.send_newsletter") as send_mock:
            result = run_pipeline(target_articles=15, send_email=True)

        self.assertFalse(result["success"])
        self.assertTrue(result["stats"]["systemic_summary_error"])
        self.assertIn("systemic Anthropic error", result["error"])
        save_mock.assert_not_called()
        send_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
from contextlib import ExitStack
from src.main import run_pipeline

from src.main import backfill_summaries
from src.state_tracker.synthesis import build_articles_summary


def article(url="https://www.chalkbeat.org/story"):
    return {"title": "Schools expand tutoring", "source": "Chalkbeat", "url": url}


def summary():
    return {"success": True, "headline": "Schools expand tutoring", "summary": "A verified source reports tutoring outcomes. " * 5}


class PipelineQualityTests(unittest.TestCase):
    def test_backup_rejected_after_resolution_is_never_scraped(self):
        with patch("src.main.resolve_google_news_url", return_value="https://schools.co.uk/story"), patch("src.main.scrape_article") as scrape:
            result, systemic = backfill_summaries([], [article()], 1)
        self.assertEqual(result, [])
        scrape.assert_not_called()

    def test_scraped_title_can_disqualify_backup(self):
        with patch("src.main.resolve_google_news_url", return_value="https://www.chalkbeat.org/story"), patch("src.main.scrape_article", return_value={"success": True, "title": "Philippines adds school counselors", "content": "Article text " * 100}), patch("src.main.summarize_article") as summarize:
            result, _ = backfill_summaries([], [article()], 1)
        self.assertEqual(result, [])
        summarize.assert_not_called()

    def test_backfill_continues_past_bad_replacements(self):
        with patch("src.main.resolve_google_news_url", side_effect=lambda url: url), patch("src.main.scrape_article", side_effect=[{"success": False}, {"success": True, "content": "Article text " * 100}]), patch("src.main.summarize_article", return_value=summary()):
            result, systemic = backfill_summaries([], [article(), article()], 1)
        self.assertEqual(len(result), 1)
        self.assertFalse(systemic)

    def test_systemic_backup_failure_stops_more_requests(self):
        with patch("src.main.resolve_google_news_url", side_effect=lambda url: url), patch("src.main.scrape_article", return_value={"success": True, "content": "Article text " * 100}) as scrape, patch("src.main.summarize_article", return_value={"success": False, "systemic_error": True, "error": "no credit"}):
            result, systemic = backfill_summaries([], [article(), article()], 1)
        self.assertTrue(systemic)
        self.assertEqual(scrape.call_count, 1)

    def test_state_synthesis_receives_article_evidence(self):
        source = article()
        source["full_content"] = "District evidence: students attended 120 sessions. " * 30
        self.assertIn("students attended 120 sessions", build_articles_summary([source]))

    def test_rejected_candidate_does_not_reenter_selection_pool(self):
        bad = article("https://news.google.com/rss/articles/bad")
        good = article()
        for item in (bad, good):
            item.update(is_local=False, category="teaching", total_score=1)
        with ExitStack() as stack:
            stack.enter_context(patch("src.main.preflight_anthropic", return_value="test"))
            stack.enter_context(patch("src.main.fetch_all_feeds", return_value=[bad, good]))
            for name in ("filter_by_date", "count_feed_appearances", "deduplicate_articles", "classify_all_articles"):
                stack.enter_context(patch("src.main." + name, side_effect=lambda items, **kw: items))
            stack.enter_context(patch("src.main.load_feedback_profile", return_value={}))
            stack.enter_context(patch("src.main.resolve_google_news_url", return_value="https://school.co.uk/story"))
            stack.enter_context(patch("src.main.select_balanced_menu", side_effect=lambda items, **kw: items[:1]))
            scrape = stack.enter_context(patch("src.main.scrape_articles", side_effect=lambda items, **kw: items))
            stack.enter_context(patch("src.main.summarize_all_articles", return_value=[summary()]))
            stack.enter_context(patch("src.main.save_summaries"))
            result = run_pipeline(target_articles=1, send_email=False)
        self.assertTrue(result["success"])
        self.assertEqual(scrape.call_args.args[0], [good])

import unittest
from unittest.mock import MagicMock, patch

from src.scraper import get_content_for_summary, scrape_article
from src.summarizer import summarize_article
from src.categorizer import is_international_story


class ContentQualityTests(unittest.TestCase):
    def test_rss_snippet_cannot_be_used_as_article(self):
        with self.assertRaises(ValueError):
            get_content_for_summary({"title": "School funding", "summary": "Headline-only RSS snippet"})

    def test_thin_content_never_calls_claude(self):
        client = MagicMock()
        result = summarize_article({"title": "School funding", "full_content": "Subscribe to read more"}, client)
        self.assertFalse(result["success"])
        client.messages.create.assert_not_called()

    def test_missing_firecrawl_key_still_uses_free_fallback(self):
        with patch("src.scraper.get_firecrawl_client", side_effect=ValueError("Missing key")), patch("src.scraper._scrape_with_requests", return_value={"success": True, "content": "Article text " * 100}) as fallback:
            result = scrape_article("https://example.com/story")
        self.assertTrue(result["success"])
        fallback.assert_called_once()

    def test_rejects_serbian_school_story(self):
        self.assertTrue(is_international_story({"title": "Serbia grounds school media literacy in data", "url": "https://coe.int/story"})[0])

    def test_international_tld_does_not_match_us_domain_substring(self):
        self.assertFalse(is_international_story({"title": "District schools expand tutoring", "url": "https://www.chalkbeat.org/story"})[0])

    def test_international_metadata_title_checked_after_scraping(self):
        self.assertTrue(is_international_story({"title": "Schools add counselors", "scraped_title": "Philippines weighs 10000 school counselor jobs", "url": "https://example.com/story"})[0])


if __name__ == "__main__":
    unittest.main()

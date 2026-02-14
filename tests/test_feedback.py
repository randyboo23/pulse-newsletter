import unittest
from datetime import datetime, timedelta, timezone

from src.feedback import (
    build_feedback_profile,
    extract_signal_tokens,
    get_feedback_boost,
    normalize_category_id
)


class FeedbackTests(unittest.TestCase):
    def test_extract_signal_tokens_prefers_repeated_content_words(self):
        text = (
            "District attendance plans target chronic absenteeism. "
            "Attendance teams track absenteeism weekly."
        )
        tokens = extract_signal_tokens(text)

        self.assertIn("attendance", tokens)
        self.assertIn("absenteeism", tokens)
        self.assertNotIn("district", tokens)  # stopword-ish generic term

    def test_category_normalization_from_label(self):
        self.assertEqual(normalize_category_id("AI & EdTech"), "ai_edtech")
        self.assertEqual(normalize_category_id("Teaching & Learning"), "teaching")

    def test_submitted_url_signal_is_stronger_than_menu_selection(self):
        now = datetime.now(timezone.utc)
        data = {
            "events": [
                {
                    "timestamp": now.isoformat(),
                    "signal": "menu_selection",
                    "weight": 1.0,
                    "domain": "edweek.org",
                    "category": "teaching"
                },
                {
                    "timestamp": now.isoformat(),
                    "signal": "submitted_url",
                    "weight": 3.0,
                    "domain": "chalkbeat.org",
                    "category": None
                }
            ]
        }
        profile = build_feedback_profile(data, now=now)

        menu_article = {
            "url": "https://edweek.org/story",
            "category": "policy"
        }
        submitted_url_article = {
            "url": "https://chalkbeat.org/story",
            "category": "policy"
        }

        menu_boost, _ = get_feedback_boost(menu_article, profile)
        url_boost, _ = get_feedback_boost(submitted_url_article, profile)

        self.assertGreater(url_boost, menu_boost)

    def test_recent_events_have_more_weight_than_old_events(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=1)
        old = now - timedelta(days=120)

        recent_profile = build_feedback_profile(
            {
                "events": [
                    {
                        "timestamp": recent.isoformat(),
                        "signal": "submitted_url",
                        "weight": 3.0,
                        "domain": "k12dive.com",
                        "category": None
                    }
                ]
            },
            now=now
        )

        old_profile = build_feedback_profile(
            {
                "events": [
                    {
                        "timestamp": old.isoformat(),
                        "signal": "submitted_url",
                        "weight": 3.0,
                        "domain": "k12dive.com",
                        "category": None
                    }
                ]
            },
            now=now
        )

        article = {
            "url": "https://k12dive.com/story",
            "category": "policy"
        }

        recent_boost, _ = get_feedback_boost(article, recent_profile)
        old_boost, _ = get_feedback_boost(article, old_profile)

        self.assertGreater(recent_boost, old_boost)

    def test_token_overlap_boosts_relevant_headlines(self):
        now = datetime.now(timezone.utc)
        profile = build_feedback_profile(
            {
                "events": [
                    {
                        "timestamp": now.isoformat(),
                        "signal": "menu_selection",
                        "weight": 1.0,
                        "domain": "edweek.org",
                        "category": "teaching",
                        "tokens": ["attendance", "absenteeism", "intervention"]
                    }
                ]
            },
            now=now
        )

        relevant_article = {
            "url": "https://example.com/story",
            "title": "District intervention plans target chronic absenteeism and attendance",
            "summary": "Leaders are deploying attendance intervention teams.",
            "category": "teaching"
        }
        unrelated_article = {
            "url": "https://example.com/other",
            "title": "Procurement cycle updates for district transportation",
            "summary": "Bus contract renewals remain a board priority.",
            "category": "teaching"
        }

        relevant_boost, relevant_reason = get_feedback_boost(relevant_article, profile)
        unrelated_boost, _ = get_feedback_boost(unrelated_article, profile)

        self.assertGreater(relevant_boost, unrelated_boost)
        self.assertIn("tokens:", relevant_reason)


if __name__ == "__main__":
    unittest.main()

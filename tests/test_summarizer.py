import unittest
from types import SimpleNamespace

from src.summarizer import summarize_all_articles, summarize_article


class FailingMessages:
    def __init__(self):
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        raise RuntimeError("not_found_error: model is unavailable")


class FailingClient:
    def __init__(self):
        self.messages = FailingMessages()


class ThinkingThenTextMessages:
    def create(self, **kwargs):
        return SimpleNamespace(content=[
            SimpleNamespace(type="thinking", thinking="internal reasoning"),
            SimpleNamespace(
                type="text",
                text=(
                    "HEADLINE: District Tutoring Pilot Shows Early Promise\n"
                    "SUMMARY: A district tutoring pilot served 1,200 middle school students. "
                    "Attendance and math completion improved during the program. "
                    "Leaders will review achievement data before expanding the approach."
                ),
            ),
        ])


class ThinkingThenTextClient:
    def __init__(self):
        self.messages = ThinkingThenTextMessages()


class SummarizerTests(unittest.TestCase):
    def test_summary_uses_text_block_after_thinking_block(self):
        article = {
            "title": "District tutoring pilot",
            "source": "Test Source",
            "url": "https://example.com/tutoring",
            "category": "teaching",
            "full_content": "Meaningful article content for summary testing.",
        }

        summary = summarize_article(article, client=ThinkingThenTextClient())

        self.assertTrue(summary["success"])
        self.assertEqual(
            summary["headline"],
            "District Tutoring Pilot Shows Early Promise",
        )
        self.assertIn("1,200 middle school students", summary["summary"])

    def test_systemic_error_stops_remaining_summary_attempts(self):
        articles = [
            {
                "title": f"Article {index}",
                "source": "Test Source",
                "url": f"https://example.com/{index}",
                "category": "teaching",
                "full_content": "Meaningful article content for summary testing.",
            }
            for index in range(3)
        ]
        client = FailingClient()

        summaries = summarize_all_articles(articles, client=client)

        self.assertEqual(client.messages.call_count, 1)
        self.assertEqual(len(summaries), 1)
        self.assertFalse(summaries[0]["success"])
        self.assertTrue(summaries[0]["systemic_error"])


if __name__ == "__main__":
    unittest.main()

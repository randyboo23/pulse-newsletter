import unittest

from src.summarizer import summarize_all_articles


class FailingMessages:
    def __init__(self):
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        raise RuntimeError("not_found_error: model is unavailable")


class FailingClient:
    def __init__(self):
        self.messages = FailingMessages()


class SummarizerTests(unittest.TestCase):
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

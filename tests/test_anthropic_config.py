import os
import unittest
from unittest.mock import patch

from src.anthropic_config import (
    DEFAULT_ANTHROPIC_MODEL,
    get_anthropic_model,
    get_minimum_complete_summaries,
    is_systemic_anthropic_error,
    preflight_anthropic,
)


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return object()


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


class AnthropicConfigTests(unittest.TestCase):
    def test_model_defaults_and_can_be_overridden(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_anthropic_model(), DEFAULT_ANTHROPIC_MODEL)

        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "claude-test-model"}):
            self.assertEqual(get_anthropic_model(), "claude-test-model")

    def test_preflight_uses_configured_model(self):
        client = FakeClient()

        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "claude-test-model"}):
            model = preflight_anthropic(client)

        self.assertEqual(model, "claude-test-model")
        self.assertEqual(len(client.messages.calls), 1)
        self.assertEqual(client.messages.calls[0]["model"], "claude-test-model")
        self.assertEqual(client.messages.calls[0]["max_tokens"], 8)

    def test_systemic_error_detection_covers_billing_and_model_access(self):
        self.assertTrue(
            is_systemic_anthropic_error(
                RuntimeError("Your credit balance is too low. Go to Plans & Billing.")
            )
        )
        self.assertTrue(
            is_systemic_anthropic_error(
                RuntimeError("not_found_error: model is unavailable")
            )
        )
        self.assertFalse(is_systemic_anthropic_error(RuntimeError("temporary timeout")))

    def test_minimum_summary_count_respects_small_explicit_requests(self):
        self.assertEqual(get_minimum_complete_summaries(25), 15)
        self.assertEqual(get_minimum_complete_summaries(15), 15)
        self.assertEqual(get_minimum_complete_summaries(5), 5)


if __name__ == "__main__":
    unittest.main()

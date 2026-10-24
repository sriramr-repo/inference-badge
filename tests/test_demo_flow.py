import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from demo_flow import advance_demo, new_demo_state, set_dave_sharing
import enrichment
from enrichment import fallback_brief


class DemoFlowTests(unittest.TestCase):
    def test_next_only_path_completes_all_demo_moments(self):
        state = new_demo_state()

        for _ in range(4):
            state = advance_demo(state)

        self.assertEqual(state["step"], 5)
        self.assertTrue(state["walked_to_sarah"])
        self.assertTrue(state["collision_stopped"])
        self.assertFalse(state["talk_logged"])

        state = advance_demo(state)
        self.assertEqual(state["step"], 5)
        self.assertTrue(state["talk_logged"])
        self.assertTrue(state["done"])

        self.assertEqual(advance_demo(state), state)

    def test_private_toggle_does_not_change_demo_progress(self):
        state = new_demo_state()
        private_state = set_dave_sharing(state, False)
        shared_state = set_dave_sharing(private_state, True)

        self.assertFalse(private_state["dave_sharing"])
        self.assertTrue(shared_state["dave_sharing"])
        self.assertEqual(shared_state["step"], 1)

    def test_fallback_brief_is_exactly_three_bullets_and_preserves_anonymity(self):
        brief = fallback_brief(
            {
                "name": "Attendee (private)",
                "locationShared": False,
                "company": "Demo Company",
                "session": "Demo session",
            }
        )
        bullets = [line for line in brief.splitlines() if line.startswith("- ")]

        self.assertEqual(len(bullets), 3)
        self.assertIn("Anonymous attendee (privacy shield active)", brief)
        self.assertNotIn("Dave Demo", brief)

    def test_malformed_openai_response_uses_three_bullet_fallback(self):
        client = Mock()
        client.chat.completions.create.return_value.choices = [
            SimpleNamespace(message=SimpleNamespace(content="A paragraph, not three bullets."))
        ]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch.object(enrichment, "OpenAI", return_value=client):
                brief = enrichment.generate_strategy_brief(
                    {"name": "Sarah Demo", "locationShared": True}
                )

        self.assertEqual(len([line for line in brief.splitlines() if line.startswith("- ")]), 3)
        self.assertIn("AI response did not match", brief)


if __name__ == "__main__":
    unittest.main()

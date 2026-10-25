import unittest
from unittest.mock import patch

from database import DatabaseError
from pathlib import Path
from streamlit.testing.v1 import AppTest

import conference_simulation as simulation


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


class ConferenceSimulationTests(unittest.TestCase):
    def _open_simulation(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        next(
            button
            for button in app.button
            if button.label == "Conference day simulation"
        ).click().run()
        return app

    def test_simulation_route_falls_back_to_in_memory_graph(self):
        with patch(
            "conference_simulation.run_query_on_graph",
            side_effect=DatabaseError("unavailable"),
        ):
            app = self._open_simulation()

        self.assertEqual(app.session_state["page"], "Conference day")
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("SIMULATION · Demo conference · No real data", rendered)
        captions = "\n".join(item.value for item in app.caption)
        self.assertIn("Shared team memory · in-memory session demo", captions)
        self.assertFalse(app.exception)

    def test_existing_simulation_session_is_migrated_with_new_defaults(self):
        with patch(
            "conference_simulation.run_query_on_graph",
            side_effect=DatabaseError("unavailable"),
        ):
            app = self._open_simulation()
            app.session_state["conference_day_simulation"] = {
                "phase": 1,
                "plugin_active": True,
            }
            app.run()

        world = app.session_state["conference_day_simulation"]
        self.assertTrue(world["plugin_active"])
        self.assertEqual(world["last_talk_lead"], "sarah")
        self.assertTrue(world["run_id"])
        self.assertFalse(app.exception)

    def test_url_restores_demo_progress_without_serializing_followup_text(self):
        with patch(
            "conference_simulation.run_query_on_graph",
            side_effect=DatabaseError("unavailable"),
        ):
            source = self._open_simulation()
            source_world = source.session_state["conference_day_simulation"]
            source_world["phase"] = 4
            source_world["followup_text"] = "User-edited draft"
            source.run()
            serialized = source.query_params["ib_simulation"]

            self.assertNotIn("followup_text", serialized)
            restored = AppTest.from_file(str(APP_FILE), default_timeout=20)
            restored.query_params["ib_simulation"] = serialized
            restored.run()
            next(
                button
                for button in restored.button
                if button.label == "Conference day simulation"
            ).click().run()

        restored_world = restored.session_state["conference_day_simulation"]
        self.assertEqual(restored_world["phase"], 4)
        self.assertEqual(
            restored_world["followup_text"],
            simulation.new_simulation_state()["followup_text"],
        )
        self.assertFalse(restored.exception)

    def test_private_attendee_graph_node_contains_only_anonymous_token(self):
        world = simulation.new_simulation_state()
        world["private_badge"] = True
        world["backend"] = "FalkorDB"
        with patch("conference_simulation.run_query_on_graph") as graph_query:
            simulation._sync_graph(world)

        private_query = next(
            call
            for call in graph_query.call_args_list
            if "token:$token" in call.args[1]
        )
        self.assertEqual(
            private_query.args[2],
            {
                "sim_id": world["run_id"],
                "token": "Attendee #A-317",
                "sharing": True,
            },
        )
        self.assertNotIn("Dave", str(world))

    def test_guided_conference_day_stays_synchronized_through_completion(self):
        with patch(
            "conference_simulation.run_query_on_graph",
            side_effect=DatabaseError("unavailable"),
        ):
            app = self._open_simulation()

            next(
                toggle
                for toggle in app.toggle
                if toggle.label == "Enable the optional badge plugin"
            ).set_value(True).run()
            next(button for button in app.button if button.label == "Activate badges").click().run()
            next(button for button in app.button if button.label == "Next").click().run()

            next(button for button in app.button if button.label == "Share with exhibitors · Sarah").click().run()
            next(button for button in app.button if button.label == "Private mode · attendee").click().run()
            next(button for button in app.button if button.label == "Next").click().run()

            next(button for button in app.button if button.label == "Build today's target list").click().run()
            next(button for button in app.button if button.label == "Next").click().run()

            next(button for button in app.button if button.label == "Walk to Sarah Chen · simulated").click().run()
            next(button for button in app.button if button.label == "Connect").click().run()
            next(item for item in app.selectbox if item.label == "Phone user").set_value("Maya").run()
            next(button for button in app.button if button.label == "Walk to Sarah Chen · simulated").click().run()
            next(button for button in app.button if button.label == "Find another lead").click().run()
            next(button for button in app.button if button.label == "Walk to Tom Alvarez · simulated").click().run()
            next(button for button in app.button if button.label == "Next").click().run()

            next(button for button in app.button if button.label == "Walk to Attendee #A-317 · simulated").click().run()
            next(
                toggle
                for toggle in app.toggle
                if toggle.label == "Private badge is visible anonymously"
            ).set_value(False).run()
            next(button for button in app.button if button.label == "Next").click().run()

            next(button for button in app.button if button.label == "End talk with Sarah").click().run()
            next(button for button in app.button if button.label == "Save outcome").click().run()
            next(button for button in app.button if button.label == "Finish the conference day").click().run()

        world = app.session_state["conference_day_simulation"]
        self.assertTrue(world["run_complete"])
        self.assertEqual(world["talks_facilitated"], 1)
        self.assertEqual(world["collisions_stopped"], 1)
        self.assertTrue(world["followup_ready"])
        self.assertFalse(world["private_sharing"])
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()

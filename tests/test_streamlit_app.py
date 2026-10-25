import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


class StreamlitAppTests(unittest.TestCase):
    def _open_business_demo(self, app):
        next(button for button in app.button if button.label == "Business demo").click().run()
        return next(tab for tab in app.tabs if tab.label == "Phone app")

    def test_marketing_page_contains_ordered_anchor_sections_without_brand_kit(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        self.assertFalse(app.exception)

    def test_sidebar_uses_page_buttons_and_names_integrations(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        self.assertEqual(len(app.radio), 0)
        button_labels = [button.label for button in app.button]
        self.assertIn("Marketing", button_labels)
        self.assertIn("Conference setup", button_labels)
        self.assertIn("Business demo", button_labels)
        self.assertIn("Start the 90-second business demo", button_labels)
        self.assertIn("Try conference setup simulation", button_labels)
        self.assertNotIn("90-second demo", button_labels)
        self.assertNotIn("Phone prototype", button_labels)
        self.assertNotIn("Booth dashboard", button_labels)
        source = APP_FILE.read_text()
        self.assertIn("Inference Badge integrations", source)
        self.assertIn("FalkorDB", source)
        self.assertIn("Bright Data", source)
        self.assertIn(":material/event:", source)
        self.assertIn(".ib-integration-row .ib-icon", source)
        self.assertIn("width:17rem !important", source)
        self.assertIn(".ib-card h3", source)
        self.assertIn("box-shadow:none", source)

    def test_conference_setup_demo_leads_into_business_demo(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        next(button for button in app.button if button.label == "Conference setup").click().run()
        self.assertEqual(app.session_state["page"], "Conference setup")
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Add the plugin", rendered)
        self.assertIn("Connect the attendee list", rendered)
        self.assertIn("Let attendees choose", rendered)

        next(button for button in app.button if button.label == "See the business demo").click().run()
        self.assertEqual(app.session_state["page"], "Business demo")
        self.assertFalse(app.exception)

    def test_conference_setup_simulation_shows_attendee_choice_and_outcome(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        next(button for button in app.button if button.label == "Conference setup").click().run()
        next(button for button in app.button if button.label == "Preview attendee sign-up").click().run()
        self.assertIn(
            "I choose to share my badge with participating sales teams",
            [checkbox.label for checkbox in app.checkbox],
        )
        next(button for button in app.button if button.label == "Complete sample sign-up").click().run()
        alerts = "\n".join(item.value for item in app.success)
        self.assertIn("your demo badge appears on the participating team’s lead list", alerts)

        next(
            checkbox
            for checkbox in app.checkbox
            if checkbox.label == "I choose to share my badge with participating sales teams"
        ).set_value(False).run()
        next(button for button in app.button if button.label == "Complete sample sign-up").click().run()
        alerts = "\n".join(item.value for item in app.info)
        self.assertIn("You chose not to share", alerts)
        self.assertFalse(app.exception)

    def test_login_and_signup_pages_are_explicitly_coming_soon(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        next(button for button in app.button if button.label == "Log in · Coming soon").click().run()
        self.assertIn("Coming soon", "\n".join(item.value for item in app.markdown))
        self.assertIn("not enabled in this prototype", "\n".join(item.value for item in app.markdown))
        next(button for button in app.button if button.label == "Sign up · Coming soon").click().run()
        self.assertIn("Create your account", "\n".join(item.value for item in app.markdown))
        self.assertFalse(app.exception)

    def test_early_access_requires_consent_and_stores_opted_in_email(self):
        with patch("database.add_early_access_signup") as save_signup:
            app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
            next(button for button in app.button if button.label == "Notify me").click().run()
            self.assertIn("Please opt in", "\n".join(item.value for item in app.error))
            save_signup.assert_not_called()

            next(
                item
                for item in app.text_input
                if item.label == "Email address"
            ).set_value("attendee@example.com")
            next(
                item
                for item in app.checkbox
                if item.label.startswith("I agree to store this email")
            ).set_value(True)
            next(button for button in app.button if button.label == "Notify me").click().run()

        save_signup.assert_called_once_with("attendee@example.com")
        self.assertIn("You’re on the early-access list", "\n".join(item.value for item in app.success))
        self.assertFalse(app.exception)

    def test_business_demo_keeps_story_phone_and_booth_together(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        self._open_business_demo(app)
        tab_labels = [tab.label for tab in app.tabs]
        for label in ("90-second story", "Phone app", "Booth dashboard"):
            self.assertIn(label, tab_labels)
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("Phone prototype", rendered)
        self.assertIn("Team coverage at a glance", rendered)
        self.assertFalse(app.exception)

    def test_iconography_is_used_for_features_and_integrations(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        rendered = "\n".join(item.value for item in app.markdown)
        self.assertIn("ib-feature-heading", rendered)
        self.assertIn("<svg", rendered)
        self.assertFalse(app.exception)

    def test_dark_mode_has_complementary_colors_and_readable_surfaces(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        next(toggle for toggle in app.toggle if toggle.label == "Dark mode").set_value(True).run()

        styles = "\n".join(item.value for item in app.markdown)
        self.assertIn("#101827", styles)
        self.assertIn("#F3F4F6", styles)
        self.assertIn("#202E42", styles)
        self.assertIn(".ib-architecture-step", styles)
        self.assertIn("border:1px solid #E8CFE0", styles)
        self.assertIn("background:#FFF8FC", styles)
        self.assertIn("dark_mode", app.session_state)
        self.assertTrue(app.session_state["dark_mode"])
        self.assertFalse(app.exception)

        rendered = "\n".join(item.value for item in app.markdown)
        section_ids = (
            'id="hero"',
            'id="problem"',
            'id="how-it-works"',
            'id="features"',
            'id="story"',
            'id="for-sales-teams"',
            'id="for-organisers"',
            'id="privacy"',
            'id="faq"',
            'id="get-the-app"',
        )
        positions = [rendered.index(section_id) for section_id in section_ids]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("Brand kit", rendered)
        self.assertNotIn("Social share card", rendered)
        self.assertNotIn("Printed badge mockup", rendered)
        self.assertIn("Inference Badge", rendered)
        self.assertIn("#FF8AD6", rendered)
        self.assertFalse(app.exception)

    def test_completed_business_demo_links_to_conference_setup(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        next(button for button in app.button if "Business demo" in button.label).click().run()
        for _ in range(4):
            next(button for button in app.button if button.label == "Next").click().run()
        next(
            button
            for button in app.button
            if button.label == "Next · log the demo talk"
        ).click().run()
        next(button for button in app.button if button.label == "Conference setup").click().run()

        self.assertEqual(app.session_state["page"], "Conference setup")
        self.assertFalse(app.exception)

    def test_marketing_cta_opens_next_only_demo(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        self.assertFalse(app.exception)

        next(button for button in app.button if "Business demo" in button.label).click().run()
        self.assertEqual(app.session_state["page"], "Business demo")
        self.assertFalse(app.exception)

        for expected_step in range(2, 6):
            next(button for button in app.button if button.label == "Next").click().run()
            self.assertEqual(app.session_state["demo_state"]["step"], expected_step)
            self.assertFalse(app.exception)

        next(
            button
            for button in app.button
            if button.label == "Next · log the demo talk"
        ).click().run()
        self.assertTrue(app.session_state["demo_state"]["done"])

    def test_phone_prototype_renders_all_eight_screens(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        self._open_business_demo(app)

        self.assertFalse(app.exception)
        self.assertEqual(
            sum(tab.label in {
                "My Badge", "Nearby", "Lead Card", "Stop Card", "Join Card",
                "Private", "After-Talk", "My Day",
            } for tab in app.tabs),
            8,
        )

    def test_phone_privacy_off_hides_named_demo_lead_across_screens(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        phone_tab = self._open_business_demo(app)
        next(
            toggle for toggle in phone_tab.toggle
            if toggle.label == "Location sharing on this demo phone"
        ).set_value(False).run()

        phone_tab = next(tab for tab in app.tabs if tab.label == "Phone app")
        rendered_markdown = "\n".join(item.value for item in phone_tab.markdown)
        self.assertIn("Attendee (private)", rendered_markdown)
        self.assertNotIn("Sarah Demo", rendered_markdown)
        self.assertFalse(app.exception)

    def test_phone_empty_and_loading_previews_hide_attendee_details(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        phone_tab = self._open_business_demo(app)

        for state, expected in (
            ("Empty · no one nearby", "No one near you yet."),
            ("Loading · checking the list", "Checking the lead list…"),
        ):
            next(item for item in phone_tab.selectbox if item.label == "Preview state").set_value(state).run()
            phone_tab = next(tab for tab in app.tabs if tab.label == "Phone app")
            rendered_markdown = "\n".join(item.value for item in phone_tab.markdown)
            rendered_text = "\n".join(item.value for item in phone_tab.info)
            self.assertIn(expected, rendered_text)
            self.assertNotIn("Sarah Demo", rendered_markdown)
            self.assertFalse(app.exception)

    def test_phone_actions_update_only_session_preview(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=20).run()
        phone_tab = self._open_business_demo(app)
        next(button for button in phone_tab.button if button.label == "Pause sharing for 1 hour").click().run()
        self.assertFalse(app.session_state["phone_sharing"])
        phone_tab = next(tab for tab in app.tabs if tab.label == "Phone app")
        self.assertIn("no real timer", "\n".join(item.value for item in phone_tab.info))

        next(button for button in phone_tab.button if button.label == "Approve demo summary").click().run()
        self.assertTrue(app.session_state["phone_summary_approved"])
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()

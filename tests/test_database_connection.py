import os
import unittest
from unittest.mock import Mock, patch

import database


class DatabaseConnectionTests(unittest.TestCase):
    def setUp(self):
        database.get_graph.cache_clear()

    def tearDown(self):
        database.get_graph.cache_clear()

    def test_health_check_uses_verified_ipv4_default(self):
        graph = Mock()
        client = Mock()
        client.select_graph.return_value = graph

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(database, "FalkorDB", return_value=client) as create_client:
                self.assertEqual(database.health_check(), (True, "Connected"))

        create_client.assert_called_once()
        self.assertEqual(create_client.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(create_client.call_args.kwargs["port"], 6379)
        client.select_graph.assert_called_once_with("inference_badge")
        graph.query.assert_called_once_with("RETURN 1 AS ok", {})

    def test_early_access_signup_normalizes_email_and_uses_parameterized_query(self):
        with patch.object(database, "run_query") as run_query:
            database.add_early_access_signup("  Person@Example.COM ")

        query, params = run_query.call_args.args
        self.assertIn("MERGE (signup:EarlyAccessSignup {email:$email})", query)
        self.assertEqual(params["email"], "person@example.com")
        self.assertTrue(params["created_at"])

    def test_early_access_signup_rejects_invalid_email_before_database_write(self):
        with patch.object(database, "run_query") as run_query:
            with self.assertRaises(ValueError):
                database.add_early_access_signup("not-an-email")
        run_query.assert_not_called()


if __name__ == "__main__":
    unittest.main()

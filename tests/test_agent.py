from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from decision_resolution_agent.agent import ResolutionAgent
from decision_resolution_agent.database import Database
from decision_resolution_agent.dispatcher import ToolDispatcher
from decision_resolution_agent.tools import ResolutionTools


def function_response(name, arguments):
    return {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"functionCall": {"name": name, "args": arguments}}],
                }
            }
        ]
    }


def text_response(text):
    return {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": text}]}}
        ]
    }


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0
        self.contents_history = []

    def generate(self, contents, function_declarations, system_instruction):
        self.calls += 1
        self.contents_history.append(deepcopy(contents))
        return next(self.responses)


class ResolutionAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.db")
        self.database.initialize()
        self.tools = ResolutionTools(self.database)
        self.dispatcher = ToolDispatcher(self.tools)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lookup_and_inventory_return_structured_data(self):
        order = self.tools.lookup_order("DEMO-1001")
        stock = self.tools.check_inventory("SMART-SPEAKER")

        self.assertTrue(order["success"])
        self.assertTrue(order["order"]["exchange_eligible"])
        self.assertEqual(stock["quantity"], 3)
        self.assertTrue(stock["available"])

    def test_refund_is_rejected_when_replacement_is_available(self):
        result = self.tools.process_refund("DEMO-1001", "damaged")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "exchange_available")
        self.assertEqual(self.tools.lookup_order("DEMO-1001")["order"]["status"], "placed")

    def test_refund_is_processed_when_no_replacement_is_available(self):
        result = self.tools.process_refund("DEMO-1002", "damaged; no stock")

        self.assertTrue(result["success"])
        self.assertEqual(result["amount"], 149.50)
        self.assertEqual(self.tools.lookup_order("DEMO-1002")["order"]["status"], "refunded")

    def test_unknown_tool_and_malformed_arguments_are_rejected(self):
        unknown = self.dispatcher.dispatch("delete_everything", {})
        malformed = self.dispatcher.dispatch("lookup_order", {"order_id": 25})

        self.assertEqual(unknown["error"]["code"], "unknown_tool")
        self.assertEqual(malformed["error"]["code"], "invalid_arguments")

    def test_agent_exchanges_notifies_and_finishes_within_five_iterations(self):
        client = FakeClient(
            [
                function_response("lookup_order", {"order_id": "DEMO-1001"}),
                function_response("check_inventory", {"item_id": "SMART-SPEAKER"}),
                function_response(
                    "process_exchange",
                    {"order_id": "DEMO-1001", "reason": "arrived damaged"},
                ),
                function_response(
                    "send_notification",
                    {
                        "email": "alex@example.test",
                        "message": "Replacement confirmed. Reference EX-123.",
                    },
                ),
                text_response("A replacement has been reserved and a confirmation was recorded."),
            ]
        )
        agent = ResolutionAgent(client, self.dispatcher)

        result = agent.run("My Smart Speaker arrived damaged. Order DEMO-1001.")

        self.assertFalse(result["escalated"])
        self.assertEqual(result["iterations"], 5)
        self.assertEqual(client.calls, 5)
        self.assertTrue(any("functionResponse" in part for part in client.contents_history[-1][-1]["parts"]))
        self.assertEqual(self.tools.lookup_order("DEMO-1001")["order"]["status"], "exchanged")
        with self.database.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
        self.assertEqual(count, 1)

    def test_agent_refunds_when_eligible_item_is_out_of_stock(self):
        client = FakeClient(
            [
                function_response("lookup_order", {"order_id": "DEMO-1002"}),
                function_response("check_inventory", {"item_id": "BLUE-CHAIR"}),
                function_response(
                    "process_refund",
                    {"order_id": "DEMO-1002", "reason": "replacement unavailable"},
                ),
                function_response(
                    "send_notification",
                    {
                        "email": "jamie@example.test",
                        "message": "Refund confirmed. Reference RF-123.",
                    },
                ),
                text_response("The refund was processed and a confirmation was recorded."),
            ]
        )
        agent = ResolutionAgent(client, self.dispatcher)

        result = agent.run("My Blue Chair arrived damaged. Order DEMO-1002.")

        self.assertFalse(result["escalated"])
        self.assertEqual(result["iterations"], 5)
        self.assertEqual(self.tools.lookup_order("DEMO-1002")["order"]["status"], "refunded")
        self.assertEqual(self.tools.check_inventory("BLUE-CHAIR")["quantity"], 0)

    def test_agent_refunds_ineligible_order_without_checking_inventory(self):
        client = FakeClient(
            [
                function_response("lookup_order", {"order_id": "DEMO-1003"}),
                function_response(
                    "process_refund",
                    {"order_id": "DEMO-1003", "reason": "not exchange-eligible"},
                ),
                function_response(
                    "send_notification",
                    {
                        "email": "taylor@example.test",
                        "message": "Refund confirmed. Reference RF-456.",
                    },
                ),
                text_response("The refund was processed and a confirmation was recorded."),
            ]
        )
        agent = ResolutionAgent(client, self.dispatcher)

        result = agent.run("My Coffee Maker arrived damaged. Order DEMO-1003.")

        self.assertFalse(result["escalated"])
        self.assertEqual(result["iterations"], 4)
        self.assertEqual(self.tools.lookup_order("DEMO-1003")["order"]["status"], "refunded")
        self.assertNotIn(
            "check_inventory",
            [
                part["functionCall"]["name"]
                for content in client.contents_history
                for message in content
                for part in message.get("parts", [])
                if isinstance(part, dict) and "functionCall" in part
            ],
        )

    def test_missing_order_is_reported_without_crashing(self):
        client = FakeClient(
            [
                function_response("lookup_order", {"order_id": "NOT-REAL"}),
                text_response("I couldn't find that order. Please verify the order ID."),
            ]
        )
        agent = ResolutionAgent(client, self.dispatcher)

        result = agent.run("My order NOT-REAL arrived damaged.")

        self.assertIn("verify", result["response"])
        self.assertFalse(result["escalated"])

    def test_iteration_limit_escalates(self):
        client = FakeClient(
            [
                function_response("lookup_order", {"order_id": "DEMO-1001"}),
                function_response("check_inventory", {"item_id": "SMART-SPEAKER"}),
            ]
        )
        agent = ResolutionAgent(client, self.dispatcher, max_iterations=2)

        result = agent.run("My order DEMO-1001 arrived damaged.")

        self.assertTrue(result["escalated"])
        self.assertEqual(result["iterations"], 2)


if __name__ == "__main__":
    unittest.main()

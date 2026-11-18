"""Deterministic order, inventory, and resolution functions."""

import re
import uuid


def _failure(code, message):
    return {"success": False, "error": {"code": code, "message": message}}


class ResolutionTools:
    def __init__(self, database):
        self.database = database

    def lookup_order(self, order_id):
        with self.database.connection() as conn:
            row = conn.execute(
                """
                SELECT order_id, customer_name, email, item_id, item_name, total,
                       exchange_eligible, status
                FROM orders WHERE order_id = ?
                """,
                (order_id,),
            ).fetchone()
        if row is None:
            return _failure("order_not_found", "No order matches that identifier. Ask the customer to verify it.")
        order = dict(row)
        order["exchange_eligible"] = bool(order["exchange_eligible"])
        return {"success": True, "order": order}

    def check_inventory(self, item_id):
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT item_id, item_name, quantity FROM inventory WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return {
                "success": True,
                "item_id": item_id,
                "item_name": None,
                "quantity": 0,
                "available": False,
            }
        return {
            "success": True,
            "item_id": row["item_id"],
            "item_name": row["item_name"],
            "quantity": row["quantity"],
            "available": row["quantity"] > 0,
        }

    def process_exchange(self, order_id, reason):
        with self.database.transaction() as conn:
            order = conn.execute(
                "SELECT item_id, exchange_eligible, status FROM orders WHERE order_id = ?",
                (order_id,),
            ).fetchone()
            if order is None:
                return _failure("order_not_found", "No order matches that identifier.")
            if order["status"] != "placed":
                return _failure("already_resolved", "This order has already been resolved.")
            if not order["exchange_eligible"]:
                return _failure("exchange_ineligible", "This order is not eligible for an exchange.")
            reserved = conn.execute(
                "UPDATE inventory SET quantity = quantity - 1 WHERE item_id = ? AND quantity > 0",
                (order["item_id"],),
            )
            if reserved.rowcount != 1:
                return _failure("replacement_unavailable", "No replacement unit is currently available.")

            reference = "EX-" + uuid.uuid4().hex[:10].upper()
            conn.execute(
                "INSERT INTO exchanges (exchange_reference, order_id, item_id, reason) VALUES (?, ?, ?, ?)",
                (reference, order_id, order["item_id"], reason),
            )
            conn.execute("UPDATE orders SET status = 'exchanged' WHERE order_id = ?", (order_id,))
        return {
            "success": True,
            "order_id": order_id,
            "status": "exchanged",
            "exchange_reference": reference,
            "message": "A replacement has been reserved.",
        }

    def process_refund(self, order_id, reason):
        with self.database.transaction() as conn:
            order = conn.execute(
                """
                SELECT total, item_id, exchange_eligible, status
                FROM orders WHERE order_id = ?
                """,
                (order_id,),
            ).fetchone()
            if order is None:
                return _failure("order_not_found", "No order matches that identifier.")
            if order["status"] != "placed":
                return _failure("already_resolved", "This order has already been resolved.")
            if order["exchange_eligible"]:
                stock = conn.execute(
                    "SELECT quantity FROM inventory WHERE item_id = ?",
                    (order["item_id"],),
                ).fetchone()
                if stock is not None and stock["quantity"] > 0:
                    return _failure(
                        "exchange_available",
                        "An eligible replacement is in stock. Process an exchange instead.",
                    )

            reference = "RF-" + uuid.uuid4().hex[:10].upper()
            conn.execute(
                "INSERT INTO refunds (refund_reference, order_id, amount, reason) VALUES (?, ?, ?, ?)",
                (reference, order_id, order["total"], reason),
            )
            conn.execute("UPDATE orders SET status = 'refunded' WHERE order_id = ?", (order_id,))
        return {
            "success": True,
            "order_id": order_id,
            "status": "refunded",
            "amount": order["total"],
            "refund_reference": reference,
        }

    def send_notification(self, email, message):
        with self.database.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO notifications (email, message) VALUES (?, ?)",
                (email, message),
            )
            notification_id = cursor.lastrowid
        return {
            "success": True,
            "notification_id": notification_id,
            "email": email,
            "delivery": "simulated",
        }

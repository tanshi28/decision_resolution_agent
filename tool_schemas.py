"""Function declarations passed to the Gemini API."""

TOOL_SCHEMAS = [
    {
        "name": "lookup_order",
        "description": "Retrieve the customer, item, order status, total, and exchange eligibility for an order. Always do this first.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "order_id": {
                    "type": "STRING",
                    "description": "The customer's order identifier.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "check_inventory",
        "description": "Read current warehouse stock for the item's identifier before choosing an exchange or refund.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_id": {
                    "type": "STRING",
                    "description": "The item identifier returned by lookup_order.",
                },
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "process_exchange",
        "description": "Reserve one in-stock replacement and exchange an eligible order. Use only when exchange eligibility is true and stock is available.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "order_id": {
                    "type": "STRING",
                    "description": "The order identifier returned by lookup_order.",
                },
                "reason": {
                    "type": "STRING",
                    "description": "Short reason for the exchange, such as 'item arrived damaged'.",
                },
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "name": "process_refund",
        "description": "Issue a refund for an order only when it is not exchange-eligible or no replacement is in stock. The application rejects refunds when an eligible replacement is available.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "order_id": {
                    "type": "STRING",
                    "description": "The order identifier returned by lookup_order.",
                },
                "reason": {
                    "type": "STRING",
                    "description": "Short reason for the refund, such as 'no replacement available'.",
                },
            },
            "required": ["order_id", "reason"],
        },
    },
    {
        "name": "send_notification",
        "description": "Record dispatch of a simulated customer email after a successful resolution. Include the outcome and transaction reference in the message.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "email": {
                    "type": "STRING",
                    "description": "Customer email address returned by lookup_order.",
                },
                "message": {
                    "type": "STRING",
                    "description": "Clear confirmation of the resolution and its reference.",
                },
            },
            "required": ["email", "message"],
        },
    },
]


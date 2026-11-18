"""Whitelist-based tool dispatch and basic argument validation."""

import logging
import re
import sqlite3

from .tool_schemas import TOOL_SCHEMAS
from .tools import ResolutionTools

logger = logging.getLogger(__name__)


class ToolDispatcher:
    def __init__(self, tools):
        self.registry = {
            "lookup_order": tools.lookup_order,
            "check_inventory": tools.check_inventory,
            "process_exchange": tools.process_exchange,
            "process_refund": tools.process_refund,
            "send_notification": tools.send_notification,
        }
        self.schemas = {schema["name"]: schema for schema in TOOL_SCHEMAS}

    def dispatch(self, name, arguments):
        if not isinstance(name, str):
            name = ""
        function = self.registry.get(name)
        schema = self.schemas.get(name)
        if function is None or schema is None:
            return {
                "success": False,
                "error": {"code": "unknown_tool", "message": "That tool is not authorized."},
            }
        if not isinstance(arguments, dict):
            return {
                "success": False,
                "error": {"code": "invalid_arguments", "message": "Tool arguments must be a JSON object."},
            }

        properties = schema["parameters"]["properties"]
        required = schema["parameters"]["required"]
        missing = [key for key in required if key not in arguments]
        extra = [key for key in arguments if key not in properties]
        if missing or extra:
            details = []
            if missing:
                details.append("Missing required argument(s): " + ", ".join(missing) + ".")
            if extra:
                details.append("Unexpected argument(s): " + ", ".join(extra) + ".")
            return {
                "success": False,
                "error": {"code": "invalid_arguments", "message": " ".join(details)},
            }

        cleaned = {}
        for key, value in arguments.items():
            if not isinstance(value, str) or not value.strip():
                return {
                    "success": False,
                    "error": {
                        "code": "invalid_arguments",
                        "message": "Argument '{}' must be a non-empty string.".format(key),
                    },
                }
            cleaned[key] = value.strip()
            if key == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cleaned[key]):
                return {
                    "success": False,
                    "error": {"code": "invalid_arguments", "message": "A valid email address is required."},
                }
        if "message" in cleaned and len(cleaned["message"]) > 2000:
            return {
                "success": False,
                "error": {"code": "invalid_arguments", "message": "Message must be 2000 characters or fewer."},
            }

        try:
            return function(**cleaned)
        except sqlite3.Error:
            logger.exception("Database error while running tool %s", name)
            return {
                "success": False,
                "error": {"code": "storage_error", "message": "The database operation failed. Please try again."},
            }

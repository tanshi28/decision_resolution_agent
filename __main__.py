"""Run the customer resolution agent from the command line."""

import logging

from .agent import ResolutionAgent
from .database import Database
from .dispatcher import ToolDispatcher
from .gemini_client import GeminiAPIError, GeminiClient
from .tools import ResolutionTools


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    database = Database()
    database.initialize()
    try:
        client = GeminiClient()
        request = input("Describe the damaged-item issue (include the order ID): ").strip()
        if not request:
            print("Please enter a customer issue.")
            return
        agent = ResolutionAgent(client, ToolDispatcher(ResolutionTools(database)))
        result = agent.run(request)
        print("\n" + result["response"])
        if result["escalated"]:
            print("\nStatus: escalated for human review.")
    except (GeminiAPIError, EOFError, KeyboardInterrupt) as exc:
        print("\nUnable to complete the request: {}".format(exc))


if __name__ == "__main__":
    main()

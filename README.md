# Decision Resolution Agent

A Python ReAct agent that investigates damaged-item orders and chooses an exchange or refund. It
uses Google's Gemini API (not Groq), a local SQLite database, JSON function declarations, and a
whitelist dispatcher. No third-party Python packages are required.

## Requirements and setup

- Python 3.10+
- A Gemini API key from Google AI Studio

In PowerShell, set the key for the current terminal:

```powershell
$env:GEMINI_API_KEY = "your-key"
python -m decision_resolution_agent
```

Run the command from the directory containing the `decision_resolution_agent` folder. Optionally
set `GEMINI_MODEL` to choose another available Gemini model, or `AGENT_DB_PATH` to choose another
SQLite database file. The default model is `gemini-3.8-flash`. The default database is created
beside this README.

The demo seeds three orders:

| Order ID | Eligibility | Inventory | Expected resolution |
| --- | --- | --- | --- |
| `DEMO-1001` | Eligible | 3 Smart Speakers | Exchange |
| `DEMO-1002` | Eligible | 0 Blue Chairs | Refund |
| `DEMO-1003` | Not eligible | 2 Coffee Makers | Refund |

Try a request such as: `My Smart Speaker arrived damaged. Order DEMO-1001.`

## Tool loop and guardrails

- `tool_schemas.py` defines Gemini function contracts.
- `dispatcher.py` rejects unknown tools, malformed arguments, and unauthorized fields.
- `tools.py` implements structured order lookup, inventory, exchange, refund, and notification
  actions. Exchange/refund logic is transactionally guarded in SQLite; an eligible order with an
  available replacement cannot be refunded.
- `agent.py` retains ordered user/model/tool history and stops after at most five model turns.
- Temporary Gemini rate-limit and server errors are retried up to three times with backoff.
- Invalid orders and tool errors are returned to the model as structured results. If the limit is
  reached, the agent halts and requests human review.

Notifications are recorded as `simulated` in SQLite; this project does not send actual email or
move real money or inventory.

## Tests

From the directory containing the package:

```powershell
python -m unittest discover -s decision_resolution_agent\tests -v
```

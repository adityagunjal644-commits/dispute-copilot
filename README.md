# AI Dispute Copilot

An AI assistant for merchants that handles PayPal disputes. It pulls the case from PayPal, gathers evidence, checks the evidence for contradictions, recommends a response, stress-tests its own recommendation, and sends the reply back through PayPal only after a human approves (or within guardrails the merchant sets).

Built for the PayPal AI Hackathon. Created during the submission period (started 31 Oct 2026). Sandbox data only, no real money.

## Live demo

- URL: https://dispute-copilot-wx2h.onrender.com
- Passcode: provided in the Devpost testing instructions
- The first load can take up to a minute, because the free hosting tier sleeps when idle.

## What it does

- **Dispute queue (AG Grid):** a live PayPal sandbox case plus demo cases, sorted by response deadline with colored countdown chips.
- **AI recommendation:** fight, offer a refund, or accept, with a confidence score, the evidence used, and an editable draft reply.
- **Buyer's lawyer stress test:** a second AI pass attacks the draft as the buyer's lawyer. Confidence drops by a fixed amount by severity (low 0%, medium 10%, high 20%), and the draft is rewritten.
- **Evidence Integrity and Contradiction Engine:** plain code (no AI) that cross-checks the evidence for date mismatches, status versus tracking-number mismatches, weak delivery proof, a dispute filed before delivery, and amount mismatches. Findings reduce confidence (capped at 25%). High-severity findings force human review and block autopilot.
- **What-if scenario simulator:** compares Fight, Partial refund (adjustable offer and chance the buyer accepts), Full refund, and Wait and collect evidence. It uses the real response deadline, a cost per day of waiting, and the AI's list of missing evidence. It says "too close to call" when the best options are within $2 or 10% of the amount.
- **Autopilot with guardrails:** the merchant sets a max amount, a minimum confidence and the allowed strategies. Safe cases are handled automatically. Everything else is escalated to a human with the exact reason.
- **Human approval:** nothing is sent to PayPal until the merchant presses Approve (or autopilot passes every guardrail).
- **Audit log and impact cards:** every AI decision, autopilot action and approval is recorded.
- **Passcode lock** on the hosted demo.

## How it works

1. Fetch disputes from the PayPal sandbox and show them in the queue.
2. Gather evidence (PayPal transaction data for real cases, sample store records for demo cases).
3. Run the integrity engine to find contradictions.
4. Gemini recommends a strategy and writes a draft reply.
5. A second Gemini pass stress-tests the recommendation as the buyer's lawyer.
6. The merchant explores options in the simulator.
7. The merchant approves, or autopilot acts if every guardrail passes.
8. The action is written to the audit log.

## PayPal APIs used

- OAuth 2.0 (client credentials)
- **Disputes API:** list disputes, get dispute details, send a message to the buyer (inquiries)
- **Transaction Search (Reporting) API:** real payment details used as evidence
- **Tracking API (optional):** add and read shipment tracking. Built, but only lightly tested in the sandbox.

## AI

- Google Gemini via the `google-genai` SDK. Two calls per case: the recommendation, then the stress test. Models fall back automatically if one fails, and each call has a timeout.
- Confidence is capped at 0.9, and cases under 0.7 are flagged for human review.

## Sponsor tools

- **AG Grid Community:** dispute queue and audit log
- **Render:** hosting

## What is real and what is simulated

- **Real:** the PayPal sandbox payment, dispute, transaction record and the reply sent back; the Gemini recommendations and drafts; the integrity checks and guardrails.
- **Simulated:** merchant shipping and delivery records (`evidence.py`, `demo_data.py`) and the 6 demo disputes. Demo cases are never sent to PayPal.
- **Simulated:** courier tracking on one demo case (DEMO-1006), built to show the integrity engine catching a contradiction.
- **Assumption:** "time saved" uses 25 minutes of manual work per case. It is not a measurement.
- Win probability and confidence are AI estimates, not statistics.

## Run it locally

Requirements: Python 3.11+, a PayPal developer account (sandbox), a Gemini API key.

```
git clone https://github.com/adityagunjal644-commits/dispute-copilot.git
cd dispute-copilot
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a file named `.env` in the project folder:

```
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_secret
GEMINI_API_KEY=your_gemini_key
APP_PASSCODE=optional_passcode
```

Run:

```
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000. Without PayPal keys, only the demo cases load. The Gemini key is required. To get a live case, create a sandbox Business and Personal account (US), pay between them as goods or services, and open "Report a problem" as the buyer.

## Deploy on Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `GEMINI_API_KEY`, `APP_PASSCODE`, `PYTHON_VERSION=3.12.3`

## Project structure

- `main.py`: FastAPI backend, passcode lock, autopilot, audit log
- `paypal_client.py`: PayPal API calls
- `ai_draft.py`: AI recommendation and stress test
- `integrity.py`: evidence contradiction checks (code only, no AI)
- `evidence.py`, `real_evidence.py`, `demo_data.py`: merchant records, PayPal evidence, demo cases
- `static/index.html`: dashboard (queue, simulator, integrity panel, audit log)
- `openapi.json`: API description

## License

MIT

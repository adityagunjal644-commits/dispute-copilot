# AI Dispute Copilot

An AI assistant for merchants that handles PayPal disputes: it pulls the case from PayPal, gathers evidence, recommends a response, stress-tests its own recommendation, and sends the reply back through PayPal only after a human approves (or within guardrails the merchant sets).

Built for the PayPal AI Hackathon. Created during the submission period (started 31 Oct 2026). Sandbox data only, no real money.

## Live demo

- URL: `<your-render-url>`
- Passcode: provided in the Devpost testing instructions
- The first load can take up to a minute, because the free hosting tier sleeps when idle.

## What it does

- **Dispute queue (AG Grid):** live PayPal sandbox case plus demo cases, sorted by response deadline with colored countdown chips.
- **AI recommendation:** fight, offer a refund, or accept, with a confidence score, the evidence used, and an editable draft reply.
- **Buyer's lawyer stress test:** a second AI pass attacks the draft as the buyer's lawyer. Confidence drops by a fixed amount by severity (low 0%, medium 10%, high 20%), and the draft is rewritten.
- **Fight or fold calculator:** compares the certain loss from refunding with the expected loss from fighting, using adjustable time cost and fees. It says "too close to call" when the gap is small.
- **Autopilot with guardrails:** the merchant sets a max amount, a minimum confidence and the allowed strategies. Safe cases are handled automatically. Everything else is escalated to a human with the exact reason.
- **Human approval:** nothing is sent to PayPal until the merchant presses Approve (or autopilot passes every guardrail).
- **Audit log and impact cards:** every AI decision, autopilot action and approval is recorded.
- **Passcode lock** on the hosted demo.

## PayPal APIs used

- OAuth 2.0 (client credentials)
- **Disputes API:** list disputes, get dispute details, send message to the buyer
- **Transaction Search (Reporting) API:** real payment details used as evidence

## AI

- Google Gemini via the `google-genai` SDK. Two calls per case: the recommendation, then the stress test. Models fall back automatically if one fails.

## Sponsor tools

- **AG Grid Community:** dispute queue and audit log
- **Render:** hosting

## What is real and what is simulated

- **Real:** the PayPal sandbox payment, dispute, transaction record and the reply sent back.
- **Simulated:** merchant shipping and delivery records (`evidence.py`, `demo_data.py`) and the 5 demo disputes. Demo cases are never sent to PayPal.
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

## Project structure

- `main.py`: FastAPI backend, autopilot, audit log
- `paypal_client.py`: PayPal API calls
- `ai_draft.py`: AI recommendation and stress test
- `evidence.py`, `real_evidence.py`, `demo_data.py`: merchant records, PayPal evidence, demo cases
- `static/index.html`: dashboard

## License

MIT
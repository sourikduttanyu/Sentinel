# Setup Guide

Full instructions for running Sentinel on your own repositories.

## Prerequisites

- Python 3.11+
- [ngrok](https://ngrok.com) (for local development)
- A GitHub account
- An [Anthropic API key](https://console.anthropic.com)
- A [LangSmith account](https://smith.langchain.com) (free)

---

## Step 1 — Clone and install

```bash
git clone https://github.com/sourikduttanyu/Sentinel
cd Sentinel
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

---

## Step 2 — Start ngrok

Sentinel needs a public URL so GitHub can deliver webhooks to your local server.

```bash
ngrok http 8000
```

Copy the `https://....ngrok-free.app` URL. You will need it in the next step.

---

## Step 3 — Create a GitHub App

1. Go to `github.com/settings/apps/new`
2. Fill in:
   - **Name:** anything unique (e.g. `my-sentinel`)
   - **Homepage URL:** `http://localhost:8000`
   - **Webhook URL:** `https://YOUR-NGROK-URL/webhook`
   - **Webhook secret:** generate one and save it
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
3. Under **Repository permissions:**
   - Pull requests → **Read & Write**
   - Contents → **Read-only**
4. Under **Subscribe to events:** check **Pull request**
5. Click **Create GitHub App**

After creation, note your **App ID** from the app settings page.

---

## Step 4 — Generate a private key

On the app settings page, scroll to **Private keys** → **Generate a private key**.

Move the downloaded `.pem` file into the project:

```bash
mkdir -p keys
mv ~/Downloads/*.pem keys/sentinel.pem
chmod 600 keys/sentinel.pem
```

---

## Step 5 — Install the app on a repository

1. App settings page → left sidebar → **Install App**
2. Click **Install** → select the repository you want Sentinel to review
3. After install, note the **Installation ID** from the URL:
   `github.com/settings/installations/XXXXXXXX`

---

## Step 6 — Fill in `.env`

```
GITHUB_APP_ID=<your app id>
GITHUB_APP_PRIVATE_KEY_PATH=./keys/sentinel.pem
GITHUB_WEBHOOK_SECRET=<secret from step 3>
GITHUB_INSTALLATION_ID=<installation id from step 5>

ANTHROPIC_API_KEY=<from console.anthropic.com>

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<from smith.langchain.com>
LANGCHAIN_PROJECT=sentinel
```

---

## Step 7 — Run Sentinel

```bash
python main.py
```

---

## Step 8 — Test it

Open a pull request on the repository you installed the app on. You should see output in the server terminal:

```
[Webhook] PR #1 opened on your-username/your-repo
[SecurityAgent] running Semgrep...
[DocsAgent] analyzing diff...
[SupervisorAgent] review generated
[Metrics] approve via: curl -X POST http://localhost:8000/approve/{run_id}
```

Approve the review to post the comment on GitHub:

```bash
curl -X POST http://localhost:8000/approve/{run_id}
```

---

## Notes

- ngrok free tier generates a new URL on every restart. If you restart ngrok, update the webhook URL in your GitHub App settings.
- The `keys/` directory and `.env` file are in `.gitignore` — they will never be committed.
- LangSmith traces appear at `smith.langchain.com` under the `sentinel` project after each run.

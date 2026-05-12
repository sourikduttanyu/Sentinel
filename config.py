import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_APP_ID = os.environ["GITHUB_APP_ID"]
GITHUB_APP_PRIVATE_KEY_PATH = os.environ["GITHUB_APP_PRIVATE_KEY_PATH"]
GITHUB_WEBHOOK_SECRET = os.environ["GITHUB_WEBHOOK_SECRET"]
GITHUB_INSTALLATION_ID = os.environ["GITHUB_INSTALLATION_ID"]

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# LLM_BACKEND: "anthropic" | "gemini" | "openai"
LLM_BACKEND = os.getenv("LLM_BACKEND", "anthropic")

# LLM_MODEL: model name for the chosen backend.
# Defaults: anthropic → claude-haiku-4-5-20251001
#           gemini    → gemini-2.0-flash
#           openai    → gpt-4o-mini
LLM_MODEL = os.getenv("LLM_MODEL", "")

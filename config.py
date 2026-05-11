import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_APP_ID = os.environ["GITHUB_APP_ID"]
GITHUB_APP_PRIVATE_KEY_PATH = os.environ["GITHUB_APP_PRIVATE_KEY_PATH"]
GITHUB_WEBHOOK_SECRET = os.environ["GITHUB_WEBHOOK_SECRET"]
GITHUB_INSTALLATION_ID = os.environ["GITHUB_INSTALLATION_ID"]

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_BACKEND = os.getenv("LLM_BACKEND", "anthropic")  # "anthropic" or "gemini"

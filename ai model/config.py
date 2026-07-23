import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    MAX_CONVERSATION_MESSAGES = int(
        os.getenv("MAX_CONVERSATION_MESSAGES", "500")
    )
    MAX_TEXT_LENGTH = int(
        os.getenv("MAX_TEXT_LENGTH", "50000")
    )

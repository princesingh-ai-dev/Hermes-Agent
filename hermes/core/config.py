# hermes/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", r"C:\Users\PRINCE SINGH\Documents\ObsidianVault")

HERMES_HOST = os.getenv("HERMES_HOST", "0.0.0.0")
HERMES_PORT = int(os.getenv("HERMES_PORT", "3737"))
HERMES_DEFAULT_TASK = os.getenv("HERMES_DEFAULT_TASK", "auto")
HERMES_MEMORY_PATH = os.getenv("HERMES_MEMORY_PATH", "./hermes_memory")
HERMES_CHECKPOINT_DB = os.getenv("HERMES_CHECKPOINT_DB", "./hermes_checkpoints.db")

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for directory in [DATA_DIR, EXPORTS_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# API Keys (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


class TextToSQLConfig:
    """All settings for text-to-sql module - ISOLATED"""
    LLM_PROVIDER = "ollama"  # "ollama" or "openai"
    OLLAMA_MODEL = "llama3.1:8b"
    OPENAI_MODEL = "gpt-3.5-turbo"
    
    # Database - separate from other modules
    SAMPLE_DB_PATH = DATA_DIR / "sample_db" / "demo.db"
    EXPORT_DIR = EXPORTS_DIR / "sql_queries"
    
    # Query settings
    MAX_QUERY_LENGTH = 1000
    TIMEOUT_SECONDS = 30
    
    @classmethod
    def initialize(cls):
        cls.SAMPLE_DB_PATH.parent.mkdir(exist_ok=True)
        cls.EXPORT_DIR.mkdir(exist_ok=True)


class GUIConfig:
    """All settings for GUI - ISOLATED"""
    THEME = "dark"  # "dark" or "light"
    COLOR_PRIMARY = "#1f6aa5"
    COLOR_ACCENT = "#2fa572"
    COLOR_ERROR = "#d32f2f"
    COLOR_SUCCESS = "#4caf50"
    
    WINDOW_TITLE = "SchemaVaultLocal"
    WINDOW_WIDTH = 1360
    WINDOW_HEIGHT = 860
    
    # Tab names - must match implementation
    TAB_TEXT_TO_SQL = "Text to SQL"


def initialize_all_configs():
    """Call this once at application startup"""
    TextToSQLConfig.initialize()

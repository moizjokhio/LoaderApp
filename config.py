"""
Configuration and constants for EduParser application
"""

# App Settings
APP_TITLE = "EduParser"
APP_ICON = "🎓"
APP_LAYOUT = "wide"

# Page Names
PAGE_DOCUMENT_PARSER = "Document Parser"
PAGE_SPREADSHEET_LOADER = "Spreadsheet Loader"
PAGE_EXPERIENCE_PARSER = "Experience Parser"
PAGE_SETTINGS = "Settings"

# Model Settings
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
DEFAULT_TEMPERATURE = 0.05

# Environment Variable Names
ENV_API_KEY_PRIMARY = "GROQ_API_KEY"
ENV_API_KEY_2 = "GROQ_API_KEY_2"
ENV_API_KEY_3 = "GROQ_API_KEY_3"

# Session State Keys
SESSION_API_KEYS = "groq_api_keys"
SESSION_RESULTS = "results_df"
SESSION_PROCESSED_FILES = "processed_files"
SESSION_CV_RESULTS = "cv_results"

# OCR Settings
OCR_DPI = 300
OCR_MIN_TEXT_LENGTH = 50
OCR_LANGUAGE = 'eng'

"""Configuration settings for the Vaalilakanabot."""

import os
from typing import Optional

# Bot configuration
TOKEN: str = os.environ["VAALILAKANABOT_TOKEN"]
ADMIN_CHAT_ID: int = int(os.environ["ADMIN_CHAT_ID"])
BASE_URL: str = os.environ["BASE_URL"]

# Google Sheets configuration
GOOGLE_SHEET_URL: str = os.environ["GOOGLE_SHEET_URL"]
# Use a fixed credentials file name; keep it out of version control
GOOGLE_CREDENTIALS_FILE: str = "google_credentials.json"

# Discourse / Fiirumi configuration
TOPIC_LIST_URL: str = os.environ["TOPIC_LIST_URL"]
QUESTION_LIST_URL: str = os.environ["QUESTION_LIST_URL"]
API_KEY: str = os.environ["API_KEY"]
API_USERNAME: str = os.environ["API_USERNAME"]
VAALILAKANA_POST_URL: str = os.environ["VAALILAKANA_POST_URL"]

# Election year for automatic area generation (optional)
# If set and matches current year, bot will auto-generate Discourse categories
_election_year_raw: Optional[str] = os.environ.get("ELECTION_YEAR")
ELECTION_YEAR: Optional[int] = None
if _election_year_raw:
    try:
        ELECTION_YEAR = int(_election_year_raw)
    except ValueError:
        pass

# Conversation states
SELECTING_DIVISION: str = "SELECTING_DIVISION"
SELECTING_ROLE: str = "SELECTING_ROLE"
CONFIRMING_APPLICATION: str = "CONFIRMING_APPLICATION"
AWAITING_ADMIN_APPROVAL: str = "AWAITING_ADMIN_APPROVAL"

# Register conversation states
REGISTER_NAME: str = "REGISTER_NAME"
REGISTER_EMAIL: str = "REGISTER_EMAIL"
REGISTER_CONSENT: str = "REGISTER_CONSENT"

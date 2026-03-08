"""Configuration settings for the Vaalilakanabot."""

import os
from typing import List, Optional

# Bot configuration
TOKEN: str = os.environ["VAALILAKANABOT_TOKEN"]
ADMIN_CHAT_ID: int = int(os.environ["ADMIN_CHAT_ID"])
BASE_URL: str = os.environ["BASE_URL"].rstrip("/")

# Google Sheets configuration
GOOGLE_SHEET_URL: str = os.environ["GOOGLE_SHEET_URL"]
# Use a fixed credentials file name; keep it out of version control
GOOGLE_CREDENTIALS_FILE: str = "google_credentials.json"

# Discourse / Fiirumi configuration
API_KEY: str = os.environ["API_KEY"]
API_USERNAME: str = os.environ["API_USERNAME"]

# Election year for automatic area generation (required)
# Set to the current election year. The bot auto-generates Discourse categories,
# creates the election sheet topic, and derives all Fiirumi URLs from this.
ELECTION_YEAR: str = os.environ["ELECTION_YEAR"]

# Set by fiirumi_area_generator after finding/creating the election sheet topic.
# A list is used so the setter can mutate it without a global statement.
_generated_vaalilakana_post_url: List[Optional[str]] = [None]


def get_topic_list_url() -> str:
    """Return the introductions category JSON URL, derived from ELECTION_YEAR."""
    return f"{BASE_URL}/c/vaalipeli-{ELECTION_YEAR}/esittelyt/l/latest.json"


def get_question_list_url() -> str:
    """Return the questions category JSON URL, derived from ELECTION_YEAR."""
    return f"{BASE_URL}/c/vaalipeli-{ELECTION_YEAR}/kysymykset/l/latest.json"


def get_vaalilakana_post_url() -> Optional[str]:
    """Return the election sheet post URL set by the area generator, or None if not yet generated."""
    return _generated_vaalilakana_post_url[0]


def set_generated_vaalilakana_post_url(url: str) -> None:
    """Set the election sheet post URL. Called from fiirumi_area_generator."""
    _generated_vaalilakana_post_url[0] = url


# Conversation states
SELECTING_DIVISION: str = "SELECTING_DIVISION"
SELECTING_ROLE: str = "SELECTING_ROLE"
CONFIRMING_APPLICATION: str = "CONFIRMING_APPLICATION"

# Register conversation states
REGISTER_NAME: str = "REGISTER_NAME"
REGISTER_EMAIL: str = "REGISTER_EMAIL"
REGISTER_CONSENT: str = "REGISTER_CONSENT"

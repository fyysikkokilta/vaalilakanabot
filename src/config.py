"""Configuration settings for the Vaalilakanabot."""

import os

# Bot configuration
TOKEN = os.environ["VAALILAKANABOT_TOKEN"]
ADMIN_CHAT_ID = os.environ["ADMIN_CHAT_ID"]
BASE_URL = os.environ["BASE_URL"]

# Google Sheets configuration
GOOGLE_SHEET_URL = os.environ["GOOGLE_SHEET_URL"]
# Use a fixed credentials file name; keep it out of version control
GOOGLE_CREDENTIALS_FILE = "google_credentials.json"

# Discourse / Fiirumi configuration
TOPIC_LIST_URL = os.environ["TOPIC_LIST_URL"]
QUESTION_LIST_URL = os.environ["QUESTION_LIST_URL"]
API_KEY = os.environ["API_KEY"]
API_USERNAME = os.environ["API_USERNAME"]
VAALILAKANA_POST_URL = os.environ["VAALILAKANA_POST_URL"]

# Conversation states
SELECTING_DIVISION = "SELECTING_DIVISION"
SELECTING_ROLE = "SELECTING_ROLE"
GIVING_NAME = "GIVING_NAME"
GIVING_EMAIL = "GIVING_EMAIL"
CONFIRMING_APPLICATION = "CONFIRMING_APPLICATION"
AWAITING_ADMIN_APPROVAL = "AWAITING_ADMIN_APPROVAL"

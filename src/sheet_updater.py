"""Update the election sheet in Fiirumi."""

from datetime import datetime
from typing import List
import requests
from telegram.ext import ContextTypes

from .sheets_data_manager import DataManager
from .types import DivisionData
from .config import API_KEY, API_USERNAME, VAALILAKANA_POST_URL

YEAR = datetime.now().year


def data_to_markdown(data: List[DivisionData]) -> str:
    """Convert data to markdown."""
    # Start building the markdown
    text = f"# VAALILAKANA {YEAR} / ELECTION SHEET {YEAR}\n\n"

    # Iterate over each division
    for division_data in data:
        division_name = division_data.get("Division_FI")
        division_name_en = division_data.get("Division_EN")

        # Add division header
        text += f"### {division_name} / {division_name_en}\n\n"

        # Iterate over each role in the division
        for role_data in division_data.get("Roles", []):
            role_title = role_data.get("Role_FI")
            role_title_en = role_data.get("Role_EN")
            role_amount = role_data.get("Amount")
            role_application_dl = role_data.get("Deadline")
            role_applicants = role_data.get("Applicants", [])
            role_tag = None

            # Determine if the role is a board role or official role
            if role_data.get("Type") == "BOARD":
                role_tag = "**"
            elif role_data.get("Type") in ("ELECTED", "AUDITOR"):
                role_tag = "*"

            role_row = ""
            if role_tag:
                role_row += role_tag
            role_row += f"{role_title} / {role_title_en}"
            if role_amount:
                role_row += f" ({role_amount})"
            if role_application_dl:
                role_row += f" {role_application_dl}"
            if role_tag:
                role_row += role_tag
            role_row += "\n"
            text += role_row

            # Add applicants list
            if len(role_applicants) > 0:
                text += "\n"
                for applicant in role_applicants:
                    applicant_name = applicant.get("Name")
                    if applicant.get("Status") == "ELECTED":
                        text += f"* **{applicant_name}**\n"
                    else:
                        text += f"* {applicant_name}\n"
                text += "\n"

            text += "\n"

        text += "—\n\n"

    return text


async def update_election_sheet(
    _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Update the election sheet in the Guild website."""
    # Get full data from Google Sheets (includes non-elected roles)
    try:
        vaalilakana_data = data_manager.vaalilakana_full
    except Exception as e:
        print("Error getting data from Google Sheets: %s", e)
        return None

    # Convert data to markdown
    text = data_to_markdown(vaalilakana_data)

    headers = {
        "Api-Key": API_KEY,
        "Api-Username": API_USERNAME,
        "Content-Type": "application/json",
    }

    payload = {
        "raw": text,
    }

    return requests.put(
        VAALILAKANA_POST_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

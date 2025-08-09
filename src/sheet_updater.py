"""Update the election sheet in Fiirumi."""

from datetime import datetime
from typing import Dict
import requests
from telegram.ext import ContextTypes

from .sheets_data_manager import DataManager, DivisionData
from .config import API_KEY, API_USERNAME, VAALILAKANA_POST_URL

YEAR = datetime.now().year


def data_to_markdown(data: Dict[str, DivisionData]) -> str:
    """Convert data to markdown."""
    # Start building the markdown
    text = f"# VAALILAKANA {YEAR} / ELECTION SHEET {YEAR}\n\n"

    # Iterate over each division
    for division_data in data.values():
        division_name = division_data["division"]
        division_name_en = division_data["division_en"]

        # Add division header
        text += f"### {division_name} / {division_name_en}\n\n"

        # Iterate over each role in the division
        for role_data in division_data["roles"].values():
            role_title = role_data["title"]
            role_title_en = role_data["title_en"]
            role_amount = role_data["amount"]
            role_application_dl = role_data["application_dl"]
            role_applicants = role_data["applicants"]

            # Determine if the role is a board role or official role
            if role_data.get("type") == "BOARD":
                role_tag = "**"
            elif role_data.get("type") in ("ELECTED", "AUDITOR"):
                role_tag = "*"
            else:
                role_tag = None

            role_row = ""
            if role_tag:
                role_row += role_tag
            role_row += role_title
            if role_title_en != role_title:
                role_row += f" / {role_title_en}"
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
                    applicant_name = applicant["name"]
                    if applicant.get("status") == "ELECTED":
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

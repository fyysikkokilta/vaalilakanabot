"""Update the election sheet in Fiirumi."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
import requests
from telegram.ext import ContextTypes

from .sheets_data_manager import DataManager
from .types import DivisionData
from .config import API_KEY, API_USERNAME, VAALILAKANA_POST_URL

YEAR = datetime.now().year
SHEET_MARKER = "---SHEET STARTS HERE---"

logger = logging.getLogger("vaalilakanabot")


def get_current_post_content() -> Optional[str]:
    """Fetch the current content of the election sheet post."""
    try:
        headers = {
            "Api-Key": API_KEY,
            "Api-Username": API_USERNAME,
        }
        response = requests.get(VAALILAKANA_POST_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("raw", "")
    except Exception as e:
        logger.error("Error fetching current post content: %s", e)
        return None


def extract_preamble_and_content(full_text: str) -> Tuple[str, bool]:
    """Extract preamble from the post content.

    Returns:
        Tuple of (preamble, has_marker)
        - preamble: Text before the marker (empty if no marker found)
        - has_marker: True if marker was found in the text
    """
    if SHEET_MARKER in full_text:
        parts = full_text.split(SHEET_MARKER, 1)
        return parts[0].rstrip(), True
    return "", False


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
            if role_title != role_title_en and role_title and role_title_en:
                role_row += f"{role_title} / {role_title_en}"
            elif role_title:
                role_row += f"{role_title}"
            else:
                role_row += f"{role_title_en}"
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
                    fiirumi_post = applicant.get("Fiirumi_Post", "")
                    status = applicant.get("Status", "")

                    applicant_row = "* "

                    if status == "ELECTED":
                        applicant_row += "**"
                    if fiirumi_post:
                        applicant_row += f"[{applicant_name}]({fiirumi_post})"
                    else:
                        applicant_row += f"{applicant_name}"
                    if status == "ELECTED":
                        applicant_row += "**"
                    applicant_row += "\n"
                    text += applicant_row
                text += "\n"

            text += "\n"

        text += "—\n\n"

    return text


async def update_election_sheet(
    _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Update the election sheet in the Guild website.

    Preserves any preamble text above the SHEET_MARKER if it exists.
    """
    # Get full data from Google Sheets (includes non-elected roles)
    try:
        vaalilakana_data = data_manager.vaalilakana_full
    except Exception as e:
        logger.error("Error getting data from Google Sheets: %s", e)
        return None

    # Convert data to markdown
    sheet_content = data_to_markdown(vaalilakana_data)

    # Fetch current post to check for preamble
    current_content = get_current_post_content()
    preamble = ""

    if current_content:
        preamble, has_marker = extract_preamble_and_content(current_content)
        if has_marker:
            logger.info("Found preamble marker, preserving preamble (%d chars)", len(preamble))
        elif preamble:
            # If there's content but no marker found, don't preserve anything
            # to avoid accidentally preserving old sheet data as preamble
            logger.info("No marker found in existing post, not preserving content")
            preamble = ""

    # Build final content
    if preamble:
        # Add preamble, marker, and sheet content
        final_text = f"{preamble}\n\n{SHEET_MARKER}\n\n{sheet_content}"
    else:
        # No preamble, just use sheet content
        final_text = sheet_content

    headers = {
        "Api-Key": API_KEY,
        "Api-Username": API_USERNAME,
        "Content-Type": "application/json",
    }

    payload = {
        "raw": final_text,
    }

    try:
        response = requests.put(
            VAALILAKANA_POST_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Successfully updated election sheet")
        return response
    except Exception as e:
        logger.error("Error updating election sheet: %s", e)
        return None

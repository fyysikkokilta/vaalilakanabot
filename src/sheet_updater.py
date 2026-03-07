"""Update the election sheet in Fiirumi."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
import requests
from telegram.ext import ContextTypes

from .sheets_data_manager import DataManager
from .types import DivisionData, RoleData
from .config import VAALILAKANA_POST_URL
from .fiirumi_area_generator import get_discourse_headers

YEAR = datetime.now().year
SHEET_MARKER = "---SHEET STARTS HERE---"

logger = logging.getLogger("vaalilakanabot")


def get_current_post_content() -> Optional[str]:
    """Fetch the current content of the election sheet post."""
    try:
        response = requests.get(
            VAALILAKANA_POST_URL, headers=get_discourse_headers(), timeout=30
        )
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


def _format_role_md(role_data: RoleData) -> str:
    """Format a single role and its applicants as markdown."""
    role_title = role_data.get("Role_FI")
    role_title_en = role_data.get("Role_EN")
    role_tag = (
        "**"
        if role_data.get("Type") == "BOARD"
        else ("*" if role_data.get("Type") in ("ELECTED", "AUDITOR") else None)
    )
    parts: List[str] = []
    if role_tag:
        parts.append(role_tag)
    if role_title != role_title_en and role_title and role_title_en:
        parts.append(f"{role_title} / {role_title_en}")
    elif role_title:
        parts.append(role_title)
    else:
        parts.append(role_title_en or "")
    if role_data.get("Amount"):
        parts.append(f" ({role_data.get('Amount')})")
    if role_data.get("Deadline"):
        parts.append(f" {role_data.get('Deadline')}")
    if role_tag:
        parts.append(role_tag)
    text = "".join(parts) + "\n"
    for applicant in role_data.get("Applicants", []):
        name = applicant.get("Name")
        fiirumi_post = applicant.get("Fiirumi_Post", "")
        status = applicant.get("Status", "")
        line = "* "
        if status == "ELECTED":
            line += "**"
        line += f"[{name}]({fiirumi_post})" if fiirumi_post else str(name or "")
        if status == "ELECTED":
            line += "**"
        text += line + "\n"
    if role_data.get("Applicants"):
        text += "\n"
    return text + "\n"


def _format_division_md(division_data: DivisionData) -> str:
    """Format a division and its roles as markdown."""
    div_fi = division_data.get("Division_FI")
    div_en = division_data.get("Division_EN")
    text = f"### {div_fi} / {div_en}\n\n"
    for role_data in division_data.get("Roles", []):
        text += _format_role_md(role_data)
    return text + "—\n\n"


def data_to_markdown(data: List[DivisionData]) -> str:
    """Convert data to markdown."""
    text = f"# VAALILAKANA {YEAR} / ELECTION SHEET {YEAR}\n\n"
    for division_data in data:
        text += _format_division_md(division_data)

    return text


async def update_election_sheet(
    _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> Optional[requests.Response]:
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
    has_marker = False

    if current_content:
        preamble, has_marker = extract_preamble_and_content(current_content)
        if has_marker:
            logger.info(
                "Found preamble marker, preserving preamble (%d chars)", len(preamble)
            )

    # Build final content
    if has_marker:
        if preamble:
            final_text = f"{preamble}\n\n{SHEET_MARKER}\n\n{sheet_content}"
        else:
            final_text = f"{SHEET_MARKER}\n\n{sheet_content}"
    else:
        final_text = sheet_content

    payload = {
        "raw": final_text,
    }

    try:
        response = requests.put(
            VAALILAKANA_POST_URL,
            headers=get_discourse_headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        logger.info("Successfully updated election sheet")
        return response
    except Exception as e:
        logger.error("Error updating election sheet: %s", e)
        return None

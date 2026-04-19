"""Update the election sheet in Fiirumi."""

import asyncio
import logging
from typing import List, Optional, Tuple
import requests
from telegram.ext import ContextTypes

from .sheets_data_manager import DataManager
from .types import DivisionData, RoleData
from .config import ELECTION_YEAR, get_vaalilakana_post_url
from .fiirumi_area_generator import get_discourse_headers

YEAR = int(ELECTION_YEAR)
SHEET_HEADING = f"# VAALILAKANA {YEAR} / ELECTION SHEET {YEAR}"

logger = logging.getLogger("vaalilakanabot")


async def get_current_post_content() -> Optional[str]:
    """Fetch the current content of the election sheet post."""
    url = get_vaalilakana_post_url()
    if not url:
        return None
    try:
        response = await asyncio.to_thread(
            requests.get, url, headers=get_discourse_headers(), timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("raw", ""))
    except Exception as e:
        logger.error("Error fetching current post content: %s", e)
        return None


def extract_preamble_and_content(full_text: str) -> Tuple[str, bool]:
    """Extract preamble from the post content.

    Splits on the sheet heading line. Everything before it is the preamble.

    Returns:
        Tuple of (preamble, has_heading)
        - preamble: Text before the heading (empty if heading is at the start or not found)
        - has_heading: True if the sheet heading was found in the text
    """
    if SHEET_HEADING in full_text:
        parts = full_text.split(SHEET_HEADING, 1)
        return parts[0].rstrip(), True
    return "", False


_TAG_BY_TYPE = {"BOARD": "**", "ELECTED": "*", "AUDITOR": "*"}


def _format_role_md(role_data: RoleData) -> str:
    """Format a single role and its applicants as markdown."""
    role_title = role_data.get("Role_FI")
    role_title_en = role_data.get("Role_EN")
    role_tag = _TAG_BY_TYPE.get(role_data.get("Type"), "")
    if role_title and role_title_en and role_title != role_title_en:
        title = f"{role_title} / {role_title_en}"
    else:
        title = role_title or role_title_en or ""
    parts: List[str] = [role_tag, title]
    if role_data.get("Amount"):
        parts.append(f" ({role_data.get('Amount')})")
    if role_data.get("Deadline"):
        parts.append(f" {role_data.get('Deadline')}")
    parts.append(role_tag)
    text = "".join(parts) + "\n"
    for applicant in role_data.get("Applicants", []):
        name = applicant.get("Name")
        fiirumi_post = applicant.get("Fiirumi_Post", "")
        body = f"[{name}]({fiirumi_post})" if fiirumi_post else str(name or "")
        if applicant.get("Status") == "ELECTED":
            body = f"**{body}**"
        text += f"* {body}\n"
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

    Preserves any preamble text that appears before the sheet heading in the post.
    Does nothing if VAALILAKANA_POST_URL is not set.
    """
    post_url = get_vaalilakana_post_url()
    if not post_url:
        logger.debug("Skipping election sheet update: VAALILAKANA_POST_URL not set")
        return None

    # Get full data from Google Sheets (includes non-elected roles)
    try:
        vaalilakana_data = data_manager.vaalilakana_full
    except Exception as e:
        logger.error("Error getting data from Google Sheets: %s", e)
        return None

    # Convert data to markdown
    sheet_content = data_to_markdown(vaalilakana_data)

    # Fetch current post to check for preamble
    current_content = await get_current_post_content()
    if current_content is None:
        logger.warning(
            "Skipping election sheet update: could not fetch current post content "
            "(API error). Preamble preservation requires a successful fetch."
        )
        return None

    preamble, has_heading = extract_preamble_and_content(current_content)
    if has_heading and preamble:
        logger.info("Found preamble, preserving it (%d chars)", len(preamble))

    # Build final content: preamble (if any) followed by the sheet
    if has_heading and preamble:
        final_text = f"{preamble}\n\n{sheet_content}"
    else:
        final_text = sheet_content

    payload = {
        "raw": final_text,
    }

    try:
        response = await asyncio.to_thread(
            requests.put,
            post_url,
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

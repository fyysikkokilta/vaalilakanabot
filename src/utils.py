"""Utility functions for the Vaalilakanabot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional

from .config import BOARD, ELECTED_OFFICIALS, BASE_URL


def generate_keyboard(
    options: List[str],
    callback_data: Optional[List[str]] = None,
    back: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Generate an inline keyboard with the given options."""
    keyboard = []
    for option in options:
        if callback_data:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        option, callback_data=callback_data[options.index(option)]
                    )
                ]
            )
        else:
            keyboard.append([InlineKeyboardButton(option, callback_data=option)])

    if back:
        keyboard.insert(0, [InlineKeyboardButton(back, callback_data="back")])

    return InlineKeyboardMarkup(keyboard)


def check_title_matches_applicant_and_role(
    title: str, applicant_name: str, role_title: str, role_title_en: str
) -> bool:
    """Check if a post title contains both the applicant name and role name."""
    title_lower = title.lower()
    name_lower = applicant_name.lower()
    role_lower = role_title.lower()
    role_en_lower = role_title_en.lower() if role_title_en else ""

    # Check if title contains the applicant name
    name_in_title = name_lower in title_lower

    # Check if title contains either Finnish or English role name
    role_in_title = role_lower in title_lower or (
        role_en_lower and role_en_lower in title_lower
    )

    return name_in_title and role_in_title


def vaalilakana_to_string(vaalilakana: dict, find_division_func) -> str:
    """Convert vaalilakana data to a formatted string."""
    output = ""
    output += "<b>---------------Raati---------------</b>\n"

    # Hardcoded to maintain order instead using dict keys
    for position in BOARD:
        output += f"<b>{position}:</b>\n"
        division = find_division_func(position)
        if division:
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                link = applicant["fiirumi"]
                selected = applicant["valittu"]
                if selected:
                    if link:
                        output += (
                            f'- <a href="{link}">{applicant["name"]}</a> (valittu)\n'
                        )
                    else:
                        output += f'- {applicant["name"]} (valittu)\n'
                else:
                    if link:
                        output += f'- <a href="{link}">{applicant["name"]}</a>\n'
                    else:
                        output += f'- {applicant["name"]}\n'
        output += "\n"

    output += "<b>----------Toimihenkilöt----------</b>\n"
    for position in ELECTED_OFFICIALS:
        output += f"<b>{position}:</b>\n"
        division = find_division_func(position)
        if division:
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                link = applicant["fiirumi"]
                selected = applicant["valittu"]
                if selected:
                    if link:
                        output += (
                            f'- <a href="{link}">{applicant["name"]}</a> (valittu)\n'
                        )
                    else:
                        output += f'- {applicant["name"]} (valittu)\n'
                else:
                    if link:
                        output += f'- <a href="{link}">{applicant["name"]}</a>\n'
                    else:
                        output += f'- {applicant["name"]}\n'
        output += "\n"

    return output


def vaalilakana_to_string_en(vaalilakana: dict, find_division_func) -> str:
    """Convert vaalilakana data to a formatted string in English."""
    output = ""
    output += "<b>---------------Board---------------</b>\n"

    # Hardcoded to maintain order instead using dict keys
    for position in BOARD:
        # Get English title if available
        division = find_division_func(position)
        if division:
            role_data = vaalilakana[division]["roles"][position]
            position_en = role_data.get("title_en", position)
        else:
            position_en = position

        output += f"<b>{position_en}:</b>\n"
        if division:
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                link = applicant["fiirumi"]
                selected = applicant["valittu"]
                if selected:
                    if link:
                        output += (
                            f'- <a href="{link}">{applicant["name"]}</a> (selected)\n'
                        )
                    else:
                        output += f'- {applicant["name"]} (selected)\n'
                else:
                    if link:
                        output += f'- <a href="{link}">{applicant["name"]}</a>\n'
                    else:
                        output += f'- {applicant["name"]}\n'
        output += "\n"

    output += "<b>----------Officials----------</b>\n"
    for position in ELECTED_OFFICIALS:
        # Get English title if available
        division = find_division_func(position)
        if division:
            role_data = vaalilakana[division]["roles"][position]
            position_en = role_data.get("title_en", position)
        else:
            position_en = position

        output += f"<b>{position_en}:</b>\n"
        if division:
            applicants = vaalilakana[division]["roles"][position]["applicants"]
            for applicant in applicants:
                link = applicant["fiirumi"]
                selected = applicant["valittu"]
                if selected:
                    if link:
                        output += (
                            f'- <a href="{link}">{applicant["name"]}</a> (selected)\n'
                        )
                    else:
                        output += f'- {applicant["name"]} (selected)\n'
                else:
                    if link:
                        output += f'- <a href="{link}">{applicant["name"]}</a>\n'
                    else:
                        output += f'- {applicant["name"]}\n'
        output += "\n"

    return output


def create_fiirumi_link(slug: str, t_id: str) -> str:
    """Create a fiirumi link from slug and thread ID."""
    return f"{BASE_URL}/t/{slug}/{t_id}"

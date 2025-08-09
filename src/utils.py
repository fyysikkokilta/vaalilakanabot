"""Utility functions for the Vaalilakanabot."""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .config import BASE_URL


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


def _build_vaalilakana_message(vaalilakana: dict, language: str = "en") -> str:
    """Build vaalilakana message in the requested language (fi|en).

    Input: flat mapping of position -> role_data.
    """
    is_finnish = language.lower() != "en"

    headings = {
        "board": (
            "<b>---------------Raati---------------</b>\n"
            if is_finnish
            else "<b>---------------Board---------------</b>\n"
        ),
        "officials": (
            "<b>----------Toimihenkilöt----------</b>\n"
            if is_finnish
            else "<b>----------Officials----------</b>\n"
        ),
    }
    elected_label = "valittu" if is_finnish else "elected"

    # Partition roles by type
    board_roles = []
    officials_roles = []
    for position, role_data in vaalilakana.items():
        role_type = role_data.get("type")
        if role_type == "BOARD":
            board_roles.append((position, role_data))
        elif role_type == "ELECTED":
            officials_roles.append((position, role_data))

    def render_roles(roles: list[tuple[str, dict]]) -> str:
        text = ""
        for position, role_data in roles:
            # Localized title
            title = role_data.get("title_en", position) if not is_finnish else position
            text += f"<b>{title}:</b>\n"
            for applicant in role_data.get("applicants", []):
                name = applicant.get("name", "")
                link = applicant.get("fiirumi", "")
                elected = applicant.get("status") == "ELECTED"
                if elected:
                    if link:
                        text += f'- <a href="{link}">{name}</a> ({elected_label})\n'
                    else:
                        text += f"- {name} ({elected_label})\n"
                else:
                    if link:
                        text += f'- <a href="{link}">{name}</a>\n'
                    else:
                        text += f"- {name}\n"
            text += "\n"
        return text

    output = ""
    output += headings["board"]
    output += render_roles(board_roles)
    output += headings["officials"]
    output += render_roles(officials_roles)
    return output


def vaalilakana_to_string(vaalilakana: dict) -> str:
    """Build vaalilakana message in Finnish."""
    return _build_vaalilakana_message(vaalilakana, language="fi")


def vaalilakana_to_string_en(vaalilakana: dict) -> str:
    """Build vaalilakana message in English."""
    return _build_vaalilakana_message(vaalilakana, language="en")


def create_fiirumi_link(t_id: str) -> str:
    """Create a fiirumi link from slug and thread ID."""
    return f"{BASE_URL}/t/{t_id}"

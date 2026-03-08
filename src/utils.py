"""Utility functions for the Vaalilakanabot."""

import logging
import time
from functools import wraps
from typing import Any, Callable, List, Literal, Optional, TypeVar

from gspread.exceptions import APIError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from .config import BASE_URL
from .types import (
    ApplicationRow,
    ApplicationStatus,
    ElectionStructureRow,
    RoleData,
    UserRow,
)

logger = logging.getLogger("vaalilakanabot")
T = TypeVar("T")


# Helper functions for common data access patterns


def get_group_id(app: ApplicationRow) -> str:
    """Safely extract and normalize Group_ID from an application.

    Returns empty string if Group_ID is None or whitespace-only.
    """
    return (app.get("Group_ID") or "").strip()


def get_user_name(user: Optional[UserRow], fallback: str = "") -> str:
    """Safely extract name from user data with fallback.

    Args:
        user: UserRow data or None
        fallback: Default value if user is None or has no name

    Returns:
        User's name or fallback value
    """
    if user is None:
        return fallback
    return user.get("Name", fallback)


def is_active_application(app: ApplicationRow) -> bool:
    """Check if an application is active (not denied or removed).

    Args:
        app: Application row to check

    Returns:
        True if status is not DENIED or REMOVED
    """
    status = app.get("Status", "")
    return status not in ("DENIED", "REMOVED")


def retry_on_api_error(
    max_retries: int = 3, backoff_factor: float = 2.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry API calls with exponential backoff on 503 errors."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    last_exception = e
                    status_code = 503
                    if hasattr(e, "response") and hasattr(e.response, "status_code"):
                        status_code = e.response.status_code
                    elif "503" not in str(e):
                        raise
                    if status_code not in (429, 500, 502, 503, 504):
                        raise
                    wait_time = backoff_factor**attempt
                    logger.warning(
                        "API error %s in %s (attempt %d/%d), retrying in %.1fs: %s",
                        status_code,
                        func.__name__,
                        attempt + 1,
                        max_retries,
                        wait_time,
                        e,
                    )
                    time.sleep(wait_time)
                except Exception as exc:
                    logger.error("Non-retryable error in %s: %s", func.__name__, exc)
                    raise
            logger.error(
                "All %d retry attempts exhausted for %s, last error: %s",
                max_retries,
                func.__name__,
                last_exception,
            )
            if last_exception:
                raise last_exception
            raise RuntimeError("Unknown error")

        return wrapper

    return decorator


def generate_keyboard(
    options: List[str],
    callback_data: Optional[List[str]] = None,
    back: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Generate an inline keyboard with the given options."""
    keyboard: List[List[InlineKeyboardButton]] = []
    if callback_data:
        for option, cb in zip(options, callback_data):
            keyboard.append([InlineKeyboardButton(option, callback_data=cb)])
    else:
        for option in options:
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

    return bool(name_in_title and role_in_title)


def get_role_name(role: ElectionStructureRow, is_finnish: bool) -> str:
    """Get the role name in the requested language (fi|en)."""
    return role.get("Role_EN") if not is_finnish else role.get("Role_FI")


def vaalilakana_to_string(vaalilakana: List[RoleData], is_finnish: bool) -> str:
    """Build vaalilakana message in the requested language (fi|en).

    Input: flat mapping of position -> role_data.
    """
    headings = {
        "board": (
            "<b>---------------Raati---------------</b>\n"
            if is_finnish
            else "<b>---------------Board---------------</b>\n"
        ),
        "officials": (
            "<b>----------Toimihenkilöt----------</b>\n"
            if is_finnish
            else "<b>------------Officials------------</b>\n"
        ),
    }
    elected_label = get_translation("elected_label", is_finnish)

    # Partition roles by type
    board_roles: List[RoleData] = []
    officials_roles: List[RoleData] = []
    for role_data in vaalilakana:
        role_type = role_data.get("Type")
        if role_type == "BOARD":
            board_roles.append((role_data))
        elif role_type == "ELECTED":
            officials_roles.append(role_data)

    def render_roles(roles: list[RoleData]) -> str:
        text = ""
        for role_data in roles:
            # Localized title
            title = role_data.get("Role_FI") if is_finnish else role_data.get("Role_EN")
            text += f"<b>{title}:</b>\n"
            for applicant in role_data.get("Applicants", []):
                name = applicant.get("Name", "")
                link = applicant.get("Fiirumi_Post", "")
                elected = applicant.get("Status") == "ELECTED"
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
    output += headings.get("board") or ""
    output += render_roles(board_roles)
    output += headings.get("officials") or ""
    output += render_roles(officials_roles)
    return output


def create_fiirumi_link(t_id: str) -> str:
    """Create a fiirumi link from slug and thread ID."""
    return f"{BASE_URL}/t/{t_id}"


async def send_sticker(update: Update, sticker_name: str) -> None:
    """Send a sticker by name."""
    try:
        with open(f"assets/{sticker_name}.png", "rb") as photo:
            if not update.message:
                return
            await update.message.reply_sticker(photo)
    except Exception as e:
        logger.warning("Error in sending %s sticker: %s", sticker_name.capitalize(), e)


def map_application_status(status: ApplicationStatus, is_finnish: bool = True) -> str:
    """Map application status to localized string."""
    status_map = {
        "": ("Odottaa", "Pending"),
        "APPROVED": ("Hyväksytty", "Approved"),
        "DENIED": ("Hylätty", "Rejected"),
        "REMOVED": ("Poistettu", "Removed"),
        "ELECTED": ("Valittu", "Elected"),
        "PENDING": ("Odottaa", "Pending"),
    }

    finnish_text, english_text = status_map.get(status, ("Tuntematon", "Unknown"))
    return finnish_text if is_finnish else english_text


def get_notification_text(
    notification_type: Literal["approved", "rejected", "removed", "elected"],
    position: str,
    is_finnish: bool,
) -> str:
    """Get standardized notification text for different scenarios."""
    notifications = {
        "approved": (
            f"✅ <b>Hakemuksesi on hyväksytty!</b>\n\n"
            f"Hakemuksesi virkaan <b>{position}</b> on hyväksytty ja lisätty vaalilakanaan. "
            f"Kiitos hakemuksestasi!",
            f"✅ <b>Your application has been approved!</b>\n\n"
            f"Your application for the position <b>{position}</b> has been approved and added to the election sheet. "
            f"Thank you for your application!",
        ),
        "rejected": (
            f"❌ <b>Hakemuksesi on hylätty</b>\n\n"
            f"Valitettavasti hakemuksesi virkaan <b>{position}</b> on hylätty. "
            f"Voit ottaa yhteyttä raatiin lisätietojen saamiseksi.",
            f"❌ <b>Your application has been rejected</b>\n\n"
            f"Unfortunately, your application for the position <b>{position}</b> has been rejected. "
            f"You can contact the board for more information.",
        ),
        "removed": (
            f"🗑️ <b>Hakemuksesi on poistettu</b>\n\n"
            f"Hakemuksesi virkaan <b>{position}</b> on poistettu raadin toimesta.\n\n"
            f"Jos haluat lisätietoja, voit ottaa yhteyttä raatiin.",
            f"🗑️ <b>Your application has been removed</b>\n\n"
            f"Your application for the position <b>{position}</b> has been removed by the board.\n\n"
            f"If you want more information, you can contact the board.",
        ),
        "elected": (
            f"🎉 <b>Onneksi olkoon!</b>\n\n"
            f"Sinut on valittu virkaan <b>{position}</b>! "
            f"Kiitos hakemuksestasi.",
            f"🎉 <b>Congratulations!</b>\n\n"
            f"You have been elected to the position <b>{position}</b>! "
            f"Thank you for your application.",
        ),
    }

    finnish_text, english_text = notifications.get(notification_type, ("", ""))
    return finnish_text if is_finnish else english_text


def get_translation(key: str, is_finnish: bool = True, **kwargs: Any) -> str:
    """Get translated text for a given key with optional formatting parameters."""

    translations = {
        # Application flow
        "select_division": (
            "Minkä jaoksen virkaan haet?",
            "For which division are you applying?",
        ),
        "select_role": ("Mihin rooliin haet?", "What position are you applying to?"),
        "ask_name": (
            "Haet {elected_text}rooliin: {position}. Mikä on nimesi?",
            "You are applying to the {elected_text}role: {position}. What is your name?",
        ),
        "ask_email": ("Mikä on sähköpostiosoitteesi?", "What is your email address?"),
        # Button texts
        "back": ("Takaisin", "Back"),
        "continue": ("Jatka", "Continue"),
        "cancel": ("Peruuta", "Cancel"),
        "yes": ("Kyllä", "Yes"),
        "no": ("En", "No"),
        # Status messages
        "already_applied": (
            "Olet jo hakenut tähän rooliin!",
            "You have already applied to this position!",
        ),
        "already_elected": (
            "Olet jo valittu tähän rooliin!",
            "You have already been elected to this position!",
        ),
        "pending_application": (
            "Sinulla on jo odottava hakemus tähän rooliin!",
            "You already have a pending application for this position!",
        ),
        "application_cancelled": ("Hakemus peruttu.", "Application cancelled."),
        "application_received": (
            "Hakemuksesi on vastaanotettu. Kiitos!",
            "Your application has been received. Thank you!",
        ),
        "application_cancelled_full": (
            "Hakemuksesi on peruttu.",
            "Your application has been cancelled.",
        ),
        "application_awaiting_approval": (
            "Hakemuksesi on lähetetty ja odottaa raadin hyväksyntää. Saat ilmoituksen kun hakemus on käsitelty.",
            "Your application has been sent and is awaiting board approval. You will be notified when it's processed.",
        ),
        # Warning messages
        "multiple_application_warning": (
            "⚠️ <b>Varoitus: Olet jo hakenut vaaleilla valittavaan virkaan!</b>\n\n"
            "Olet jo hakenut virkaan: <b>{elected_positions}</b>\n\n"
            "Jos sinulla on vararooleja, kerro niistä raadille.\n\n"
            "Haluatko jatkaa hakemusta tähän rooliin?",
            "⚠️ <b>Warning: You have already applied to an elected position!</b>\n\n"
            "You have already applied to: <b>{elected_positions}</b>\n\n"
            "If you have backup roles, tell the board.\n\n"
            "Do you want to continue with this application?",
        ),
        # Validation errors
        "name_no_commas": (
            "Nimi ei voi sisältää pilkkuja. Anna nimesi uudelleen:",
            "Name cannot contain commas. Please enter your name again:",
        ),
        "name_not_empty": (
            "Nimi ei voi olla tyhjä. Anna nimesi:",
            "Name cannot be empty. Please enter your name:",
        ),
        "email_invalid": (
            "Sähköpostiosoite ei ole kelvollinen. Anna sähköpostiosoite muodossa: nimi@domain.fi",
            "Email address is not valid. Please provide an email in format: name@domain.com",
        ),
        # Application confirmation
        "application_details": (
            "Hakemuksesi tiedot: \n"
            "<b>Haettava rooli</b>: {position}\n"
            "<b>Nimi</b>: {name}\n"
            "<b>Sähköposti</b>: {email}\n"
            "<b>Telegram</b>: {telegram}\n\n"
            "Haluatko lähettää hakemuksen{elected_text}?",
            "Your application details: \n"
            "<b>Position</b>: {position}\n"
            "<b>Name</b>: {name}\n"
            "<b>Email</b>: {email}\n"
            "<b>Telegram</b>: {telegram}\n\n"
            "Do you want to send the application{elected_text}?",
        ),
        # Role type indicators
        "elected_role_prefix": ("vaaleilla valittavaan ", "elected "),
        "admin_approval_note": (
            " (Hakemus vaatii raadin hyväksynnän ennen lisäämistä vaalilakanaan)",
            " (Application requires board approval before being added to the election sheet)",
        ),
        # Status labels
        "elected_label": ("valittu", "elected"),
        "fiirumi_label": ("Fiirumi", "Fiirumi"),
        "division_label": ("Jaos", "Division"),
        "status_label": ("Tila", "Status"),
        # User applications
        "my_applications": (
            "📋 <b>Omat hakemuksesi</b>\n\n",
            "📋 <b>Your applications</b>\n\n",
        ),
        "no_applications": (
            "Sinulla ei ole vielä hakemuksia.",
            "You have no applications yet.",
        ),
        # Registration
        "please_register_first": (
            "Rekisteröidy ensin komennolla /rekisteroidy ennen hakemista.",
            "Please register first with /register before applying.",
        ),
        "register_ask_name": (
            "Syötä koko nimesi:",
            "Enter your full name:",
        ),
        "register_ask_email": (
            "Syötä sähköpostiosoitteesi:",
            "Enter your email address:",
        ),
        "register_consent": (
            "Haluatko että nimesi näytetään killan sivustolla Toimihenkilöt-sivulla? (Kyllä/En)",
            "Do you want your name shown on the guild website in the Officials page? (Yes/No)",
        ),
        "register_done": (
            "Rekisteröityminen valmis. Voit nyt hakea virkoihin komennolla /hae tai /apply.",
            "Registration complete. You can now apply for positions with /apply or /hae.",
        ),
        "register_update_intro": (
            "Olet jo rekisteröitynyt. Täytä kohdat uudelleen päivittääksesi tietosi.",
            "You are already registered. Go through the steps again to update your info.",
        ),
        "register_cancelled": (
            "Rekisteröityminen peruttu.",
            "Registration cancelled.",
        ),
    }

    finnish_text, english_text = translations.get(key, (key, key))
    text = finnish_text if is_finnish else english_text

    # Format with provided kwargs if any
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            # If formatting fails, return unformatted text
            return text

    return text

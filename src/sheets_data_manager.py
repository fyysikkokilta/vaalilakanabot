"""Data management using Google Sheets as the primary data source."""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from telegram.ext import ContextTypes
from .sheets_manager import SheetsManager
from .types import (
    ElectionStructureRow,
    DivisionDict,
    PositionDict,
    ApplicantDict,
    DivisionData,
    RoleData,
    FiirumiPost,
    QuestionPost,
    PendingApplication,
    FiirumiPostInput,
    QuestionPostInput,
    ApplicationData,
    ChannelRow,
)


logger = logging.getLogger("vaalilakanabot")


class DataManager:
    """Manages all data operations using Google Sheets as the backend."""

    def __init__(
        self, sheet_url: Optional[str] = None, credentials_file: Optional[str] = None
    ) -> None:
        """Initialize with Google Sheets connection."""
        self.sheets_manager: SheetsManager = SheetsManager(sheet_url, credentials_file)

        # Initialize empty structure if needed
        self._ensure_basic_structure()

    def _ensure_basic_structure(self) -> None:
        """Ensure basic sheets structure exists or create fallback."""
        try:
            # Try to get basic data to verify connection works
            roles: List[ElectionStructureRow] = self.sheets_manager.get_all_roles()
            logger.info("Connected to Google Sheets with %s roles", len(roles))
        except Exception as e:
            logger.warning(
                "Google Sheets not accessible, will use empty structure: %s", e
            )

    def get_all_roles(self) -> List[ElectionStructureRow]:
        """Get all roles from Google Sheets with caching."""
        return self.sheets_manager.get_all_roles()

    def get_all_divisions(self) -> List[DivisionDict]:
        """Get all divisions with caching."""
        return self.sheets_manager.get_divisions()

    def find_position_by_name(self, position_name: str) -> Optional[str]:
        """Find position by Finnish or English name."""
        role: Optional[ElectionStructureRow] = self.find_role_by_name(position_name)
        if role:
            return role["Role_FI"]
        return None

    def find_role_by_name(self, role_name: str) -> Optional[ElectionStructureRow]:
        """Find a role by name using SheetsManager's cached lookup."""
        return self.sheets_manager.find_role_by_name(role_name)

    def get_all_positions(self) -> List[PositionDict]:
        """Get all positions with both Finnish and English names."""
        roles = self.get_all_roles()
        return [
            {
                "fi": role["Role_FI"],
                "en": role["Role_EN"],
                "division": role["Division_FI"],
            }
            for role in roles
        ]

    def get_divisions(self, is_finnish: bool = True) -> tuple[List[str], List[str]]:
        """Get divisions with localization."""
        divisions: List[DivisionDict] = self.get_all_divisions()
        localized_divisions: List[str] = [
            division["fi"] if is_finnish else division["en"] for division in divisions
        ]
        callback_data: List[str] = [division["fi"] for division in divisions]
        return localized_divisions, callback_data

    def get_positions(
        self, division: str, is_finnish: bool = True
    ) -> tuple[List[str], List[str]]:
        """Get positions for a division with deadline filtering."""
        current_date = datetime.now()
        # Use cached roles and filter by division to avoid extra Sheets calls
        roles = [
            role for role in self.get_all_roles() if role.get("Division_FI") == division
        ]
        filtered_roles = []

        for role in roles:
            # Check if there's a deadline and if it has passed
            deadline_str = role.get("Deadline", "")
            if deadline_str:
                try:
                    # Parse date in dd.mm format and assume current year
                    day, month = deadline_str.rstrip(".").split(".")
                    deadline = datetime(current_date.year, int(month), int(day))

                    if current_date.date() > deadline.date():
                        continue  # Skip this position if deadline has passed
                except (ValueError, AttributeError):
                    # If date parsing fails, include the position (assume no deadline)
                    pass

            filtered_roles.append(role)

        localized_positions = []
        for role in filtered_roles:
            position_name = role["Role_FI"] if is_finnish else role["Role_EN"]
            # Add emoji for elected positions (BOARD and ELECTED types)
            if role.get("Type") in ("BOARD", "ELECTED"):
                position_name = f"🗳️ {position_name}"
            localized_positions.append(position_name)

        callback_data = [role["Role_FI"] for role in filtered_roles]

        return localized_positions, callback_data

    def add_applicant(
        self,
        position: str,
        applicant: ApplicantDict,
        language: str = "en",
    ) -> bool:
        """Add a new applicant to a position."""
        # Find the role ID
        role: Optional[ElectionStructureRow] = self.find_role_by_name(position)
        if not role:
            logger.error("Role not found: %s", position)
            return False

        return self.sheets_manager.add_application(
            role_id=role["ID"],
            telegram_id=applicant["user_id"],
            name=applicant["name"],
            email=applicant["email"],
            telegram_username=applicant["telegram"],
            fiirumi_post=applicant.get("fiirumi", ""),
            status=applicant.get("status", ""),
            language=language,
        )

    async def remove_applicant(
        self,
        position: str,
        applicant_name: str,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> bool:
        """Remove an applicant by marking Status as REMOVED and notify them."""
        role = self.find_role_by_name(position)
        if not role:
            return False

        applications = self.sheets_manager.get_applications_for_role(role["ID"])
        for app in applications:
            if app["Name"] == applicant_name:
                telegram_id = app["Telegram_ID"]
                success = self.sheets_manager.update_application_status(
                    role["ID"], telegram_id, status="REMOVED"
                )

                if success:
                    # Send notification to the applicant
                    try:
                        # Get the user's language preference from the application
                        user_language = app.get("Language", "en")

                        if user_language == "en":
                            notification_text = (
                                f"🗑️ <b>Your application has been removed</b>\n\n"
                                f"Your application for the position <b>{position}</b> has been removed by the admins.\n\n"
                                f"If you want more information, you can contact the board."
                            )
                        else:
                            notification_text = (
                                f"🗑️ <b>Hakemuksesi on poistettu</b>\n\n"
                                f"Hakemuksesi virkaan <b>{position}</b> on poistettu adminien toimesta.\n\n"
                                f"Jos haluat lisätietoja, voit ottaa yhteyttä raatiin."
                            )

                        await context.bot.send_message(
                            chat_id=telegram_id,
                            text=notification_text,
                            parse_mode="HTML",
                        )
                        logger.info(
                            "Sent removal notification to user %s for position %s in %s",
                            telegram_id,
                            position,
                            user_language,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to notify user %s about removal: %s", telegram_id, e
                        )

                return success
        return False

    def set_applicant_fiirumi(
        self, position: str, applicant_name: str, fiirumi_link: str
    ) -> bool:
        """Set the fiirumi link for an applicant."""
        role = self.find_role_by_name(position)
        if not role:
            return False

        # Find the applicant by name (this is not ideal, should use telegram_id)
        applications = self.sheets_manager.get_applications_for_role(role["ID"])
        for app in applications:
            if app["Name"] == applicant_name:
                return self.sheets_manager.update_application_status(
                    role["ID"], app["Telegram_ID"], fiirumi_post=fiirumi_link
                )
        return False

    def set_applicant_elected(self, position: str, applicant_name: str) -> bool:
        """Mark an applicant as elected by setting Status="ELECTED"."""
        role = self.find_role_by_name(position)
        if not role:
            return False

        applications = self.sheets_manager.get_applications_for_role(role["ID"])
        for app in applications:
            if app["Name"] == applicant_name:
                return self.sheets_manager.update_application_status(
                    role["ID"], app["Telegram_ID"], status="ELECTED"
                )
        return False

    def check_applicant_exists(self, position: str, user_id: int) -> bool:
        """Check if a user has already applied to a position."""
        role = self.find_role_by_name(position)
        if not role:
            return False

        return self.sheets_manager.check_application_exists(role["ID"], user_id)

    def check_pending_application_exists(self, position: str, user_id: int) -> bool:
        """Check if a user has a pending application for a position."""
        # Find the role ID for the position
        role = self.find_role_by_name(position)
        if not role:
            return False

        # Check if there's a pending application (Status is empty)
        applications = self.sheets_manager.get_applications_for_role(role["ID"])
        for app in applications:
            if (
                app["Telegram_ID"] == user_id
                and app.get("Status", app.get("Admin_Approved", "")) == ""
            ):
                return True
        return False

    def add_pending_application(self, application_data: ApplicationData) -> bool:
        """Add a new pending application awaiting admin approval."""
        try:
            applicant = application_data.get("applicant", {})
            position = application_data.get("position", "")

            role = self.find_role_by_name(position)
            if not role:
                logger.error("Role not found: %s", position)
                return False

            return self.sheets_manager.add_application(
                role_id=role["ID"],
                telegram_id=applicant.get("user_id", 0),
                name=applicant.get("name", ""),
                email=applicant.get("email", ""),
                telegram_username=applicant.get("telegram", ""),
                fiirumi_post="",
                status="",  # pending
                language=application_data.get("language", "en"),
            )
        except Exception as e:
            logger.error("Error adding pending application: %s", e)
            return False

    def approve_application(
        self, role_id: str, telegram_id: int
    ) -> Optional[Dict[str, str]]:
        """Approve a pending application by updating its status to APPROVED."""
        try:
            success = self.sheets_manager.update_application_status(
                role_id, telegram_id, status="APPROVED"
            )
            if success:
                return {"status": "approved"}
            return None
        except Exception as e:
            logger.error("Error approving application: %s", e)
            return None

    def reject_application(
        self, role_id: str, telegram_id: int
    ) -> Optional[Dict[str, str]]:
        """Reject a pending application by marking it as DENIED."""
        try:
            success = self.sheets_manager.update_application_status(
                role_id, telegram_id, status="DENIED"
            )
            if success:
                return {"status": "rejected"}
            return None
        except Exception as e:
            logger.error("Error rejecting application: %s", e)
            return None

    # Google Sheets methods for all data
    def add_channel(self, chat_id: int) -> bool:
        """Add a new channel."""
        success = self.sheets_manager.add_channel(chat_id)
        if success:
            logger.info("New channel added %s", chat_id)
        return success

    def remove_channel(self, chat_id: int) -> bool:
        """Remove a channel."""
        return self.sheets_manager.remove_channel(chat_id)

    def add_fiirumi_post(self, post_id: str, post_data: FiirumiPostInput) -> bool:
        """Add a new fiirumi post."""
        return self.sheets_manager.add_fiirumi_post(post_id, post_data)

    def add_question_post(self, post_id: str, post_data: QuestionPostInput) -> bool:
        """Add a new question post."""
        return self.sheets_manager.add_question_post(post_id, post_data)

    def update_question_posts_count(self, post_id: str, posts_count: int) -> bool:
        """Update the posts count for a question."""
        return self.sheets_manager.update_question_posts_count(post_id, posts_count)

    @property
    def channels(self) -> List[ChannelRow]:
        """Get all registered channels."""
        return self.sheets_manager.get_all_channels()

    @property
    def fiirumi_posts(self) -> Dict[str, FiirumiPost]:
        """Get all fiirumi posts."""
        return self.sheets_manager.get_all_fiirumi_posts()

    @property
    def question_posts(self) -> Dict[str, QuestionPost]:
        """Get all question posts."""
        return self.sheets_manager.get_all_question_posts()

    @property
    def pending_applications(self) -> List[PendingApplication]:
        """Get all pending applications."""
        return self.sheets_manager.get_all_pending_applications()

    @property
    def vaalilakana_full(self) -> Dict[str, DivisionData]:
        """Get the full election dataset (all roles)."""
        return self.sheets_manager.get_election_data(True)

    @property
    def vaalilakana(self) -> Dict[str, RoleData]:
        """Get only elected roles (BOARD, ELECTED) as a flat mapping by position.

        Returns a dict keyed by Finnish role title with role data including
        denormalized division names for convenience.
        """
        full_data = self.sheets_manager.get_election_data(False)
        elected_types = {"BOARD", "ELECTED"}

        flat_roles: Dict[str, RoleData] = {}
        for division_data in full_data.values():
            division_fi = division_data.get("division", "")
            division_en = division_data.get("division_en", "")
            for position, role in division_data.get("roles", {}).items():
                if str(role.get("type")) in elected_types:
                    role_copy: RoleData = {
                        "title": role.get("title", position),
                        "title_en": role.get("title_en", position),
                        "amount": role.get("amount"),
                        "application_dl": role.get("application_dl"),
                        "type": role.get("type"),
                        "applicants": role.get("applicants", []),
                        "division": division_fi,
                        "division_en": division_en,
                    }
                    flat_roles[position] = role_copy

        return flat_roles

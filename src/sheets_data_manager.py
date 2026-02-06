"""Data management using Google Sheets as the primary data source."""

import logging
import uuid
from typing import List, Optional, Tuple, cast
from datetime import datetime

from .sheets_manager import SheetsManager
from .utils import get_role_name, get_group_id, get_user_name, is_active_application
from .types import (
    ElectionStructureRow,
    DivisionDict,
    DivisionData,
    RoleData,
    ChannelRow,
    ApplicationRow,
    UserRow,
    ResultTuple,
    ApprovalResult,
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
        return cast(List[ElectionStructureRow], self.sheets_manager.get_all_roles())

    def find_role_by_name(self, role_name: str) -> Optional[ElectionStructureRow]:
        """Find a role by name using SheetsManager's cached lookup."""
        return self.sheets_manager.find_role_by_name(role_name)

    def get_role_by_id(self, role_id: str) -> Optional[ElectionStructureRow]:
        """Get a role by ID using SheetsManager's cached lookup."""
        return self.sheets_manager.get_role_by_id(role_id)

    def get_divisions(self, is_finnish: bool = False) -> Tuple[List[str], List[str]]:
        """Get divisions with localization."""
        divisions: List[DivisionDict] = self.sheets_manager.get_divisions()
        localized_divisions: List[str] = [
            division.get("Division_FI") if is_finnish else division.get("Division_EN")
            for division in divisions
        ]
        callback_data: List[str] = [
            division.get("Division_FI") for division in divisions
        ]
        return localized_divisions, callback_data

    def get_positions(
        self, division: str, is_finnish: bool = False
    ) -> Tuple[List[str], List[str]]:
        """Get positions for a division with deadline filtering."""
        current_date = datetime.now()
        # Use cached roles and filter by division to avoid extra Sheets calls
        roles = [
            role for role in self.get_all_roles() if role.get("Division_FI") == division
        ]
        filtered_roles: List[ElectionStructureRow] = []

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
            position_name = get_role_name(role, is_finnish)
            # Add emoji for elected positions (BOARD and ELECTED types)
            if role.get("Type") != "NON_ELECTED":
                position_name = f"🗳️ {position_name}"
            localized_positions.append(position_name)

        callback_data = [role.get("ID") for role in filtered_roles]

        return localized_positions, callback_data

    def _get_applications_for_role(self, role_id: str) -> List[ApplicationRow]:
        """Get all active applications for a specific role."""
        try:
            all_applications = self.sheets_manager.get_all_applications()
            return [
                app
                for app in all_applications
                if app.get("Role_ID") == role_id and is_active_application(app)
            ]
        except Exception as e:
            logger.error("Error getting applications for role %s: %s", role_id, e)
            return []

    def get_applications_for_user(self, telegram_id: int) -> List[ApplicationRow]:
        """Get all active applications for a specific user."""
        try:
            all_applications = self.sheets_manager.get_all_applications()
            return [
                app
                for app in all_applications
                if app.get("Telegram_ID") == telegram_id and is_active_application(app)
            ]
        except Exception as e:
            logger.error("Error getting applications for user %s: %s", telegram_id, e)
            return []

    def get_applicant_display(self, app: ApplicationRow) -> Optional[UserRow]:
        """Resolve Name, Email, Telegram for an application from Users sheet (or legacy app fields)."""
        return self.sheets_manager.get_user_by_telegram_id(app.get("Telegram_ID"))

    def get_applicant_display_names_for_announcement(
        self, role_id: str, application: ApplicationRow
    ) -> str:
        """Display name for announcements: single name or 'Name1, Name2' for groups."""
        group_id = get_group_id(application)

        # Single applicant (not in a group)
        if not group_id:
            user = self.get_applicant_display(application)
            return get_user_name(user, "")

        # Group application - get all member names
        group_apps = self._get_applications_for_group(role_id, group_id)
        names = [
            get_user_name(self.get_applicant_display(app), "(?)")
            for app in group_apps
        ]
        return ", ".join(sorted(names))

    def get_applicant_display_names_for_role_and_name(
        self, role: ElectionStructureRow, applicant_name: str
    ) -> str:
        """Resolve display name(s) for a role+name (single or group). For use in replies."""
        apps = self._get_applications_by_role_and_display_name(role, applicant_name)

        # If not found by display name, try by single name
        if not apps:
            app = self._get_applicant_by_role_and_name(role, applicant_name)
            if app is not None:
                group_id = get_group_id(app)
                apps = (
                    self._get_applications_for_group(role.get("ID"), group_id)
                    if group_id
                    else [app]
                )

        if not apps:
            return applicant_name

        return self.get_applicant_display_names_for_announcement(
            role.get("ID"), apps[0]
        )

    def _get_applications_for_group(
        self, role_id: str, group_id: str
    ) -> List[ApplicationRow]:
        """Return all applications for this role with the given Group_ID."""
        normalized_group_id = group_id.strip()
        if not normalized_group_id:
            return []
        return [
            app
            for app in self._get_applications_for_role(role_id)
            if get_group_id(app) == normalized_group_id
        ]

    def _get_applicant_by_role_and_name(
        self, role: ElectionStructureRow, applicant_name: str
    ) -> Optional[ApplicationRow]:
        """Find an application for this role by applicant name (resolved from Users sheet)."""
        applications = self._get_applications_for_role(role.get("ID", ""))
        for app in applications:
            display = self.get_applicant_display(app)
            if display is not None and display.get("Name") == applicant_name:
                return app
        return None

    def _get_group_applications_by_merged_name(
        self, role_id: str, merged_name: str
    ) -> List[ApplicationRow]:
        """Find group applications whose combined names match 'Name1, Name2' format."""
        target_names = frozenset(name.strip() for name in merged_name.split(","))
        applications = self._get_applications_for_role(role_id)

        for app in applications:
            group_id = get_group_id(app)
            if not group_id:
                continue

            group_apps = self._get_applications_for_group(role_id, group_id)
            group_names = frozenset(
                get_user_name(self.get_applicant_display(a), "")
                for a in group_apps
            )

            if group_names == target_names:
                return group_apps

        return []

    def _get_applications_by_role_and_display_name(
        self, role: ElectionStructureRow, display_name: str
    ) -> List[ApplicationRow]:
        """Resolve to list of applications: single name -> [app] or []; merged 'Name1, Name2' -> group members."""
        role_id = role.get("ID", "")

        # Check if this is a merged group name (contains comma)
        if ", " in display_name:
            return self._get_group_applications_by_merged_name(role_id, display_name)

        # Single name lookup
        found_app = self._get_applicant_by_role_and_name(role, display_name)
        return [found_app] if found_app is not None else []

    def add_applicant(
        self,
        applicant: ApplicationRow,
    ) -> bool:
        """Add a new applicant to a position."""
        return self.sheets_manager.add_application(applicant)

    def remove_applicant(
        self,
        role: ElectionStructureRow,
        applicant_name: str,
    ) -> Tuple[bool, Optional[ApplicationRow]]:
        """Remove an applicant by marking Status as REMOVED. Name is resolved from Users sheet.

        Returns:
            Tuple of (success: bool, application_data or None)
            application_data contains the removed application info for notification purposes
        """
        app = self._get_applicant_by_role_and_name(role, applicant_name)
        if not app:
            return False, None

        telegram_id = app.get("Telegram_ID")
        role_id = role.get("ID", "")
        success = self.sheets_manager.update_application_status(
            role_id, telegram_id, status="REMOVED"
        )

        return (success, app) if success else (False, None)

    def set_applicant_fiirumi(
        self, role: ElectionStructureRow, applicant_name: str, fiirumi_link: str
    ) -> bool:
        """Set the fiirumi link for an applicant (or whole group). Name can be single or 'Name1, Name2'."""
        role_id = role.get("ID", "")
        apps = self._get_applications_by_role_and_display_name(role, applicant_name)

        # Try single name lookup if display name didn't match
        if not apps:
            app = self._get_applicant_by_role_and_name(role, applicant_name)
            if not app:
                return False

            group_id = get_group_id(app)
            apps = (
                self._get_applications_for_group(role_id, group_id)
                if group_id
                else [app]
            )

        # If single app is in a group, update entire group
        if len(apps) == 1:
            group_id = get_group_id(apps[0])
            if group_id:
                apps = self._get_applications_for_group(role_id, group_id)

        # Update all applications
        for app in apps:
            self.sheets_manager.update_application_status(
                role_id, app.get("Telegram_ID"), fiirumi_post=fiirumi_link
            )

        return True

    def set_applicant_elected(
        self, role: ElectionStructureRow, applicant_name: str
    ) -> bool:
        """Mark an applicant as elected by setting Status="ELECTED". Name is resolved from Users sheet."""
        app = self._get_applicant_by_role_and_name(role, applicant_name)
        if not app:
            return False
        return self.sheets_manager.update_application_status(
            role.get("ID"), app.get("Telegram_ID"), status="ELECTED"
        )

    def _validate_group_completeness(
        self, apps: List[ApplicationRow], names_set: set[str], role_id: str
    ) -> Optional[str]:
        """Validate that all group members are included when electing groups.

        Returns error message if validation fails, None if OK.
        """
        for app in apps:
            group_id = get_group_id(app)
            if not group_id:
                continue

            # Get all applications in this group
            group_apps = self._get_applications_for_group(role_id, group_id)
            group_names = {
                get_user_name(self.get_applicant_display(a), "")
                for a in group_apps
            }

            # Check if all group members are in the command
            if not group_names.issubset(names_set):
                missing = group_names - names_set
                return (
                    f"Group application: list all members: {', '.join(sorted(group_names))}. "
                    f"Missing in command: {', '.join(sorted(missing))}."
                )

        return None

    def set_applicants_elected(
        self, role: ElectionStructureRow, names: List[str]
    ) -> ResultTuple:
        """Mark applicants as elected. For group applications, all group members must be listed.

        Returns:
            (True, success_message) or (False, error_message).
        """
        if not names:
            return False, "At least one name is required."

        role_id = role.get("ID")
        apps: List[ApplicationRow] = []
        missing: List[str] = []

        # Find all applications by name
        for name in names:
            app = self._get_applicant_by_role_and_name(role, name)
            if app:
                apps.append(app)
            else:
                missing.append(name)

        if missing:
            return False, f"Could not find applicant(s): {', '.join(missing)}"

        # Validate group completeness
        names_set = {get_user_name(self.get_applicant_display(a), "") for a in apps}
        error_msg = self._validate_group_completeness(apps, names_set, role_id)
        if error_msg:
            return False, error_msg

        # Mark all as elected
        for app in apps:
            self.sheets_manager.update_application_status(
                role_id, app.get("Telegram_ID"), status="ELECTED"
            )

        role_name = role.get("Role_EN") or role.get("Role_FI") or role_id
        return True, f"Elected: {', '.join(names)} for {role_name}"

    def combine_applicants(
        self, role: ElectionStructureRow, names: List[str]
    ) -> ResultTuple:
        """Set the same Group_ID on all applications for the given role and names (group application).

        Returns:
            (True, success_message) or (False, error_message).
        """
        if len(names) < 2:
            return False, "At least two names are required to combine."

        role_id = role.get("ID")
        apps: List[ApplicationRow] = []
        missing: List[str] = []

        # Find all applications by name
        for name in names:
            app = self._get_applicant_by_role_and_name(role, name)
            if app:
                apps.append(app)
            else:
                missing.append(name)

        if missing:
            return (
                False,
                f"Could not find applicant(s) for this role: {', '.join(missing)}",
            )

        # Assign shared group ID to all applications
        group_id = str(uuid.uuid4())
        for app in apps:
            self.sheets_manager.update_application_status(
                role_id, app.get("Telegram_ID"), group_id=group_id
            )

        role_name = role.get("Role_EN") or role.get("Role_FI") or role_id
        return (
            True,
            f"Combined {len(apps)} applicants for {role_name}: {', '.join(names)}",
        )

    def approve_application(
        self, role_id: str, telegram_id: int
    ) -> Optional[ApprovalResult]:
        """Approve a pending application by updating its status to APPROVED."""
        try:
            success = self.sheets_manager.update_application_status(
                role_id, telegram_id, status="APPROVED"
            )
            return {"status": "approved"} if success else None
        except Exception as e:
            logger.error("Error approving application: %s", e)
            return None

    def reject_application(
        self, role_id: str, telegram_id: int
    ) -> Optional[ApprovalResult]:
        """Reject a pending application by marking it as DENIED."""
        try:
            success = self.sheets_manager.update_application_status(
                role_id, telegram_id, status="DENIED"
            )
            return {"status": "rejected"} if success else None
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

    @property
    def channels(self) -> List[ChannelRow]:
        """Get all registered channels."""
        return cast(List[ChannelRow], self.sheets_manager.get_all_channels())

    @property
    def vaalilakana_full(self) -> List[DivisionData]:
        """Get the full election dataset (all roles)."""
        return self.sheets_manager.get_election_data()

    @property
    def vaalilakana(self) -> List[RoleData]:
        """Get only elected roles (BOARD, ELECTED) as a flat mapping by position.

        Returns a dict keyed by Finnish role title with role data including
        denormalized division names for convenience.
        """
        full_data = self.sheets_manager.get_election_data()

        # Flatten all roles from all divisions and filter by elected types
        return [
            role
            for division in full_data
            for role in division.get("Roles", [])
            if role.get("Type") in ("BOARD", "ELECTED")
        ]

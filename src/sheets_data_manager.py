"""Data management using Google Sheets as the primary data source."""

import logging
import uuid
from typing import Dict, List, Optional, Tuple, cast
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
    ApplicationWithDisplay,
    UserRow,
    ResultTuple,
)


logger = logging.getLogger("vaalilakanabot")

# Keys added when enriching ApplicationRow -> ApplicationWithDisplay (from Users sheet).
# Excluded when spreading app to avoid duplicate keyword arguments if sheet data contains them.
_DISPLAY_KEYS = frozenset({"Name", "Email", "Telegram"})


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
        return self.sheets_manager.get_all_roles()  # type: ignore[no-any-return]

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
            all_applications = self.get_all_applications()
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
            all_applications = self.get_all_applications()
            return [
                app
                for app in all_applications
                if app.get("Telegram_ID") == telegram_id and is_active_application(app)
            ]
        except Exception as e:
            logger.error("Error getting applications for user %s: %s", telegram_id, e)
            return []

    def get_other_elected_roles_for_user(
        self, telegram_id: int, current_role_id: str = ""
    ) -> List[ElectionStructureRow]:
        """Return role rows for the user's other BOARD/ELECTED applications."""
        out: List[ElectionStructureRow] = []
        for app in self.get_applications_for_user(telegram_id):
            role = self.get_role_by_id(app.get("Role_ID", ""))
            if (
                role
                and role.get("Type") in ("BOARD", "ELECTED")
                and role.get("ID") != current_role_id
            ):
                out.append(role)
        return out

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[UserRow]:
        """Get a user by Telegram ID (includes queued upserts). Use this for all user lookups."""
        return self.sheets_manager.get_user_by_telegram_id(telegram_id)

    def get_all_users(self) -> List[UserRow]:
        """Get all users (sheet data plus queued upserts). Use this for consistent view of users."""
        return self.sheets_manager.get_all_users()

    def upsert_user(self, user: UserRow) -> bool:
        """Queue a user to be added or updated. Flush user queue for persistence."""
        return self.sheets_manager.upsert_user(user)

    def get_all_applications(self) -> List[ApplicationRow]:
        """Get all applications (sheet data plus queued and status updates)."""
        return self.sheets_manager.get_all_applications()

    def _build_users_by_id(self) -> Dict[int, UserRow]:
        """Build a lookup dict of users by Telegram_ID for efficient repeated lookups."""
        return {u["Telegram_ID"]: u for u in self.get_all_users()}

    def get_applicant_display(self, app: ApplicationRow) -> Optional[UserRow]:
        """Resolve Name, Email, Telegram for an application from Users sheet."""
        return self.get_user_by_telegram_id(app.get("Telegram_ID"))

    def get_applicant_display_names_for_announcement(
        self,
        role_id: str,
        application: ApplicationRow,
        users_by_id: Optional[Dict[int, UserRow]] = None,
    ) -> str:
        """Display name for announcements: single name or 'Name1, Name2' for groups."""
        group_id = get_group_id(application)

        # Single applicant (not in a group)
        if not group_id:
            if users_by_id is not None:
                user = users_by_id.get(application.get("Telegram_ID"))
            else:
                user = self.get_applicant_display(application)
            return get_user_name(user, "")

        # Group application - get all member names
        group_apps = self._get_applications_for_group(role_id, group_id)
        if users_by_id is not None:
            names = [
                get_user_name(users_by_id.get(app.get("Telegram_ID")), "(?)")
                for app in group_apps
            ]
        else:
            names = [
                get_user_name(self.get_applicant_display(app), "(?)")
                for app in group_apps
            ]
        return ", ".join(sorted(names))

    def get_applicant_display_names_for_role_and_name(
        self, role: ElectionStructureRow, applicant_name: str
    ) -> str:
        """Resolve display name(s) for a role+name (single or group). For use in replies."""
        apps = self._resolve_applications_by_name(role, applicant_name)
        if not apps:
            return applicant_name
        return self.get_applicant_display_names_for_announcement(
            role.get("ID"), apps[0]
        )

    def _get_applications_for_group(
        self,
        role_id: str,
        group_id: str,
        role_apps: Optional[List[ApplicationRow]] = None,
    ) -> List[ApplicationRow]:
        """Return all applications for this role with the given Group_ID."""
        normalized_group_id = group_id.strip()
        if not normalized_group_id:
            return []
        if role_apps is None:
            role_apps = self._get_applications_for_role(role_id)
        return [app for app in role_apps if get_group_id(app) == normalized_group_id]

    def _resolve_applications_by_name(
        self,
        role: ElectionStructureRow,
        name: str,
        users_by_id: Optional[Dict[int, UserRow]] = None,
        role_apps: Optional[List[ApplicationRow]] = None,
    ) -> List[ApplicationRow]:
        """Resolve name (single or 'Name1, Name2') to application(s) for a role.

        For single names: finds the application whose user Name matches.
        For comma-separated names: finds the group whose member names match exactly.
        Always expands to full group if the matched app is in a group.
        """
        role_id = role.get("ID", "")
        if role_apps is None:
            role_apps = self._get_applications_for_role(role_id)
        if users_by_id is None:
            users_by_id = self._build_users_by_id()

        # Comma-separated → group lookup
        if ", " in name:
            target_names = frozenset(n.strip() for n in name.split(","))
            seen_groups: set[str] = set()
            for app in role_apps:
                gid = get_group_id(app)
                if not gid or gid in seen_groups:
                    continue
                seen_groups.add(gid)
                group_apps = self._get_applications_for_group(
                    role_id, gid, role_apps=role_apps
                )
                group_names = frozenset(
                    get_user_name(users_by_id.get(a.get("Telegram_ID")), "")
                    for a in group_apps
                )
                if group_names == target_names:
                    return group_apps
            return []

        # Single name → find matching app, expand to group if applicable
        for app in role_apps:
            user = users_by_id.get(app.get("Telegram_ID"))
            if user is not None and user.get("Name") == name:
                gid = get_group_id(app)
                if gid:
                    return self._get_applications_for_group(
                        role_id, gid, role_apps=role_apps
                    )
                return [app]
        return []

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
        apps = self._resolve_applications_by_name(role, applicant_name)
        if not apps:
            return False, None

        role_id = role.get("ID", "")
        success = all(
            self.sheets_manager.update_application_status(
                role_id, app.get("Telegram_ID"), status="REMOVED"
            )
            for app in apps
        )
        return (success, apps[0]) if success else (False, None)

    def set_applicant_fiirumi(
        self, role: ElectionStructureRow, applicant_name: str, fiirumi_link: str
    ) -> bool:
        """Set the fiirumi link for an applicant (or whole group). Name can be single or 'Name1, Name2'."""
        role_id = role.get("ID", "")
        apps = self._resolve_applications_by_name(role, applicant_name)
        if not apps:
            return False

        for app in apps:
            self.sheets_manager.update_application_status(
                role_id, app.get("Telegram_ID"), fiirumi_post=fiirumi_link
            )
        return True

    def _validate_group_completeness(
        self,
        apps: List[ApplicationRow],
        names_set: set[str],
        role_id: str,
        users_by_id: Optional[Dict[int, UserRow]] = None,
    ) -> Optional[str]:
        """Validate that all group members are included when electing groups.

        Returns error message if validation fails, None if OK.
        """
        if users_by_id is None:
            users_by_id = self._build_users_by_id()

        role_apps = self._get_applications_for_role(role_id)
        for app in apps:
            group_id = get_group_id(app)
            if not group_id:
                continue

            # Get all applications in this group
            group_apps = self._get_applications_for_group(role_id, group_id, role_apps)
            group_names = {
                get_user_name(users_by_id.get(a.get("Telegram_ID")), "")
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

    def _resolve_names_to_apps(
        self, role: ElectionStructureRow, names: List[str]
    ) -> Tuple[List[ApplicationRow], List[str], Dict[int, UserRow]]:
        """Resolve a list of display names to applications for a role.

        Returns (resolved_apps, missing_names, users_by_id).
        """
        users_by_id = self._build_users_by_id()
        role_apps = self._get_applications_for_role(role.get("ID", ""))
        apps: List[ApplicationRow] = []
        missing: List[str] = []
        seen_ids: set[int] = set()
        for name in names:
            resolved = self._resolve_applications_by_name(
                role, name, users_by_id, role_apps
            )
            if resolved:
                for app in resolved:
                    tid = app.get("Telegram_ID")
                    if tid not in seen_ids:
                        seen_ids.add(tid)
                        apps.append(app)
            else:
                missing.append(name)
        return apps, missing, users_by_id

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
        apps, missing, users_by_id = self._resolve_names_to_apps(role, names)
        if missing:
            return False, f"Could not find applicant(s): {', '.join(missing)}"

        # Validate group completeness
        names_set = set(names)
        error_msg = self._validate_group_completeness(
            apps, names_set, role_id, users_by_id
        )
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
        apps, missing, _ = self._resolve_names_to_apps(role, names)
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

    def approve_application(self, role_id: str, telegram_id: int) -> bool:
        """Approve a pending application by updating its status to APPROVED."""
        try:
            return self.sheets_manager.update_application_status(
                role_id, telegram_id, status="APPROVED"
            )
        except Exception as e:
            logger.error("Error approving application: %s", e)
            return False

    def reject_application(self, role_id: str, telegram_id: int) -> bool:
        """Reject a pending application by marking it as DENIED."""
        try:
            return self.sheets_manager.update_application_status(
                role_id, telegram_id, status="DENIED"
            )
        except Exception as e:
            logger.error("Error rejecting application: %s", e)
            return False

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

    def flush_all_queues(self) -> None:
        """Flush all queues and invalidate caches in dependency order."""
        self.sheets_manager.flush_user_queue()
        self.sheets_manager.flush_application_queue()
        self.sheets_manager.flush_status_update_queue()
        self.sheets_manager.flush_channel_queue()
        self.sheets_manager.invalidate_caches()

    @property
    def channels(self) -> List[ChannelRow]:
        """Get all registered channels."""
        return self.sheets_manager.get_all_channels()  # type: ignore[no-any-return]

    def _applicants_for_role_enriched(
        self,
        role_apps: List[ApplicationRow],
        users_by_id: Optional[Dict[int, UserRow]] = None,
    ) -> List[ApplicationWithDisplay]:
        """Return enriched and group-merged applicants for one role.

        role_apps must already be filtered to this role and to APPROVED/ELECTED status.
        """
        enriched: List[ApplicationWithDisplay] = []
        for app in role_apps:
            user = (
                users_by_id.get(app.get("Telegram_ID"))
                if users_by_id is not None
                else self.get_user_by_telegram_id(app.get("Telegram_ID"))
            )
            if not user:
                logger.warning(
                    "Skipping application with missing user: Role_ID=%s, Telegram_ID=%s",
                    app.get("Role_ID"),
                    app.get("Telegram_ID"),
                )
                continue
            base = {k: v for k, v in app.items() if k not in _DISPLAY_KEYS}
            disp = ApplicationWithDisplay(
                **cast(ApplicationRow, base),
                Name=user.get("Name", ""),
                Email=user.get("Email", ""),
                Telegram=user.get("Telegram", ""),
            )
            enriched.append(disp)
        by_group: Dict[str, List[ApplicationWithDisplay]] = {}
        for app in enriched:
            gid = app.get("Group_ID") or ""
            key = gid if gid else f"_single_{app.get('Telegram_ID')}"
            by_group.setdefault(key, []).append(app)
        applicants: List[ApplicationWithDisplay] = []
        for group_apps in by_group.values():
            if len(group_apps) == 1:
                applicants.append(group_apps[0])
            else:
                first = group_apps[0]
                merged = first.copy()
                merged["Name"] = ", ".join(
                    a.get("Name", "") or "(?)" for a in group_apps
                )
                merged["Fiirumi_Post"] = next(
                    (
                        a.get("Fiirumi_Post", "")
                        for a in group_apps
                        if a.get("Fiirumi_Post")
                    ),
                    first.get("Fiirumi_Post", ""),
                )
                applicants.append(merged)
        return applicants

    def _build_election_data(self) -> List[DivisionData]:
        """Build full election dataset (divisions with roles and enriched applicants)."""
        roles = self.get_all_roles()
        all_applications = self.get_all_applications()
        users_by_id = self._build_users_by_id()
        # Bucket active approved/elected apps by Role_ID once: avoids scanning all apps per role.
        apps_by_role: Dict[str, List[ApplicationRow]] = {}
        for app in all_applications:
            if app.get("Status", "") in ("APPROVED", "ELECTED"):
                role_id = app.get("Role_ID")
                if role_id:
                    apps_by_role.setdefault(role_id, []).append(app)
        divisions_dict: Dict[str, DivisionData] = {}
        for role in roles:
            div_fi = role.get("Division_FI")
            div_en = role.get("Division_EN")
            if div_fi not in divisions_dict:
                divisions_dict[div_fi] = DivisionData(
                    Division_FI=div_fi, Division_EN=div_en, Roles=[]
                )
            applicants = self._applicants_for_role_enriched(
                apps_by_role.get(role.get("ID", ""), []), users_by_id
            )
            divisions_dict[div_fi]["Roles"].append(
                RoleData(
                    ID=role.get("ID", ""),
                    Role_FI=role.get("Role_FI", ""),
                    Role_EN=role.get("Role_EN", ""),
                    Amount=role.get("Amount"),
                    Deadline=role.get("Deadline"),
                    Type=role.get("Type", "NON_ELECTED"),
                    Applicants=applicants,
                    Division_FI=div_fi or "",
                    Division_EN=div_en or "",
                )
            )
        return list(divisions_dict.values())

    @property
    def vaalilakana_full(self) -> List[DivisionData]:
        """Get the full election dataset (all roles)."""
        return self._build_election_data()

    @property
    def vaalilakana(self) -> List[RoleData]:
        """Get only elected roles (BOARD, ELECTED) as a flat list."""
        return [
            role
            for division in self.vaalilakana_full
            for role in division.get("Roles", [])
            if role.get("Type") in ("BOARD", "ELECTED")
        ]

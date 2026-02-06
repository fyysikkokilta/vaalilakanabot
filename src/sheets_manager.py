"""Google Sheets integration for vaalilakana data management."""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast
from collections import deque
from cachetools import cached, TTLCache
import gspread
from google.oauth2.service_account import Credentials
from .utils import retry_on_api_error
from .types import (
    ApplicationRow,
    ApplicationStatus,
    ChannelRow,
    ElectionStructureRow,
    DivisionDict,
    UserRow,
)

from .config import GOOGLE_SHEET_URL, GOOGLE_CREDENTIALS_FILE

logger = logging.getLogger("vaalilakanabot")

# These are invalidated by the job queue every minute
_roles_cache = TTLCache(maxsize=1, ttl=300)
_applications_cache = TTLCache(maxsize=1, ttl=300)
_channels_cache = TTLCache(maxsize=1, ttl=300)
_users_cache = TTLCache(maxsize=1, ttl=300)

# Persistent storage for last known good values (mutate in place to avoid global statement)
_fallback_cache: Dict[str, Any] = {
    "roles": None,
    "applications": None,
    "channels": None,
    "users": None,
}


class SheetsManager:  # pylint: disable=too-many-public-methods,too-many-instance-attributes
    """Manages Google Sheets operations for election data."""

    def __init__(
        self,
        sheet_url: Optional[str] = None,
        credentials_file: Optional[str] = None,
    ) -> None:
        """Initialize Google Sheets connection."""

        self.sheet_url = sheet_url or GOOGLE_SHEET_URL
        self.credentials_file = credentials_file or GOOGLE_CREDENTIALS_FILE

        if not self.sheet_url:
            raise ValueError("Google Sheet URL must be provided")

        if not self.credentials_file:
            raise ValueError("Google Credentials file path must be provided")

        # Define required scopes for Google Sheets
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        self.client: Any = None
        self.spreadsheet: Any = None
        self.election_sheet: Any = None
        self.applications_sheet: Any = None
        self.channels_sheet: Any = None
        self.users_sheet: Any = None

        # Application queue for batching
        self.application_queue: deque[ApplicationRow] = deque()

        # Status update queue for batching (processed after application queue)
        self.status_update_queue: deque[Dict[str, Any]] = deque()

        # Channel operation queues for batching
        self.channel_add_queue: deque[int] = deque()
        self.channel_remove_queue: deque[int] = deque()

        # User operation queues for batching
        self.user_upsert_queue: deque[UserRow] = deque()

        self._connect()

    def _connect(self) -> None:
        """Establish connection to Google Sheets."""
        try:
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(
                    f"Google credentials file not found: {self.credentials_file}"
                )

            # Use service account credentials file
            creds: Credentials = Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                self.credentials_file, scopes=self.scopes
            )

            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_url(self.sheet_url)

            # Get or create worksheets
            self._setup_worksheets()

            logger.info("Successfully connected to Google Sheets")

        except Exception as e:
            logger.error("Failed to connect to Google Sheets: %s", e)
            raise

    def _setup_worksheets(self) -> None:
        """Set up required worksheets with proper headers."""
        # Get or create Election Structure sheet
        try:
            self.election_sheet = self.spreadsheet.worksheet("Election Structure")
        except gspread.WorksheetNotFound:
            self.election_sheet = self.spreadsheet.add_worksheet(
                title="Election Structure", rows=1000, cols=8
            )
            # Add headers
            headers = [
                "ID",
                "Division_FI",
                "Division_EN",
                "Role_FI",
                "Role_EN",
                "Type",
                "Amount",
                "Deadline",
            ]
            self.election_sheet.update("A1:H1", [headers])

        # Get or create Applications sheet
        try:
            self.applications_sheet = self.spreadsheet.worksheet("Applications")
        except gspread.WorksheetNotFound:
            self.applications_sheet = self.spreadsheet.add_worksheet(
                title="Applications", rows=1000, cols=7
            )
            # Add headers (user info lives in Users sheet)
            headers = [
                "Timestamp",
                "Role_ID",
                "Telegram_ID",
                "Fiirumi_Post",
                "Status",
                "Language",
                "Group_ID",
            ]
            self.applications_sheet.update("A1:G1", [headers])

        # Get or create Channels sheet
        try:
            self.channels_sheet = self.spreadsheet.worksheet("Channels")
        except gspread.WorksheetNotFound:
            self.channels_sheet = self.spreadsheet.add_worksheet(
                title="Channels", rows=1000, cols=2
            )
            # Add headers
            headers = ["Chat_ID", "Added_Date"]
            self.channels_sheet.update("A1:B1", [headers])

        # Get or create Users sheet
        try:
            self.users_sheet = self.spreadsheet.worksheet("Users")
        except gspread.WorksheetNotFound:
            self.users_sheet = self.spreadsheet.add_worksheet(
                title="Users", rows=1000, cols=6
            )
            # Add headers (single consent: show on website's official page)
            headers = [
                "Telegram_ID",
                "Name",
                "Email",
                "Telegram",
                "Show_On_Website_Consent",
                "Updated_At",
            ]
            self.users_sheet.update("A1:F1", [headers])

    def invalidate_caches(self) -> None:
        """Invalidate all caches."""
        _roles_cache.clear()
        _applications_cache.clear()
        _channels_cache.clear()
        _users_cache.clear()
        for key in _fallback_cache:
            _fallback_cache[key] = None

    @retry_on_api_error(max_retries=3, backoff_factor=2.0)
    def _get_all_values_with_retry(self, worksheet: Any) -> List[List[Any]]:
        """Get all values from a worksheet with retry logic."""
        return cast(List[List[Any]], worksheet.get_all_values())

    @retry_on_api_error(max_retries=3, backoff_factor=2.0)
    def _get_all_records_with_retry(self, worksheet: Any) -> List[Dict[str, Any]]:
        """Get all records from a worksheet with retry logic."""
        return cast(List[Dict[str, Any]], worksheet.get_all_records())

    @retry_on_api_error(max_retries=3, backoff_factor=2.0)
    def _batch_update_with_retry(
        self, worksheet: Any, updates: List[Dict[str, Any]]
    ) -> None:
        """Perform batch update on a worksheet with retry logic."""
        worksheet.batch_update(updates)

    @retry_on_api_error(max_retries=3, backoff_factor=2.0)
    def _update_with_retry(
        self, worksheet: Any, range_str: str, values: List[List[Any]]
    ) -> None:
        """Perform update on a worksheet with retry logic."""
        worksheet.update(range_str, values)

    @retry_on_api_error(max_retries=3, backoff_factor=2.0)
    def _delete_rows_with_retry(self, worksheet: Any, row_index: int) -> None:
        """Delete a row from a worksheet with retry logic."""
        worksheet.delete_rows(row_index)

    def _collect_missing_role_id_updates(
        self, all_values: List[List[Any]], headers: List[Any]
    ) -> List[Dict[str, Any]]:
        """Build batch updates for role rows that are missing an ID."""
        id_col = headers.index("ID") + 1
        div_fi_col = headers.index("Division_FI") + 1
        role_fi_col = headers.index("Role_FI") + 1
        updates = []
        for row_idx, row in enumerate(all_values[1:], start=2):
            id_val = row[id_col - 1] if len(row) >= id_col else ""
            if not id_val:
                div_fi = row[div_fi_col - 1] if len(row) >= div_fi_col else ""
                role_fi = row[role_fi_col - 1] if len(row) >= role_fi_col else ""
                if div_fi and role_fi:
                    updates.append(
                        {
                            "range": f"{chr(64 + id_col)}{row_idx}",
                            "values": [[str(uuid.uuid4())]],
                        }
                    )
        return updates

    @cached(cache=_roles_cache)  # type: ignore[untyped-decorator]
    def get_all_roles(self) -> List[ElectionStructureRow]:
        """Get all roles with caching and ensure IDs exist when cache refreshes."""
        if self.election_sheet is None:
            return []
        try:
            all_values: List[List[Any]] = self._get_all_values_with_retry(
                self.election_sheet
            )
            if not all_values:
                fallback_roles = _fallback_cache.get("roles")
                if fallback_roles:
                    logger.warning("Empty data from sheets, using last known roles")
                    return cast(List[ElectionStructureRow], fallback_roles)
                return []

            headers = all_values[0]
            updates = self._collect_missing_role_id_updates(all_values, headers)
            if updates:
                self._batch_update_with_retry(self.election_sheet, updates)
                logger.info("Assigned IDs to %s role rows without IDs", len(updates))

            result: List[Dict[str, Any]] = self._get_all_records_with_retry(
                self.election_sheet
            )
            _fallback_cache["roles"] = result
            return cast(List[ElectionStructureRow], result)

        except Exception as e:
            logger.error("Error getting roles: %s", e)
            fallback_val = _fallback_cache.get("roles")
            if fallback_val:
                logger.warning("Returning last known roles due to error")
                return cast(List[ElectionStructureRow], fallback_val)
            return []

    def get_divisions(self) -> List[DivisionDict]:
        """Get unique divisions (derived from cached roles)."""
        roles = self.get_all_roles()
        divisions: Dict[str, DivisionDict] = {}
        for role in roles:
            Division_FI = role.get("Division_FI")
            Division_EN = role.get("Division_EN")
            if Division_FI not in divisions:
                divisions[Division_FI] = DivisionDict(
                    Division_FI=Division_FI, Division_EN=Division_EN
                )
        return list(divisions.values())

    def find_role_by_name(self, role_name: str) -> Optional[ElectionStructureRow]:
        """Find a role by Finnish or English name using cached roles."""
        if not role_name:
            return None
        all_roles = self.get_all_roles()
        return next(
            (r for r in all_roles if role_name in (r.get("Role_FI"), r.get("Role_EN"))),
            None,
        )

    def get_role_by_id(self, role_id: str) -> Optional[ElectionStructureRow]:
        """Get a role by ID using cached roles."""
        all_roles = self.get_all_roles()
        found = next((role for role in all_roles if role.get("ID") == role_id), None)
        return found

    @cached(cache=_applications_cache)  # type: ignore[untyped-decorator]
    def get_all_applications_from_sheets(self) -> List[ApplicationRow]:
        """Get all applications with caching (1 minute TTL)."""
        if self.applications_sheet is None:
            return []
        try:
            result: List[Dict[str, Any]] = self._get_all_records_with_retry(
                self.applications_sheet
            )
            _fallback_cache["applications"] = result
            return cast(List[ApplicationRow], result)
        except Exception as e:
            logger.error("Error getting all applications: %s", e)
            fallback_val = _fallback_cache.get("applications")
            if fallback_val:
                logger.warning("Returning last known applications due to error")
                return cast(List[ApplicationRow], fallback_val)
            return []

    def get_all_applications(self) -> List[ApplicationRow]:
        """Get all applications with caching (1 minute TTL)."""
        try:
            sheet_applications = self.get_all_applications_from_sheets()

            # Add queue applications to sheet applications
            queue_applications = list(self.application_queue)
            all_applications = sheet_applications + queue_applications

            # Apply status updates to all applications
            status_updates = self.status_update_queue.copy()

            for status_update in status_updates:
                for app in all_applications:
                    if (
                        app.get("Role_ID") == status_update.get("Role_ID")
                        and app.get("Telegram_ID") == status_update.get("Telegram_ID")
                        and app.get("Status") not in ("DENIED", "REMOVED")
                    ):
                        if status_update.get("Status") is not None:
                            app["Status"] = cast(
                                ApplicationStatus, status_update.get("Status")
                            )
                        if status_update.get("Fiirumi_Post") is not None:
                            app["Fiirumi_Post"] = cast(
                                str, status_update.get("Fiirumi_Post")
                            )
                        if status_update.get("Group_ID") is not None:
                            app["Group_ID"] = cast(str, status_update.get("Group_ID"))
                        break

            return all_applications
        except Exception as e:
            logger.error("Error getting all applications: %s", e)
            return []

    def add_application(
        self,
        applicant: ApplicationRow,
    ) -> bool:
        """Queue a new application for batch processing."""
        try:
            role_id = applicant.get("Role_ID")
            telegram_id = applicant.get("Telegram_ID")

            # Check if application is already in queue
            for queued_app in self.application_queue:
                if (
                    queued_app.get("Role_ID") == role_id
                    and queued_app.get("Telegram_ID") == telegram_id
                ):
                    logger.warning(
                        "Application already queued for role %s and user %s",
                        role_id,
                        telegram_id,
                    )
                    return False

            self.application_queue.append(applicant)

            logger.info(
                "Queued application for role %s by user %s", role_id, telegram_id
            )
            return True

        except Exception as e:
            logger.error("Error queueing application: %s", e)
            return False

    def flush_application_queue(self) -> bool:
        """Flush all queued applications to Google Sheets in a single batch operation."""
        if self.applications_sheet is None:
            return False
        applications_to_add: List[ApplicationRow] = []
        try:
            if not self.application_queue:
                logger.debug("No applications in queue to flush")
                return True

            # Convert queue to list and clear queue
            applications_to_add = list(self.application_queue)
            self.application_queue.clear()

            if len(applications_to_add) == 0:
                logger.info("No new applications to add (all were duplicates)")
                return True

            # Find the starting row for new applications
            start_row = len(self.applications_sheet.col_values(1)) + 1

            # Prepare batch data
            batch_data: List[List[Any]] = []
            for app in applications_to_add:
                row_data = [
                    app.get("Timestamp"),
                    app.get("Role_ID"),
                    app.get("Telegram_ID"),
                    app.get("Fiirumi_Post"),
                    app.get("Status"),
                    app.get("Language"),
                    app.get("Group_ID", ""),
                ]
                batch_data.append(row_data)

            # Calculate the range for batch update
            end_row = start_row + len(batch_data) - 1
            range_str = f"A{start_row}:G{end_row}"

            # Perform batch update with retry
            self._update_with_retry(self.applications_sheet, range_str, batch_data)

            logger.info(
                "Flushed %d applications from queue to sheets", len(applications_to_add)
            )
            return True

        except Exception as e:
            logger.error("Error flushing application queue: %s", e)
            # Re-queue the applications if they failed to flush
            for app in applications_to_add:
                self.application_queue.append(app)
            return False

    def update_application_status(
        self, role_id: str, telegram_id: int, **kwargs: Any
    ) -> bool:
        """Queue an application status update. kwargs: status, fiirumi_post, group_id."""
        status = kwargs.get("status")
        fiirumi_post = kwargs.get("fiirumi_post")
        group_id = kwargs.get("group_id")
        try:
            for queued_update in self.status_update_queue:
                if (
                    queued_update.get("Role_ID") == role_id
                    and queued_update.get("Telegram_ID") == telegram_id
                ):
                    if status is not None:
                        queued_update["Status"] = status
                    if fiirumi_post is not None:
                        queued_update["Fiirumi_Post"] = fiirumi_post
                    if group_id is not None:
                        queued_update["Group_ID"] = group_id
                    logger.info(
                        "Updated queued status change for role %s, user %s",
                        role_id,
                        telegram_id,
                    )
                    return True

            status_update = {
                "Role_ID": role_id,
                "Telegram_ID": telegram_id,
                "Status": status,
                "Fiirumi_Post": fiirumi_post,
                "Group_ID": group_id or "",
            }
            self.status_update_queue.append(status_update)
            logger.info(
                "Queued status update for role %s, user %s",
                role_id,
                telegram_id,
            )
            return True

        except Exception as e:
            logger.error("Error queueing status update: %s", e)
            return False

    def _row_updates_for_status_update(
        self,
        update_data: Dict[str, Any],
        all_data: List[List[Any]],
        headers: List[Any],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Return (list of range/values updates for one row, found)."""
        cols = {
            k: headers.index(k) + 1
            for k in ("Role_ID", "Telegram_ID", "Status", "Fiirumi_Post", "Group_ID")
        }
        role_id = update_data.get("Role_ID")
        telegram_id = update_data.get("Telegram_ID")
        status = update_data.get("Status")
        fiirumi_post = update_data.get("Fiirumi_Post")
        group_id = update_data.get("Group_ID")
        for i, row in enumerate(all_data[1:], start=2):
            if (
                len(row) > max(cols["Role_ID"], cols["Telegram_ID"]) - 1
                and row[cols["Role_ID"] - 1] == role_id
                and str(row[cols["Telegram_ID"] - 1]) == str(telegram_id)
                and row[cols["Status"] - 1] not in ("DENIED", "REMOVED")
            ):
                out = []
                if status is not None:
                    out.append(
                        {
                            "range": f"{chr(64 + cols['Status'])}{i}",
                            "values": [[status]],
                        }
                    )
                if fiirumi_post is not None:
                    out.append(
                        {
                            "range": f"{chr(64 + cols['Fiirumi_Post'])}{i}",
                            "values": [[fiirumi_post]],
                        }
                    )
                if group_id and group_id != "":
                    out.append(
                        {
                            "range": f"{chr(64 + cols['Group_ID'])}{i}",
                            "values": [[group_id]],
                        }
                    )
                return out, True
        logger.warning(
            "Application not found for queued status update: role %s, user %s",
            role_id,
            telegram_id,
        )
        return [], False

    def _compute_status_update_batch(
        self,
        all_data: List[List[Any]],
        headers: List[Any],
        updates_to_process: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Compute batch updates and processed count for status update queue flush."""
        batch_updates = []
        processed_count = 0
        for update_data in updates_to_process:
            row_updates, found = self._row_updates_for_status_update(
                update_data, all_data, headers
            )
            batch_updates.extend(row_updates)
            if found:
                processed_count += 1
        return batch_updates, processed_count

    def flush_status_update_queue(self) -> bool:
        """Flush all queued status updates to Google Sheets in a single batch operation."""
        if self.applications_sheet is None:
            return False
        updates_to_process: List[Dict[str, Any]] = []
        try:
            if not self.status_update_queue:
                logger.debug("No status updates in queue to flush")
                return True
            updates_to_process = list(self.status_update_queue)
            self.status_update_queue.clear()
            all_data: List[List[Any]] = self._get_all_values_with_retry(
                self.applications_sheet
            )
            headers = all_data[0]
            batch_updates, processed_count = self._compute_status_update_batch(
                all_data, headers, updates_to_process
            )
            if batch_updates:
                self._batch_update_with_retry(self.applications_sheet, batch_updates)
            logger.info(
                "Flushed %d status updates from queue to sheets", processed_count
            )
            return True
        except Exception as e:
            logger.error("Error flushing status update queue: %s", e)
            for update_data in updates_to_process:
                self.status_update_queue.append(update_data)
            return False

    def flush_channel_queue(self) -> bool:
        """Flush all queued channel operations to Google Sheets in batch operations."""
        if self.channels_sheet is None:
            return False
        channels_to_add: List[int] = []
        channels_to_remove: List[int] = []

        try:
            # Process channel additions
            if self.channel_add_queue:
                channels_to_add = list(self.channel_add_queue)
                self.channel_add_queue.clear()

                # Prepare batch data for additions
                current_row = len(self.channels_sheet.col_values(1)) + 1
                batch_data: List[List[Any]] = []

                for chat_id in channels_to_add:
                    batch_data.append([chat_id, datetime.now().isoformat()])

                if batch_data:
                    range_end = current_row + len(batch_data) - 1
                    self._update_with_retry(
                        self.channels_sheet, f"A{current_row}:B{range_end}", batch_data
                    )
                    logger.info("Added %d channels in batch", len(batch_data))

            # Process channel removals
            if self.channel_remove_queue:
                channels_to_remove = list[int](self.channel_remove_queue)
                self.channel_remove_queue.clear()

                # Get current sheet data with retry
                all_data: List[List[Any]] = self._get_all_values_with_retry(
                    self.channels_sheet
                )

                # Find rows to delete (collect indices in reverse order)
                rows_to_delete: List[int] = []
                for i, row in enumerate(all_data[1:], start=2):  # Start from row 2
                    if (
                        len(row) > 0
                        and int(str(row[0]).replace("−", "-")) in channels_to_remove
                    ):
                        rows_to_delete.append(i)

                # Delete rows in reverse order to maintain correct indices
                for row_index in reversed(rows_to_delete):
                    self._delete_rows_with_retry(self.channels_sheet, row_index)

                logger.info("Removed %d channels in batch", len(rows_to_delete))

            return True

        except Exception as e:
            logger.error("Error flushing channel queue: %s", e)
            # Re-queue the operations if they failed to flush
            for chat_id in channels_to_add:
                self.channel_add_queue.append(chat_id)
            for chat_id in channels_to_remove:
                self.channel_remove_queue.append(chat_id)
            return False

    # Channel management methods
    @cached(cache=_channels_cache)  # type: ignore[untyped-decorator]
    def get_all_channels(self) -> List[ChannelRow]:
        """Get all registered channels."""
        if self.channels_sheet is None:
            return []
        try:
            all_data: List[Dict[str, Any]] = self._get_all_records_with_retry(
                self.channels_sheet
            )
            unique_ids = {
                int(str(record.get("Chat_ID", "")).replace("−", "-"))
                for record in all_data
            }
            result: List[ChannelRow] = [
                ChannelRow(Channel_ID=chat_id) for chat_id in unique_ids
            ]
            _fallback_cache["channels"] = result
            return result
        except Exception as e:
            logger.error("Error getting channels: %s", e)
            fallback_val = _fallback_cache.get("channels")
            if fallback_val:
                logger.warning("Returning last known channels due to error")
                return cast(List[ChannelRow], fallback_val)
            return []

    def _queue_channel_op(self, chat_id: int, for_addition: bool) -> bool:
        """Queue a channel add or remove. Returns False only when removing non-existent channel."""
        my_queue = self.channel_add_queue if for_addition else self.channel_remove_queue
        other_queue = (
            self.channel_remove_queue if for_addition else self.channel_add_queue
        )
        if chat_id in my_queue:
            logger.info(
                "Channel %s already queued for %s",
                chat_id,
                "addition" if for_addition else "removal",
            )
            return True
        try:
            other_queue.remove(chat_id)
            logger.info(
                "Cancelled %s: removed channel %s from %s queue",
                "removal" if for_addition else "addition",
                chat_id,
                "remove" if for_addition else "add",
            )
            return True
        except ValueError:
            pass
        existing = any(c.get("Channel_ID") == chat_id for c in self.get_all_channels())
        if for_addition and existing:
            logger.info("Channel %s already exists", chat_id)
            return True
        if not for_addition and not existing:
            logger.warning("Channel %s not found", chat_id)
            return False
        my_queue.append(chat_id)
        logger.info(
            "Queued channel %s for %s",
            chat_id,
            "addition" if for_addition else "removal",
        )
        return True

    def add_channel(self, chat_id: int) -> bool:
        """Queue a channel to be added."""
        try:
            return self._queue_channel_op(chat_id, for_addition=True)
        except Exception as e:
            logger.error("Error queueing channel addition: %s", e)
            return False

    def remove_channel(self, chat_id: int) -> bool:
        """Queue a channel to be removed."""
        try:
            return self._queue_channel_op(chat_id, for_addition=False)
        except Exception as e:
            logger.error("Error queueing channel removal: %s", e)
            return False

    # User management methods
    @cached(cache=_users_cache)  # type: ignore[untyped-decorator]
    def get_all_users_from_sheets(self) -> List[UserRow]:
        """Get all users from the sheet with caching (TTL). Used by get_all_users()."""
        if self.users_sheet is None:
            return []
        try:
            all_data: List[Dict[str, Any]] = self._get_all_records_with_retry(
                self.users_sheet
            )
            result: List[UserRow] = []
            for record in all_data:
                user = UserRow(
                    Telegram_ID=int(record.get("Telegram_ID", 0)),
                    Name=record.get("Name", ""),
                    Email=record.get("Email", ""),
                    Telegram=record.get("Telegram", ""),
                    Show_On_Website_Consent=record.get(
                        "Show_On_Website_Consent", "FALSE"
                    )
                    == "TRUE",
                    Updated_At=record.get("Updated_At", ""),
                )
                result.append(user)
            _fallback_cache["users"] = result
            return result
        except Exception as e:
            logger.error("Error getting users: %s", e)
            fallback_val = _fallback_cache.get("users")
            if fallback_val:
                logger.warning("Returning last known users due to error")
                return cast(List[UserRow], fallback_val)
            return []

    def get_all_users(self) -> List[UserRow]:
        """Get all users: sheet data plus queued upserts. Use this everywhere for immediate visibility of changes."""
        try:
            sheet_users = self.get_all_users_from_sheets()
            if not self.user_upsert_queue:
                return sheet_users
            result: List[UserRow] = list(sheet_users)
            for queued in self.user_upsert_queue:
                telegram_id = queued.get("Telegram_ID")
                found = next(
                    (
                        i
                        for i, u in enumerate(result)
                        if u.get("Telegram_ID") == telegram_id
                    ),
                    None,
                )
                if found is not None:
                    result[found] = queued
                else:
                    result.append(queued)
            return result
        except Exception as e:
            logger.error("Error getting all users: %s", e)
            return []

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[UserRow]:
        """Get a user by Telegram ID (includes queued upserts)."""
        all_users = self.get_all_users()
        return next(
            (user for user in all_users if user.get("Telegram_ID") == telegram_id), None
        )

    def upsert_user(self, user: UserRow) -> bool:
        """Queue a user to be added or updated."""
        try:
            telegram_id = user.get("Telegram_ID")

            # Check if already queued
            for queued_user in self.user_upsert_queue:
                if queued_user.get("Telegram_ID") == telegram_id:
                    # Update the existing queue entry in place (UserRow keys)
                    queued_user["Name"] = user.get("Name", "")
                    queued_user["Email"] = user.get("Email", "")
                    queued_user["Telegram"] = user.get("Telegram", "")
                    queued_user["Show_On_Website_Consent"] = user.get(
                        "Show_On_Website_Consent", False
                    )
                    queued_user["Updated_At"] = user.get("Updated_At", "")
                    logger.info("Updated queued user info for user %s", telegram_id)
                    return True

            # Add to queue
            self.user_upsert_queue.append(user)
            logger.info("Queued user info for user %s", telegram_id)
            return True

        except Exception as e:
            logger.error("Error queueing user upsert: %s", e)
            return False

    def _prepare_user_flush_batch(
        self,
        all_data: List[List[Any]],
        headers: List[Any],
        users_to_process: List[UserRow],
    ) -> Tuple[List[Dict[str, Any]], List[List[Any]]]:
        """Compute batch updates and new user rows for user queue flush."""
        telegram_id_col = headers.index("Telegram_ID") + 1
        batch_updates = []
        new_users = []
        for user in users_to_process:
            telegram_id = user.get("Telegram_ID")
            user_row_index = None
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) > telegram_id_col - 1 and str(
                    row[telegram_id_col - 1]
                ) == str(telegram_id):
                    user_row_index = i
                    break
            user_data = [
                user.get("Telegram_ID"),
                user.get("Name"),
                user.get("Email"),
                user.get("Telegram"),
                "TRUE" if user.get("Show_On_Website_Consent") else "FALSE",
                user.get("Updated_At"),
            ]
            if user_row_index:
                batch_updates.append(
                    {
                        "range": f"A{user_row_index}:F{user_row_index}",
                        "values": [user_data],
                    }
                )
            else:
                new_users.append(user_data)
        return batch_updates, new_users

    def flush_user_queue(self) -> bool:
        """Flush all queued user operations to Google Sheets."""
        if self.users_sheet is None:
            return False
        users_to_process: List[UserRow] = []
        try:
            if not self.user_upsert_queue:
                logger.debug("No users in queue to flush")
                return True
            users_to_process = list(self.user_upsert_queue)
            self.user_upsert_queue.clear()
            all_data: List[List[Any]] = self._get_all_values_with_retry(
                self.users_sheet
            )
            headers = all_data[0]
            batch_updates, new_users = self._prepare_user_flush_batch(
                all_data, headers, users_to_process
            )
            if batch_updates:
                self._batch_update_with_retry(self.users_sheet, batch_updates)
                logger.info("Updated %d existing users", len(batch_updates))
            if new_users:
                start_row = len(all_data) + 1
                end_row = start_row + len(new_users) - 1
                self._update_with_retry(
                    self.users_sheet,
                    f"A{start_row}:F{end_row}",
                    new_users,
                )
                logger.info("Added %d new users", len(new_users))
            return True
        except Exception as e:
            logger.error("Error flushing user queue: %s", e)
            for user in users_to_process:
                self.user_upsert_queue.append(user)
            return False

"""Google Sheets integration for vaalilakana data management."""

import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
from cachetools import cached, TTLCache
import gspread
from google.oauth2.service_account import Credentials
from .types import (
    ApplicationRow,
    ChannelRow,
    DivisionData,
    ElectionStructureRow,
    DivisionDict,
)

from .config import GOOGLE_SHEET_URL, GOOGLE_CREDENTIALS_FILE

logger = logging.getLogger("vaalilakanabot")

# These are invalidated by the job queue every minute
_roles_cache = TTLCache(maxsize=1, ttl=300)
_applications_cache = TTLCache(maxsize=1, ttl=300)
_channels_cache = TTLCache(maxsize=1, ttl=300)


class SheetsManager:  # pylint: disable=too-many-public-methods
    """Manages Google Sheets operations for election data."""

    def __init__(self, sheet_url: str = None, credentials_file: str = None):
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

        self.client = None
        self.spreadsheet = None
        self.election_sheet = None
        self.applications_sheet = None
        self.channels_sheet = None

        # Application queue for batching
        self.application_queue: deque[ApplicationRow] = deque()

        # Status update queue for batching (processed after application queue)
        self.status_update_queue: deque[ApplicationRow] = deque()

        # Channel operation queues for batching
        self.channel_add_queue: deque[int] = deque()
        self.channel_remove_queue: deque[int] = deque()

        self._connect()

    def _connect(self):
        """Establish connection to Google Sheets."""
        try:
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(
                    f"Google credentials file not found: {self.credentials_file}"
                )

            # Use service account credentials file
            creds = Credentials.from_service_account_file(
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

    def _setup_worksheets(self):
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
                title="Applications", rows=1000, cols=8
            )
            # Add headers
            headers = [
                "Role_ID",
                "Telegram_ID",
                "Name",
                "Email",
                "Telegram",
                "Fiirumi_Post",
                "Status",
                "Language",
            ]
            self.applications_sheet.update("A1:H1", [headers])

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

    def generate_role_id(self) -> str:
        """Generate a unique role ID using UUID4."""
        return str(uuid.uuid4())

    @cached(cache=_roles_cache)
    def get_all_roles(self) -> List[ElectionStructureRow]:
        """Get all roles with caching and ensure IDs exist when cache refreshes.
        Also ensures that every role has a unique ID."""
        try:
            all_values = self.election_sheet.get_all_values()
            if not all_values:
                return []

            headers = all_values[0]
            id_col = headers.index("ID") + 1
            div_fi_col = headers.index("Division_FI") + 1
            role_fi_col = headers.index("Role_FI") + 1

            # Collect all missing IDs for bulk update
            updates = []
            for row_idx, row in enumerate(all_values[1:], start=2):
                id_val = row[id_col - 1] if len(row) >= id_col else ""
                if not id_val:
                    division_fi = row[div_fi_col - 1] if len(row) >= div_fi_col else ""
                    role_fi = row[role_fi_col - 1] if len(row) >= role_fi_col else ""
                    if division_fi and role_fi:
                        new_id = self.generate_role_id()
                        # Store the cell reference and new ID for bulk update
                        updates.append(
                            {
                                "range": f"{chr(64 + id_col)}{row_idx}",  # Convert column number to letter
                                "values": [[new_id]],
                            }
                        )

            # Perform bulk update if there are missing IDs
            if updates:
                self.election_sheet.batch_update(updates)
                logger.info("Assigned IDs to %s role rows without IDs", len(updates))

            return self.election_sheet.get_all_records()

        except Exception as e:
            logger.error("Error getting roles: %s", e)
            return []

    def get_divisions(self) -> List[DivisionDict]:
        """Get unique divisions (derived from cached roles)."""
        roles = self.get_all_roles()
        divisions: Dict[str, DivisionDict] = {}
        for role in roles:
            div_fi = role.get("Division_FI")
            div_en = role.get("Division_EN")
            if div_fi not in divisions:
                divisions[div_fi] = {"fi": div_fi, "en": div_en}
        return list(divisions.values())

    def find_role_by_name(self, role_name: str) -> Optional[ElectionStructureRow]:
        """Find a role by Finnish or English name using cached roles."""
        if not role_name:
            return None

        all_roles = self.get_all_roles()

        # Search for exact match first
        for role in all_roles:
            if role_name in (role.get("Role_FI"), role.get("Role_EN")):
                return role

        return None

    @cached(cache=_applications_cache)
    def get_all_applications(self) -> List[ApplicationRow]:
        """Get all applications with caching (1 minute TTL)."""
        try:
            return self.applications_sheet.get_all_records()
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
            # Check if application already exists
            if self.get_existing_application(role_id, telegram_id):
                logger.warning(
                    "Application already exists for role %s and user %s",
                    role_id,
                    telegram_id,
                )
                return False

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
        try:
            if not self.application_queue:
                logger.debug("No applications in queue to flush")
                return True

            # Convert queue to list and clear queue
            applications_to_add = list(self.application_queue)
            self.application_queue.clear()

            # Double-check for existing applications (in case they were added while queued)
            new_applications = []
            for app in applications_to_add:
                if not self.get_existing_application(
                    app.get("Role_ID"), app.get("Telegram_ID")
                ):
                    new_applications.append(app)
                else:
                    logger.warning(
                        "Skipping duplicate application for role %s and user %s",
                        app.get("Role_ID"),
                        app.get("Telegram_ID"),
                    )

            if not new_applications:
                logger.info("No new applications to add (all were duplicates)")
                return True

            # Find the starting row for new applications
            start_row = len(self.applications_sheet.col_values(1)) + 1

            # Prepare batch data
            batch_data = []
            for app in new_applications:
                row_data = [
                    app.get("Role_ID"),
                    app.get("Telegram_ID"),
                    app.get("Name"),
                    app.get("Email"),
                    app.get("Telegram"),
                    app.get("Fiirumi_Post"),
                    app.get("Status"),
                    app.get("Language"),
                ]
                batch_data.append(row_data)

            # Calculate the range for batch update
            end_row = start_row + len(batch_data) - 1
            range_str = f"A{start_row}:H{end_row}"

            # Perform batch update
            self.applications_sheet.update(range_str, batch_data)

            logger.info(
                "Flushed %d applications from queue to sheets", len(new_applications)
            )
            return True

        except Exception as e:
            logger.error("Error flushing application queue: %s", e)
            # Re-queue the applications if they failed to flush
            for app in applications_to_add:
                self.application_queue.append(app)
            return False

    def get_existing_application(
        self, role_id: str, telegram_id: int
    ) -> Optional[ApplicationRow]:
        """Get existing application for a role and user."""
        try:
            applications = self.get_applications_for_role(role_id)
            return next(
                (app for app in applications if app.get("Telegram_ID") == telegram_id),
                None,
            )
        except Exception as e:
            logger.error("Error getting existing application: %s", e)
            return None

    def get_applications_for_role(self, role_id: str) -> List[ApplicationRow]:
        """Get all applications for a specific role."""
        try:
            all_applications = self.get_all_applications()
            return [app for app in all_applications if app.get("Role_ID") == role_id]
        except Exception as e:
            logger.error("Error getting applications for role %s: %s", role_id, e)
            return []

    def get_applications_for_user(self, telegram_id: int) -> List[ApplicationRow]:
        """Get all applications for a specific user."""
        try:
            all_applications = self.get_all_applications()
            return [
                app for app in all_applications if app.get("Telegram_ID") == telegram_id
            ]
        except Exception as e:
            logger.error("Error getting applications for user %s: %s", telegram_id, e)
            return []

    def update_application_status(
        self,
        role_id: str,
        telegram_id: int,
        status: str = None,
        fiirumi_post: str = None,
    ) -> bool:
        """Queue an application status update for batch processing."""
        try:
            # Check if there's already an update for this application in the queue
            for queued_update in self.status_update_queue:
                if (
                    queued_update.get("Role_ID") == role_id
                    and queued_update.get("Telegram_ID") == telegram_id
                ):
                    # Update existing queue entry
                    if status is not None:
                        queued_update["Status"] = status
                    if fiirumi_post is not None:
                        queued_update["Fiirumi_Post"] = fiirumi_post
                    logger.info(
                        "Updated queued status change for role %s, user %s",
                        role_id,
                        telegram_id,
                    )
                    return True

            # Add new status update to queue
            status_update = ApplicationRow(
                Role_ID=role_id,
                Telegram_ID=telegram_id,
                Status=status,
                Fiirumi_Post=fiirumi_post,
            )
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

    def flush_status_update_queue(self) -> bool:
        """Flush all queued status updates to Google Sheets in a single batch operation."""
        try:
            if not self.status_update_queue:
                logger.debug("No status updates in queue to flush")
                return True

            # Convert queue to list and clear queue
            updates_to_process = list(self.status_update_queue)
            self.status_update_queue.clear()

            # Get current sheet data once
            all_data = self.applications_sheet.get_all_values()
            headers = all_data[0]

            # Find column indices
            role_id_col = headers.index("Role_ID") + 1
            telegram_id_col = headers.index("Telegram_ID") + 1
            status_col = headers.index("Status") + 1
            fiirumi_col = headers.index("Fiirumi_Post") + 1

            # Prepare batch updates
            batch_updates = []
            processed_count = 0

            for update_data in updates_to_process:
                role_id = update_data.get("Role_ID")
                telegram_id = update_data.get("Telegram_ID")
                status = update_data.get("Status")
                fiirumi_post = update_data.get("Fiirumi_Post")

                # Find the row for this application
                row_found = False
                for i, row in enumerate(all_data[1:], start=2):  # Start from row 2
                    if (
                        len(row) > max(role_id_col, telegram_id_col) - 1
                        and row[role_id_col - 1] == role_id
                        and str(row[telegram_id_col - 1]) == str(telegram_id)
                    ):
                        # Add updates for this row
                        if status is not None:
                            batch_updates.append(
                                {
                                    "range": f"{chr(64 + status_col)}{i}",
                                    "values": [[status]],
                                }
                            )
                        if fiirumi_post is not None:
                            batch_updates.append(
                                {
                                    "range": f"{chr(64 + fiirumi_col)}{i}",
                                    "values": [[fiirumi_post]],
                                }
                            )
                        processed_count += 1
                        row_found = True
                        break

                if not row_found:
                    logger.warning(
                        "Application not found for queued status update: role %s, user %s",
                        role_id,
                        telegram_id,
                    )

            # Perform batch update if there are any updates
            if batch_updates:
                self.applications_sheet.batch_update(batch_updates)

            logger.info(
                "Flushed %d status updates from queue to sheets", processed_count
            )
            return True

        except Exception as e:
            logger.error("Error flushing status update queue: %s", e)
            # Re-queue the updates if they failed to flush
            for update_data in updates_to_process:
                self.status_update_queue.append(update_data)
            return False

    def flush_channel_queue(self) -> bool:
        """Flush all queued channel operations to Google Sheets in batch operations."""
        channels_to_add = []
        channels_to_remove = []

        try:
            # Process channel additions
            if self.channel_add_queue:
                channels_to_add = list(self.channel_add_queue)
                self.channel_add_queue.clear()

                # Prepare batch data for additions
                current_row = len(self.channels_sheet.col_values(1)) + 1
                batch_data = []

                for chat_id in channels_to_add:
                    batch_data.append([chat_id, datetime.now().isoformat()])

                if batch_data:
                    range_end = current_row + len(batch_data) - 1
                    self.channels_sheet.update(
                        f"A{current_row}:B{range_end}", batch_data
                    )
                    logger.info("Added %d channels in batch", len(batch_data))

            # Process channel removals
            if self.channel_remove_queue:
                channels_to_remove = list(self.channel_remove_queue)
                self.channel_remove_queue.clear()

                # Get current sheet data
                all_data = self.channels_sheet.get_all_values()

                # Find rows to delete (collect indices in reverse order)
                rows_to_delete = []
                for i, row in enumerate(all_data[1:], start=2):  # Start from row 2
                    if len(row) > 0 and int(row[0]) in channels_to_remove:
                        rows_to_delete.append(i)

                # Delete rows in reverse order to maintain correct indices
                for row_index in reversed(rows_to_delete):
                    self.channels_sheet.delete_rows(row_index)

                logger.info("Removed %d channels in batch", len(rows_to_delete))

            # Invalidate cache after successful operations
            if channels_to_add or channels_to_remove:
                _channels_cache.clear()
                logger.debug("Invalidated channels cache after modifications")

            return True

        except Exception as e:
            logger.error("Error flushing channel queue: %s", e)
            # Re-queue the operations if they failed to flush
            for chat_id in channels_to_add:
                self.channel_add_queue.append(chat_id)
            for chat_id in channels_to_remove:
                self.channel_remove_queue.append(chat_id)
            return False

    def get_election_data(self, invalidate_cache: bool = False) -> List[DivisionData]:
        """Get election data structured for display/export."""
        try:
            if invalidate_cache:
                _roles_cache.clear()
                _applications_cache.clear()
                logger.debug("Caches invalidated")

            # Get all roles and applications
            roles = self.get_all_roles()
            all_applications = self.get_all_applications()

            # Group by division using arrays
            divisions_dict: Dict[str, DivisionData] = {}

            for role in roles:
                division_fi = role.get("Division_FI")
                division_en = role.get("Division_EN")

                if division_fi not in divisions_dict:
                    divisions_dict[division_fi] = DivisionData(
                        division=division_fi,
                        division_en=division_en,
                        roles={},
                    )

                # Get approved/elected applications for this role
                applicants = [
                    app
                    for app in all_applications
                    if app.get("Role_ID") == role.get("ID")
                    and app.get("Status", "") in ("APPROVED", "ELECTED")
                ]

                role_data = role.copy()
                role_data["applicants"] = applicants
                divisions_dict[division_fi].get("roles", []).append(role_data)

            # Convert to array of divisions
            return list(divisions_dict.values())

        except Exception as e:
            logger.error("Error getting election data: %s", e)
            return []

    # Channel management methods
    @cached(cache=_channels_cache)
    def get_all_channels(self) -> List[ChannelRow]:
        """Get all registered channels."""
        try:
            all_data = self.channels_sheet.get_all_records()
            return [
                ChannelRow(Channel_ID=int(record.get("Chat_ID"))) for record in all_data
            ]
        except Exception as e:
            logger.error("Error getting channels: %s", e)
            return []

    def add_channel(self, chat_id: int) -> bool:
        """Queue a channel to be added."""
        try:
            # Check if already queued for addition
            if any(queued_id == chat_id for queued_id in self.channel_add_queue):
                logger.info("Channel %s already queued for addition", chat_id)
                return True

            # If queued for removal, remove from remove queue instead of adding to add queue
            try:
                self.channel_remove_queue.remove(chat_id)
                logger.info(
                    "Removed channel %s from remove queue (cancelled removal)", chat_id
                )
                return True
            except ValueError:
                pass  # Not in remove queue, continue with normal add logic

            # Check if channel already exists in current data
            existing_channels = self.get_all_channels()
            if any(
                channel.get("Channel_ID") == chat_id for channel in existing_channels
            ):
                logger.info("Channel %s already exists", chat_id)
                return True

            # Queue for addition
            self.channel_add_queue.append(chat_id)
            logger.info("Queued channel %s for addition", chat_id)
            return True

        except Exception as e:
            logger.error("Error queueing channel addition: %s", e)
            return False

    def remove_channel(self, chat_id: int) -> bool:
        """Queue a channel to be removed."""
        try:
            # Check if already queued for removal
            if any(queued_id == chat_id for queued_id in self.channel_remove_queue):
                logger.info("Channel %s already queued for removal", chat_id)
                return True

            # If queued for addition, remove from add queue instead of adding to remove queue
            try:
                self.channel_add_queue.remove(chat_id)
                logger.info(
                    "Removed channel %s from add queue (cancelled addition)", chat_id
                )
                return True
            except ValueError:
                pass  # Not in add queue, continue with normal remove logic

            # Check if channel exists in current data
            existing_channels = self.get_all_channels()
            if not any(
                channel.get("Channel_ID") == chat_id for channel in existing_channels
            ):
                logger.warning("Channel %s not found in current data", chat_id)
                return False

            # Queue for removal
            self.channel_remove_queue.append(chat_id)
            logger.info("Queued channel %s for removal", chat_id)
            return True

        except Exception as e:
            logger.error("Error queueing channel removal: %s", e)
            return False

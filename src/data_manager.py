"""Data management for vaalilakana, channels, and posts."""

import json
import logging
from typing import Dict, List, Any

from createvaalilakana import create_vaalilakana

logger = logging.getLogger("vaalilakanabot")


class DataManager:
    """Manages all data operations for the bot."""

    def __init__(self):
        self.vaalilakana = {}
        self.channels = []
        self.fiirumi_posts = {}
        self.question_posts = {}
        self.positions = []
        self.divisions = []
        self.pending_applications = {}

        self._load_all_data()

    def _load_all_data(self):
        """Load all data files."""
        self._load_vaalilakana()
        self._load_channels()
        self._load_fiirumi_posts()
        self._load_question_posts()
        self._load_pending_applications()

    def _load_vaalilakana(self):
        """Load vaalilakana data."""
        try:
            with open("data/vaalilakana.json", "r") as f:
                data = f.read()
                self.vaalilakana = json.loads(data)
                self.positions = [
                    {"fi": role["title"], "en": role["title_en"]}
                    for division in self.vaalilakana.values()
                    for role in division["roles"].values()
                ]
                self.divisions = [
                    {"fi": division["division"], "en": division["division_en"]}
                    for division in self.vaalilakana.values()
                ]
        except FileNotFoundError:
            self.vaalilakana = create_vaalilakana()
            self.positions = [
                {"fi": role["title"], "en": role["title_en"]}
                for division in self.vaalilakana.values()
                for role in division["roles"].values()
            ]
            self.divisions = [
                {"fi": division["division"], "en": division["division_en"]}
                for division in self.vaalilakana.values()
            ]

        logger.info("Loaded vaalilakana: %s", self.vaalilakana)

    def _load_channels(self):
        """Load channels data."""
        try:
            with open("data/channels.json", "r") as f:
                data = f.read()
                self.channels = json.loads(data)
        except FileNotFoundError:
            self.channels = []

        logger.info("Loaded channels: %s", self.channels)

    def _load_fiirumi_posts(self):
        """Load fiirumi posts data."""
        try:
            with open("data/fiirumi_posts.json", "r") as f:
                data = f.read()
                self.fiirumi_posts = json.loads(data)
        except FileNotFoundError:
            self.fiirumi_posts = {}

        logger.info("Loaded fiirumi posts: %s", self.fiirumi_posts)

    def _load_question_posts(self):
        """Load question posts data."""
        try:
            with open("data/question_posts.json", "r") as f:
                data = f.read()
                self.question_posts = json.loads(data)
        except FileNotFoundError:
            self.question_posts = {}

        logger.info("Loaded question posts: %s", self.question_posts)

    def _load_pending_applications(self):
        """Load pending applications data."""
        try:
            with open("data/pending_applications.json", "r") as f:
                data = f.read()
                self.pending_applications = json.loads(data)
        except FileNotFoundError:
            self.pending_applications = {}

        logger.info("Loaded pending applications: %s", self.pending_applications)

    def save_data(self, filename: str, content: Any):
        """Save data to a file."""
        with open(filename, "w+") as fp:
            fp.write(json.dumps(content))

    def find_division_for_position(self, position: str) -> str:
        """Find the division for a given position."""
        for division in self.vaalilakana.values():
            if position in division["roles"]:
                return division["division"]

        logger.warning("Position %s not found in vaalilakana", position)
        return None

    def get_divisions(self, is_finnish: bool = True) -> tuple:
        """Get divisions with localization."""
        localized_divisions = [
            division["fi"] if is_finnish else division["en"]
            for division in self.divisions
        ]
        callback_data = [division["fi"] for division in self.divisions]
        return localized_divisions, callback_data

    def get_positions(self, division: str, is_finnish: bool = True) -> tuple:
        """Get positions for a division with deadline filtering."""
        from datetime import datetime

        current_date = datetime.now()
        filtered_roles = []

        for role in self.vaalilakana[division]["roles"].values():
            # Check if there's a deadline and if it has passed
            if role.get("application_dl"):
                try:
                    # Parse date in dd.mm format and assume current year
                    day, month = role["application_dl"].split(".")
                    deadline = datetime(current_date.year, int(month), int(day))

                    if current_date.date() > deadline.date():
                        continue  # Skip this position if deadline has passed
                except (ValueError, AttributeError):
                    # If date parsing fails, include the position (assume no deadline)
                    pass

            filtered_roles.append(role)

        localized_positions = [
            role["title"] if is_finnish else role["title_en"] for role in filtered_roles
        ]
        callback_data = [role["title"] for role in filtered_roles]

        return localized_positions, callback_data

    def add_channel(self, chat_id: int):
        """Add a new channel."""
        if chat_id not in self.channels:
            self.channels.append(chat_id)
            self.save_data("data/channels.json", self.channels)
            logger.info(f"New channel added {chat_id}")

    def remove_channel(self, chat_id: int):
        """Remove a channel."""
        if chat_id in self.channels:
            self.channels.remove(chat_id)
            self.save_data("data/channels.json", self.channels)

    def add_fiirumi_post(self, post_id: str, post_data: Dict):
        """Add a new fiirumi post."""
        self.fiirumi_posts[post_id] = post_data
        self.save_data("data/fiirumi_posts.json", self.fiirumi_posts)

    def add_question_post(self, post_id: str, post_data: Dict):
        """Add a new question post."""
        self.question_posts[post_id] = post_data
        self.save_data("data/question_posts.json", self.question_posts)

    def update_question_posts_count(self, post_id: str, posts_count: int):
        """Update the posts count for a question."""
        if post_id in self.question_posts:
            self.question_posts[post_id]["posts_count"] = posts_count
            self.save_data("data/question_posts.json", self.question_posts)

    def add_applicant(self, division: str, position: str, applicant: Dict):
        """Add a new applicant to a position."""
        self.vaalilakana[division]["roles"][position]["applicants"].append(applicant)
        self.save_data("data/vaalilakana.json", self.vaalilakana)

    def remove_applicant(self, division: str, position: str, applicant_name: str):
        """Remove an applicant from a position."""
        applicants = self.vaalilakana[division]["roles"][position]["applicants"]
        for applicant in applicants:
            if applicant["name"] == applicant_name:
                applicants.remove(applicant)
                break
        self.save_data("data/vaalilakana.json", self.vaalilakana)

    def set_applicant_fiirumi(
        self, division: str, position: str, applicant_name: str, fiirumi_link: str
    ):
        """Set the fiirumi link for an applicant."""
        applicants = self.vaalilakana[division]["roles"][position]["applicants"]
        for applicant in applicants:
            if applicant["name"] == applicant_name:
                applicant["fiirumi"] = fiirumi_link
                break
        self.save_data("data/vaalilakana.json", self.vaalilakana)

    def set_applicant_selected(self, division: str, position: str, applicant_name: str):
        """Mark an applicant as selected."""
        applicants = self.vaalilakana[division]["roles"][position]["applicants"]
        for applicant in applicants:
            if applicant["name"] == applicant_name:
                applicant["valittu"] = True
                break
        self.save_data("data/vaalilakana.json", self.vaalilakana)

    def get_applicants_for_position(self, position: str) -> List[Dict]:
        """Get all applicants for a position."""
        division = self.find_division_for_position(position)
        if division:
            return self.vaalilakana[division]["roles"][position]["applicants"]
        return []

    def check_applicant_exists(self, position: str, user_id: int) -> bool:
        """Check if a user has already applied to a position."""
        division = self.find_division_for_position(position)
        if division:
            applicants = self.vaalilakana[division]["roles"][position]["applicants"]
            return any(applicant["user_id"] == user_id for applicant in applicants)
        return False

    def check_pending_application_exists(self, position: str, user_id: int) -> bool:
        """Check if a user has a pending application for a position."""
        for application in self.pending_applications.values():
            if (
                application["position"] == position
                and application["applicant"]["user_id"] == user_id
            ):
                return True
        return False

    def add_pending_application(self, application_id: str, application_data: Dict):
        """Add a new pending application awaiting admin approval."""
        self.pending_applications[application_id] = application_data
        self.save_data("data/pending_applications.json", self.pending_applications)

    def remove_pending_application(self, application_id: str):
        """Remove a pending application."""
        if application_id in self.pending_applications:
            del self.pending_applications[application_id]
            self.save_data("data/pending_applications.json", self.pending_applications)

    def get_pending_application(self, application_id: str) -> Dict:
        """Get a pending application by ID."""
        return self.pending_applications.get(application_id, {})

    def approve_application(self, application_id: str) -> Dict:
        """Approve a pending application and add it to vaalilakana."""
        if application_id not in self.pending_applications:
            return None

        application = self.pending_applications[application_id]
        division = application["division"]
        position = application["position"]
        applicant = application["applicant"]

        # Add admin_approved field
        applicant["admin_approved"] = True

        # Add to vaalilakana
        self.add_applicant(division, position, applicant)

        # Remove from pending
        self.remove_pending_application(application_id)

        return application

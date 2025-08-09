"""Types for the application process."""

from typing import TypedDict, List, Optional, Dict, Literal


RoleType = Literal["BOARD", "ELECTED", "NON-ELECTED", "AUDITOR"]
ApplicationStatus = Literal["APPROVED", "DENIED", "REMOVED", "ELECTED", ""]


class ElectionStructureRow(TypedDict):
    """Row in the election structure sheet."""

    ID: str
    Division_FI: str
    Division_EN: str
    Role_FI: str
    Role_EN: str
    Type: RoleType
    Amount: Optional[str]
    Deadline: Optional[str]


class ApplicationRow(TypedDict):
    """Row in the applications sheet."""

    Role_ID: str
    Telegram_ID: int
    Name: str
    Email: str
    Telegram: str
    Fiirumi_Post: str
    Status: ApplicationStatus
    Language: str


class DivisionDict(TypedDict):
    """Division dictionary."""

    fi: str
    en: str


class ApplicantDict(TypedDict):
    """Applicant dictionary."""

    user_id: int
    name: str
    email: str
    telegram: str
    fiirumi: str
    status: ApplicationStatus


class RoleData(TypedDict):
    """Role data dictionary."""

    title: str
    title_en: str
    amount: Optional[str]
    application_dl: Optional[str]
    type: RoleType
    applicants: List[ApplicantDict]
    # Optional denormalized division information for flattened views
    division: Optional[str]
    division_en: Optional[str]


class DivisionData(TypedDict):
    """Division data dictionary."""

    division: str
    division_en: str
    roles: Dict[str, RoleData]


class PendingApplication(TypedDict):
    """Pending application dictionary."""

    Role_ID: str
    Telegram_ID: int
    Name: str
    Email: str
    Telegram: str
    Fiirumi_Post: str
    Status: str


class ChannelRow(TypedDict):
    """Channel row dictionary."""

    Channel_ID: int


class ApplicationData(TypedDict):
    """Application data dictionary."""

    position: str
    language: str
    applicant: ApplicantDict

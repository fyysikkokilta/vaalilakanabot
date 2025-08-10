"""Types for the application process."""

from typing import TypedDict, List, Optional, Literal


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


class RoleData(TypedDict):
    """Role data dictionary."""

    title: str
    title_en: str
    amount: Optional[str]
    application_dl: Optional[str]
    type: RoleType
    applicants: List[ApplicationRow]
    # Optional denormalized division information for flattened views
    division: Optional[str]
    division_en: Optional[str]


class DivisionData(TypedDict):
    """Division data dictionary."""

    division: str
    division_en: str
    roles: List[RoleData]


class ChannelRow(TypedDict):
    """Channel row dictionary."""

    Channel_ID: int

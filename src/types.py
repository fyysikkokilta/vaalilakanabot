"""Types for the application process."""

from typing import TypedDict, List, Optional, Literal


RoleType = Literal["BOARD", "ELECTED", "NON-ELECTED", "AUDITOR"]
ApplicationStatus = Literal["APPROVED", "DENIED", "REMOVED", "ELECTED", "PENDING"]


class UserRow(TypedDict):
    """Row in the users sheet."""

    Telegram_ID: int
    Name: str
    Email: str
    Telegram: str  # @username
    Show_On_Website_Consent: bool  # Consent to show person on the website's official page
    Updated_At: str  # ISO timestamp of last update


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
    """Row in the applications sheet. User display info (name, email, telegram) comes from Users sheet by Telegram_ID."""

    Timestamp: str
    Role_ID: str
    Telegram_ID: int
    Fiirumi_Post: str
    Status: ApplicationStatus
    Language: str
    Group_ID: Optional[str]  # UUID linking group applications together


class DivisionDict(TypedDict):
    """Division dictionary."""

    Division_FI: str
    Division_EN: str


# For election sheet data
class RoleData(TypedDict):
    """Role data dictionary."""

    ID: str
    Role_FI: str
    Role_EN: str
    Amount: Optional[str]
    Deadline: Optional[str]
    Type: RoleType
    Applicants: List[ApplicationRow]
    Division_FI: Optional[str]
    Division_EN: Optional[str]


class DivisionData(TypedDict):
    """Division data dictionary."""

    Division_FI: str
    Division_EN: str
    Roles: List[RoleData]


class ChannelRow(TypedDict):
    """Channel row dictionary."""

    Channel_ID: int

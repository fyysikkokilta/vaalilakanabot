"""Announcement and notification functionality."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple

import requests
from telegram.ext import ContextTypes

from .utils import check_title_matches_applicant_and_role, create_fiirumi_link
from .sheets_data_manager import DataManager
from .types import ApplicationWithDisplay, ElectionStructureRow, RoleData
from .config import get_topic_list_url, get_question_list_url
from .fiirumi_area_generator import get_discourse_headers

logger = logging.getLogger("vaalilakanabot")


def get_current_minute_start() -> datetime:
    """Get the current time rounded down to the start of the ongoing minute."""
    now = datetime.now(timezone.utc)
    return now.replace(second=0, microsecond=0)


def get_fiirumi_data(url: str) -> Any:
    """Get Fiirumi data from the given URL."""
    # Using authenticated headers bypasses the anonymous cache so we see new posts.
    response = requests.get(url, headers=get_discourse_headers(), timeout=10)
    return response.json()


def is_recent_timestamp(
    timestamp_str: str, current_time: datetime, minutes: int = 1
) -> bool:
    """Check if a timestamp is within the last N minutes."""
    try:
        # Parse the timestamp (assume ISO format from Discourse)
        post_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        time_diff = current_time - post_time

        return time_diff <= timedelta(minutes=minutes)
    except Exception as e:
        logger.warning("Failed to parse timestamp %s: %s", timestamp_str, e)
        return False


async def announce_to_channels(
    message: str, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Announce a message to all registered channels concurrently."""
    channels = list(data_manager.channels)
    if not channels:
        return

    async def _send(channel_id: int) -> Tuple[int, Any]:
        try:
            await context.bot.send_message(channel_id, message, parse_mode="HTML")
            return channel_id, None
        except Exception as e:  # pylint: disable=broad-except
            return channel_id, e

    results = await asyncio.gather(
        *(_send(c.get("Channel_ID")) for c in channels)
    )
    for channel_id, error in results:
        if error is not None:
            logger.error(error)
            data_manager.remove_channel(channel_id)


# (role_data, applicant, role_row) — built once per parse_fiirumi_posts run
ApplicantIndex = List[
    Tuple[RoleData, ApplicationWithDisplay, ElectionStructureRow]
]


def _build_applicant_index(data_manager: DataManager) -> ApplicantIndex:
    """Build a flat list of matchable applicants, with the role row preloaded."""
    index: ApplicantIndex = []
    for role_data in data_manager.vaalilakana:
        role_row = data_manager.get_role_by_id(role_data.get("ID", ""))
        if role_row is None:
            continue
        for applicant in role_data.get("Applicants", []):
            index.append((role_data, applicant, role_row))
    return index


def _link_topic_to_applicants(
    topic: Dict[str, Any],
    data_manager: DataManager,
    applicant_index: ApplicantIndex,
) -> Tuple[str, List[str]]:
    """Link a topic to matching applicants; return (fiirumi_link, linked_applicants)."""
    t_id = topic["id"]
    title = topic["title"]
    fiirumi_link = create_fiirumi_link(t_id)
    linked: List[str] = []
    for role_data, applicant, role_row in applicant_index:
        applicant_name = str(applicant.get("Name") or "")
        role_fi = str(role_data.get("Role_FI") or "")
        role_en = str(role_data.get("Role_EN") or "")
        if check_title_matches_applicant_and_role(
            title, applicant_name, role_fi, role_en
        ):
            data_manager.set_applicant_fiirumi(
                role_row, applicant_name, fiirumi_link
            )
            linked.append(f"{role_en}: {applicant_name}")
    return fiirumi_link, linked


async def parse_fiirumi_posts(
    context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Parse and announce new fiirumi posts and questions based on timestamps."""
    topic_url = get_topic_list_url()
    question_url = get_question_list_url()
    try:
        current_time = get_current_minute_start()
        topic_json, question_json = await asyncio.gather(
            asyncio.to_thread(get_fiirumi_data, topic_url),
            asyncio.to_thread(get_fiirumi_data, question_url),
        )
        topic_list = topic_json["topic_list"]["topics"]
        question_list = question_json["topic_list"]["topics"]
        logger.debug(
            "Retrieved %d topics and %d questions", len(topic_list), len(question_list)
        )
    except KeyError as e:
        logger.error(
            "The topic and question lists cannot be found. Check URLs. Got error %s", e
        )
        return
    except Exception as e:
        logger.error("Error fetching Fiirumi data: %s", e)
        return

    applicant_index: ApplicantIndex = []
    index_built = False

    for topic in topic_list:
        created_at = topic.get("created_at")
        if not (created_at and is_recent_timestamp(created_at, current_time)):
            continue
        title = topic["title"]
        logger.info("Found new post: %s (ID: %s)", title, topic["id"])
        if not index_built:
            applicant_index = _build_applicant_index(data_manager)
            index_built = True
        fiirumi_link, linked = _link_topic_to_applicants(
            topic, data_manager, applicant_index
        )
        if linked:
            logger.info("Auto-linked post '%s' to applicants: %s", title, linked)
        await announce_to_channels(
            f"<b>Uusi postaus Fiirumilla!</b>\n"
            f"<b>New post on Fiirumi!</b>\n"
            f'<a href="{fiirumi_link}">{title}</a>',
            context,
            data_manager,
        )

    for question in question_list:
        created_at = question.get("created_at")
        if not (created_at and is_recent_timestamp(created_at, current_time)):
            continue
        title = question["title"]
        t_id = question["id"]
        logger.info("Found new question: %s (ID: %s)", title, t_id)
        await announce_to_channels(
            f"<b>Uusi kysymys Fiirumilla!</b>\n"
            f"<b>New question on Fiirumi!</b>\n"
            f'<a href="{create_fiirumi_link(t_id)}">{title}</a>',
            context,
            data_manager,
        )


async def announce_new_responses(
    context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Announce new responses to questions based on timestamps, runs every hour."""
    question_url = get_question_list_url()
    try:
        current_time = get_current_minute_start()
        question_json = await asyncio.to_thread(get_fiirumi_data, question_url)
        question_list = question_json["topic_list"]["topics"]

        new_responses: List[Dict[str, Any]] = []

        for question in question_list:
            t_id = question["id"]
            title = question["title"]
            posts_count = question["posts_count"]
            last_posted_at = question.get("last_posted_at")

            # Check if there was activity in the last hour (since this runs hourly)
            # and it's not a brand new question (posts_count > 1 means responses exist)
            if (
                last_posted_at
                and is_recent_timestamp(last_posted_at, current_time, minutes=60)
                and posts_count > 1
            ):  # More than just the original question

                new_responses.append(
                    {
                        "title": title,
                        "t_id": t_id,
                        "posts_count": posts_count,
                        "last_poster": question.get("last_poster_username", "Unknown"),
                    }
                )
                logger.info(
                    "Found recent activity in question: %s (ID: %s)", title, t_id
                )

        # If there are new responses, create a single grouped message
        if new_responses:
            message = "<b>Uusia vastauksia Fiirumilla!</b>\n"
            message += "<b>New responses on Fiirumi!</b>\n\n"

            for response in new_responses:
                message += f"• <a href=\"{create_fiirumi_link(response['t_id'])}/{response['posts_count']}\">{response['title']}</a>\n"
                message += f"  Viimeisin vastaaja / Latest poster: {response['last_poster']}\n\n"

            await announce_to_channels(message, context, data_manager)
            logger.info(
                "Announced %d questions with recent responses", len(new_responses)
            )

    except Exception as e:
        logger.error("Error in announce_new_responses: %s", e)

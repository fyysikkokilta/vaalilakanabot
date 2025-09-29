"""Announcement and notification functionality."""

import time
import logging
from datetime import datetime, timezone, timedelta

import requests
from telegram.ext import ContextTypes

from .utils import check_title_matches_applicant_and_role, create_fiirumi_link
from .sheets_data_manager import DataManager
from .config import TOPIC_LIST_URL, QUESTION_LIST_URL

logger = logging.getLogger("vaalilakanabot")


def is_recent_timestamp(timestamp_str: str, minutes: int = 1) -> bool:
    """Check if a timestamp is within the last N minutes."""
    try:
        # Parse the timestamp (assume ISO format from Discourse)
        post_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - post_time

        return time_diff <= timedelta(minutes=minutes)
    except Exception as e:
        logger.warning("Failed to parse timestamp %s: %s", timestamp_str, e)
        return False


async def announce_to_channels(
    message: str, context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Announce a message to all registered channels."""
    for channel in data_manager.channels:
        try:
            await context.bot.send_message(
                channel.get("Channel_ID"), message, parse_mode="HTML"
            )
            time.sleep(0.5)
        except Exception as e:
            logger.error(e)
            data_manager.remove_channel(channel.get("Channel_ID"))
            continue


async def parse_fiirumi_posts(
    context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Parse and announce new fiirumi posts and questions based on timestamps."""

    try:
        page_fiirumi = requests.get(TOPIC_LIST_URL, timeout=10)
        page_question = requests.get(QUESTION_LIST_URL, timeout=10)
        topic_list_raw = page_fiirumi.json()
        question_list_raw = page_question.json()
        topic_list = topic_list_raw["topic_list"]["topics"]
        question_list = question_list_raw["topic_list"]["topics"]

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

    # Check for new posts (created in the last minute)
    for topic in topic_list:
        t_id = topic["id"]
        title = topic["title"]
        created_at = topic.get("created_at")

        if created_at and is_recent_timestamp(created_at):
            logger.info("Found new post: %s (ID: %s)", title, t_id)

            # Try to automatically link this post to an applicant
            fiirumi_link = create_fiirumi_link(t_id)
            linked_applicants = []

            # Check all elected roles for updates using flattened structure
            for role_data in data_manager.vaalilakana:
                for applicant in role_data.get("Applicants", []):
                    if check_title_matches_applicant_and_role(
                        title,
                        applicant.get("Name"),
                        role_data.get("Role_FI"),
                        role_data.get("Role_EN"),
                    ):
                        # Link the post to this applicant (queue the status update)
                        data_manager.set_applicant_fiirumi(
                            role_data,
                            applicant.get("Name"),
                            fiirumi_link,
                        )
                        linked_applicants.append(
                            f"{role_data.get('Role_EN')}: {applicant.get('Name')}"
                        )

            # Log successful auto-links
            if linked_applicants:
                logger.info(
                    "Auto-linked post '%s' to applicants: %s", title, linked_applicants
                )

            await announce_to_channels(
                f"<b>Uusi postaus Fiirumilla!</b>\n"
                f"<b>New post on Fiirumi!</b>\n"
                f"<a href=\"{fiirumi_link}\">{title}</a>",
                context,
                data_manager,
            )

    # Check for new questions (created in the last minute)
    for question in question_list:
        t_id = question["id"]
        title = question["title"]
        created_at = question.get("created_at")

        if created_at and is_recent_timestamp(created_at):
            logger.info("Found new question: %s (ID: %s)", title, t_id)

            await announce_to_channels(
                f"<b>Uusi kysymys Fiirumilla!</b>\n"
                f"<b>New question on Fiirumi!</b>\n"
                f"<a href=\"{create_fiirumi_link(t_id)}\">{title}</a>",
                context,
                data_manager,
            )


async def announce_new_responses(
    context: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Announce new responses to questions based on timestamps, runs every hour."""

    try:
        page_question = requests.get(QUESTION_LIST_URL, timeout=10)
        question_list_raw = page_question.json()
        question_list = question_list_raw["topic_list"]["topics"]

        new_responses = []

        for question in question_list:
            t_id = question["id"]
            title = question["title"]
            posts_count = question["posts_count"]
            last_posted_at = question.get("last_posted_at")

            # Check if there was activity in the last hour (since this runs hourly)
            # and it's not a brand new question (posts_count > 1 means responses exist)
            if (
                last_posted_at
                and is_recent_timestamp(last_posted_at, minutes=60)
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

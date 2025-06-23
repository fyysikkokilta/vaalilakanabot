"""Announcement and notification functionality."""

import time
import logging

from telegram.ext import ContextTypes

from .utils import create_fiirumi_link, check_title_matches_applicant_and_role

logger = logging.getLogger("vaalilakanabot")


async def announce_to_channels(
    message: str, context: ContextTypes.DEFAULT_TYPE, data_manager
):
    """Announce a message to all registered channels."""
    for cid in data_manager.channels:
        try:
            await context.bot.send_message(cid, message, parse_mode="HTML")
            time.sleep(0.5)
        except Exception as e:
            logger.error(e)
            data_manager.remove_channel(cid)
            continue


async def parse_fiirumi_posts(context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Parse and announce new fiirumi posts and questions."""
    import requests
    from .config import TOPIC_LIST_URL, QUESTION_LIST_URL, BOARD, ELECTED_OFFICIALS

    try:
        page_fiirumi = requests.get(TOPIC_LIST_URL, timeout=10)
        logger.debug(page_fiirumi)
        page_question = requests.get(QUESTION_LIST_URL, timeout=10)
        topic_list_raw = page_fiirumi.json()
        logger.debug(str(topic_list_raw))
        question_list_raw = page_question.json()
        topic_list = topic_list_raw["topic_list"]["topics"]
        question_list = question_list_raw["topic_list"]["topics"]

        logger.debug(topic_list)
    except KeyError as e:
        logger.error(
            "The topic and question lists cannot be found. Check URLs. Got error %s", e
        )
        return
    except Exception as e:
        logger.error(e)
        return

    for topic in topic_list:
        t_id = topic["id"]
        title = topic["title"]
        slug = topic["slug"]
        if str(t_id) not in data_manager.fiirumi_posts:
            new_post = {
                "id": t_id,
                "title": title,
                "slug": slug,
            }
            data_manager.add_fiirumi_post(str(t_id), new_post)

            # Try to automatically link this post to an applicant
            fiirumi_link = create_fiirumi_link(slug, t_id)
            linked_applicants = []

            # Check all elected roles (BOARD + ELECTED_OFFICIALS)
            for position in BOARD + ELECTED_OFFICIALS:
                division = data_manager.find_division_for_position(position)
                if division:
                    role_data = data_manager.vaalilakana[division]["roles"][position]
                    for applicant in role_data["applicants"]:
                        if check_title_matches_applicant_and_role(
                            title,
                            applicant["name"],
                            role_data["title"],
                            role_data["title_en"],
                        ):
                            # Link the post to this applicant
                            data_manager.set_applicant_fiirumi(
                                division, position, applicant["name"], fiirumi_link
                            )
                            linked_applicants.append(f"{position}: {applicant['name']}")

            # Log successful auto-links
            if linked_applicants:
                logger.info(
                    f"Auto-linked post '{title}' to applicants: {linked_applicants}"
                )

            await announce_to_channels(
                f"<b>Uusi postaus Vaalipeli-palstalla!</b>\n{title}\n{fiirumi_link}",
                context,
                data_manager,
            )

    for question in question_list:
        t_id = question["id"]
        title = question["title"]
        slug = question["slug"]
        posts_count = question["posts_count"]
        if str(t_id) not in data_manager.question_posts:
            new_question = {
                "id": t_id,
                "title": title,
                "slug": slug,
                "posts_count": posts_count,
            }
            data_manager.add_question_post(str(t_id), new_question)
            await announce_to_channels(
                f"<b>Uusi kysymys Fiirumilla!</b>\n{title}\n{create_fiirumi_link(slug, t_id)}",
                context,
                data_manager,
            )
        else:
            # Update the posts count but don't announce individual responses
            # They will be handled by the separate response announcement function
            data_manager.update_question_posts_count(str(t_id), posts_count)


async def announce_new_responses(context: ContextTypes.DEFAULT_TYPE, data_manager):
    """Announce new responses to questions in a grouped message, runs every hour."""
    import requests
    from .config import QUESTION_LIST_URL

    try:
        page_question = requests.get(QUESTION_LIST_URL, timeout=10)
        question_list_raw = page_question.json()
        question_list = question_list_raw["topic_list"]["topics"]

        new_responses = []

        for question in question_list:
            t_id = question["id"]
            title = question["title"]
            slug = question["slug"]
            posts_count = question["posts_count"]

            if str(t_id) in data_manager.question_posts:
                stored_count = data_manager.question_posts[str(t_id)]["posts_count"]
                if posts_count > stored_count:
                    # There are new responses
                    new_responses.append(
                        {
                            "title": title,
                            "slug": slug,
                            "t_id": t_id,
                            "posts_count": posts_count,
                            "last_poster": question.get(
                                "last_poster_username", "Unknown"
                            ),
                        }
                    )

        # If there are new responses, create a single grouped message
        if new_responses:
            message = "<b>Uusia vastauksia Fiirumilla!</b>\n\n"

            for response in new_responses:
                message += f"• <b>{response['title']}</b>\n"
                message += f"  {create_fiirumi_link(response['slug'], response['t_id'])}/{response['posts_count']}\n"
                message += f"  Viimeisin vastaaja: {response['last_poster']}\n\n"

            await announce_to_channels(message, context, data_manager)

    except Exception as e:
        logger.error(f"Error in announce_new_responses: {e}")

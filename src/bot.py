"""Main bot module."""

import datetime
import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from .config import (
    TOKEN,
    SELECTING_DIVISION,
    SELECTING_ROLE,
    GIVING_NAME,
    GIVING_EMAIL,
    CONFIRMING_APPLICATION,
)
from .sheets_data_manager import DataManager
from .admin_commands import (
    remove_applicant,
    add_fiirumi_to_applicant,
    unassociate_fiirumi,
    add_elected_tag,
    export_officials_website,
    admin_help,
)
from .user_commands import (
    register_channel,
    unregister_channel,
    show_election_sheet,
    show_election_sheet_en,
    applications_en,
    applications,
    jauhis,
    jauh,
    jauho,
    lauh,
    mauh,
    help_command,
    apua_command,
)
from .application_handlers import (
    hae,
    apply,
    select_division,
    select_role,
    enter_name,
    enter_email,
    confirm_application,
    cancel,
    handle_multiple_application_choice,
    handle_back_button,
)
from .announcements import parse_fiirumi_posts, announce_new_responses
from .admin_approval import handle_admin_approval
from .sheet_updater import update_election_sheet

logger = logging.getLogger("vaalilakanabot")


def setup_logging():
    """Setup logging configuration."""
    logger.setLevel(logging.INFO)
    fh = logging.StreamHandler(sys.stdout)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log Errors caused by Updates."""
    logger.warning("Update '%s' caused error '%s'", update, context.error)


async def process_application_queue(
    _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
):
    """Flush queued applications, status updates, and channel operations to Google Sheets."""
    try:
        # First flush new applications
        app_success = data_manager.sheets_manager.flush_application_queue()
        if app_success:
            logger.debug("Successfully flushed application queue")
        else:
            logger.warning("Failed to flush application queue")

        # Then flush status updates (after applications exist)
        status_success = data_manager.sheets_manager.flush_status_update_queue()
        if status_success:
            logger.debug("Successfully flushed status update queue")
        else:
            logger.warning("Failed to flush status update queue")

        # Finally flush channel operations
        channel_success = data_manager.sheets_manager.flush_channel_queue()
        if channel_success:
            logger.debug("Successfully flushed channel queue")
        else:
            logger.warning("Failed to flush channel queue")

        # Invalidate caches after all operations
        data_manager.sheets_manager.invalidate_caches()

    except Exception as e:
        logger.error("Error in queue processing job: %s", e)


async def post_init(app: Application, data_manager: DataManager):
    """Post initialization setup."""
    jq = app.job_queue
    if jq is None:
        raise ValueError("JobQueue is None")

    # Schedule jobs
    jq.run_repeating(
        lambda context: parse_fiirumi_posts(context, data_manager),
        interval=60,
        first=datetime.datetime(2025, 8, 10, hour=0),
    )
    jq.run_repeating(
        lambda context: announce_new_responses(context, data_manager),
        interval=3600,
        first=datetime.datetime(2025, 8, 10, hour=0),
    )

    jq.run_repeating(
        lambda context: update_election_sheet(context, data_manager),
        interval=60,
        first=datetime.datetime(2025, 8, 10, hour=0),
    )

    jq.run_repeating(
        lambda context: process_application_queue(context, data_manager),
        interval=60,
        first=datetime.datetime(2025, 8, 10, hour=0, minute=0, second=10),
    )

    # Admin command handlers
    app.add_handler(
        CommandHandler(
            "remove",
            lambda update, context: remove_applicant(update, context, data_manager),
        )
    )
    app.add_handler(
        CommandHandler(
            "add_fiirumi",
            lambda update, _: add_fiirumi_to_applicant(update, data_manager),
        )
    )
    app.add_handler(
        CommandHandler(
            "remove_fiirumi",
            lambda update, _: unassociate_fiirumi(update, data_manager),
        )
    )
    app.add_handler(
        CommandHandler(
            "elected",
            lambda update, context: add_elected_tag(update, context, data_manager),
        )
    )

    # export_data removed; use Google Sheets directly for raw exports
    app.add_handler(
        CommandHandler(
            "export_officials_website",
            lambda update, _: export_officials_website(update, data_manager),
        )
    )
    app.add_handler(CommandHandler("admin_help", admin_help))

    # User command handlers
    app.add_handler(
        CommandHandler(
            "start", lambda update, _: register_channel(update, data_manager)
        )
    )
    app.add_handler(
        CommandHandler(
            "stop", lambda update, _: unregister_channel(update, data_manager)
        )
    )
    app.add_handler(
        CommandHandler(
            "lakana", lambda update, _: show_election_sheet(update, data_manager)
        )
    )
    app.add_handler(
        CommandHandler(
            "sheet", lambda update, _: show_election_sheet_en(update, data_manager)
        )
    )
    app.add_handler(
        CommandHandler(
            "hakemukset",
            lambda update, _: applications(update, data_manager),
            filters.ChatType.PRIVATE,
        )
    )
    app.add_handler(
        CommandHandler(
            "applications",
            lambda update, _: applications_en(update, data_manager),
            filters.ChatType.PRIVATE,
        )
    )
    app.add_handler(CommandHandler("jauhis", jauhis))
    app.add_handler(CommandHandler("jauh", jauh))
    app.add_handler(CommandHandler("jauho", jauho))
    app.add_handler(CommandHandler("lauh", lauh))
    app.add_handler(CommandHandler("mauh", mauh))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("apua", apua_command))

    # Admin approval callback handler
    app.add_handler(
        CallbackQueryHandler(
            lambda update, ctx: handle_admin_approval(update, ctx, data_manager),
            pattern="^(approve_|reject_)",
        )
    )

    application_states = {
        SELECTING_DIVISION: [
            CallbackQueryHandler(
                lambda update, ctx: select_division(update, ctx, data_manager)
            )
        ],
        SELECTING_ROLE: [
            CallbackQueryHandler(
                handle_multiple_application_choice,
                pattern="^(continue_multiple|cancel_multiple)$",
            ),
            CallbackQueryHandler(
                lambda update, ctx: handle_back_button(update, ctx, data_manager),
                pattern="^back$",
            ),
            CallbackQueryHandler(
                lambda update, ctx: select_role(update, ctx, data_manager)
            ),
        ],
        GIVING_NAME: [
            MessageHandler(
                filters.TEXT & (~filters.COMMAND),
                enter_name,
            )
        ],
        GIVING_EMAIL: [
            MessageHandler(
                filters.TEXT & (~filters.COMMAND),
                lambda update, ctx: enter_email(update, ctx, data_manager),
            )
        ],
        CONFIRMING_APPLICATION: [
            CallbackQueryHandler(
                lambda update, ctx: confirm_application(update, ctx, data_manager)
            )
        ],
    }

    # Application conversation handlers
    # Finnish application handler
    hae_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "hae",
                lambda update, ctx: hae(update, ctx, data_manager),
                filters.ChatType.PRIVATE,
            )
        ],
        states=application_states,
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("hae", lambda update, ctx: hae(update, ctx, data_manager)),
        ],
    )

    # English application handler
    apply_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "apply",
                lambda update, ctx: apply(update, ctx, data_manager),
                filters.ChatType.PRIVATE,
            )
        ],
        states=application_states,
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler(
                "apply", lambda update, ctx: apply(update, ctx, data_manager)
            ),
        ],
    )

    app.add_handler(hae_handler)
    app.add_handler(apply_handler)
    app.add_error_handler(error)

    logger.info("Post init done.")


def main():
    """Main function to run the bot."""
    setup_logging()

    # Initialize data manager
    data_manager = DataManager()

    # Create and configure application
    app = Application.builder().token(TOKEN).concurrent_updates(False).build()

    # Set up post initialization
    app.post_init = lambda app: post_init(app, data_manager)

    # Run the bot
    app.run_polling()


if __name__ == "__main__":
    main()

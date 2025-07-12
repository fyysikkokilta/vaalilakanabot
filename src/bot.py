"""Main bot module."""

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
from .data_manager import DataManager
from .admin_commands import (
    remove_applicant,
    add_fiirumi_to_applicant,
    unassociate_fiirumi,
    add_selected_tag,
    edit_or_add_new_role,
    remove_role,
    export_data,
    export_officials_website,
    admin_help,
)
from .user_commands import (
    register_channel,
    show_vaalilakana,
    show_election_sheet,
    jauhis,
    jauh,
    jauho,
    lauh,
    mauh,
    help,
    apua,
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
)
from .announcements import parse_fiirumi_posts, announce_new_responses
from .admin_approval import handle_admin_approval, list_pending_applications

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
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def create_wrapper(func, data_manager):
    """Create a wrapper function that includes the data_manager parameter."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await func(update, context, data_manager)

    return wrapper


async def post_init(app: Application, data_manager: DataManager):
    """Post initialization setup."""
    jq = app.job_queue
    if jq is None:
        raise ValueError("JobQueue is None")

    # Schedule jobs
    jq.run_repeating(
        lambda ctx: parse_fiirumi_posts(ctx, data_manager), interval=60, first=0
    )
    jq.run_repeating(
        lambda ctx: announce_new_responses(ctx, data_manager), interval=3600, first=0
    )

    # Import and schedule the election sheet updater
    from lakanaupdater import update_election_sheet

    jq.run_repeating(update_election_sheet, interval=60, first=0)

    # Admin command handlers
    app.add_handler(
        CommandHandler("remove", create_wrapper(remove_applicant, data_manager))
    )
    app.add_handler(
        CommandHandler(
            "add_fiirumi", create_wrapper(add_fiirumi_to_applicant, data_manager)
        )
    )
    app.add_handler(
        CommandHandler(
            "remove_fiirumi", create_wrapper(unassociate_fiirumi, data_manager)
        )
    )
    app.add_handler(
        CommandHandler("selected", create_wrapper(add_selected_tag, data_manager))
    )
    app.add_handler(
        CommandHandler(
            "edit_or_add_new_role", create_wrapper(edit_or_add_new_role, data_manager)
        )
    )
    app.add_handler(
        CommandHandler("remove_role", create_wrapper(remove_role, data_manager))
    )
    app.add_handler(
        CommandHandler("export_data", create_wrapper(export_data, data_manager))
    )
    app.add_handler(
        CommandHandler(
            "export_officials_website",
            create_wrapper(export_officials_website, data_manager),
        )
    )
    app.add_handler(
        CommandHandler(
            "pending", create_wrapper(list_pending_applications, data_manager)
        )
    )
    app.add_handler(
        CommandHandler("admin_help", create_wrapper(admin_help, data_manager))
    )

    # User command handlers
    app.add_handler(
        CommandHandler("start", create_wrapper(register_channel, data_manager))
    )
    app.add_handler(
        CommandHandler("lakana", create_wrapper(show_vaalilakana, data_manager))
    )
    app.add_handler(
        CommandHandler("sheet", create_wrapper(show_election_sheet, data_manager))
    )
    app.add_handler(CommandHandler("jauhis", create_wrapper(jauhis, data_manager)))
    app.add_handler(CommandHandler("jauh", create_wrapper(jauh, data_manager)))
    app.add_handler(CommandHandler("jauho", create_wrapper(jauho, data_manager)))
    app.add_handler(CommandHandler("lauh", create_wrapper(lauh, data_manager)))
    app.add_handler(CommandHandler("mauh", create_wrapper(mauh, data_manager)))
    app.add_handler(CommandHandler("help", create_wrapper(help, data_manager)))
    app.add_handler(CommandHandler("apua", create_wrapper(apua, data_manager)))

    # Admin approval callback handler
    app.add_handler(
        CallbackQueryHandler(
            create_wrapper(handle_admin_approval, data_manager),
            pattern="^(approve_|reject_)",
        )
    )

    # Application conversation handlers
    # Finnish application handler
    hae_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "hae", create_wrapper(hae, data_manager), filters.ChatType.PRIVATE
            )
        ],
        states={
            SELECTING_DIVISION: [
                CallbackQueryHandler(create_wrapper(select_division, data_manager))
            ],
            SELECTING_ROLE: [
                CallbackQueryHandler(
                    create_wrapper(handle_multiple_application_choice, data_manager),
                    pattern="^(continue_multiple|cancel_multiple)$",
                ),
                CallbackQueryHandler(create_wrapper(select_role, data_manager)),
            ],
            GIVING_NAME: [
                MessageHandler(
                    filters.TEXT & (~filters.COMMAND),
                    create_wrapper(enter_name, data_manager),
                )
            ],
            GIVING_EMAIL: [
                MessageHandler(
                    filters.TEXT & (~filters.COMMAND),
                    create_wrapper(enter_email, data_manager),
                )
            ],
            CONFIRMING_APPLICATION: [
                CallbackQueryHandler(create_wrapper(confirm_application, data_manager))
            ],
        },
        fallbacks=[
            CommandHandler("cancel", create_wrapper(cancel, data_manager)),
            CommandHandler("hae", create_wrapper(hae, data_manager)),
        ],
    )

    # English application handler
    apply_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "apply", create_wrapper(apply, data_manager), filters.ChatType.PRIVATE
            )
        ],
        states={
            SELECTING_DIVISION: [
                CallbackQueryHandler(create_wrapper(select_division, data_manager))
            ],
            SELECTING_ROLE: [
                CallbackQueryHandler(
                    create_wrapper(handle_multiple_application_choice, data_manager),
                    pattern="^(continue_multiple|cancel_multiple)$",
                ),
                CallbackQueryHandler(create_wrapper(select_role, data_manager)),
            ],
            GIVING_NAME: [
                MessageHandler(
                    filters.TEXT & (~filters.COMMAND),
                    create_wrapper(enter_name, data_manager),
                )
            ],
            GIVING_EMAIL: [
                MessageHandler(
                    filters.TEXT & (~filters.COMMAND),
                    create_wrapper(enter_email, data_manager),
                )
            ],
            CONFIRMING_APPLICATION: [
                CallbackQueryHandler(create_wrapper(confirm_application, data_manager))
            ],
        },
        fallbacks=[
            CommandHandler("cancel", create_wrapper(cancel, data_manager)),
            CommandHandler("apply", create_wrapper(apply, data_manager)),
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

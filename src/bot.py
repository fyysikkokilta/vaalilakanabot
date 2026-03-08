"""Main bot module."""

import datetime
import logging
import sys
from typing import Any, Callable, Coroutine, Dict, List, Optional

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
    CONFIRMING_APPLICATION,
    ELECTION_YEAR,
    REGISTER_NAME,
    REGISTER_EMAIL,
    REGISTER_CONSENT,
)
from .sheets_data_manager import DataManager
from .admin_commands import (
    remove_applicant,
    add_fiirumi_to_applicant,
    unassociate_fiirumi,
    add_elected_tag,
    combine_applicants,
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
    STICKER_COMMANDS,
    help_command,
    apua_command,
)
from .utils import send_sticker
from .application_handlers import (
    hae,
    apply,
    select_division,
    select_role,
    confirm_application,
    cancel,
    handle_multiple_application_choice,
    handle_back_button,
)
from .register_handlers import (
    register_start_finnish,
    register_start_english,
    register_name,
    register_email,
    register_consent,
    register_cancel,
)
from .announcements import parse_fiirumi_posts, announce_new_responses
from .admin_approval import handle_admin_approval
from .sheet_updater import update_election_sheet
from .fiirumi_area_generator import should_generate_areas, generate_election_areas

logger = logging.getLogger("vaalilakanabot")


def _dm(
    func: Callable[..., Coroutine[Any, Any, Any]], data_manager: DataManager
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Wrap (update, data_manager) handler as (update, context) handler."""
    async def wrapper(update: Update, _: ContextTypes.DEFAULT_TYPE) -> Any:
        return await func(update, data_manager)
    return wrapper


def _dm_ctx(
    func: Callable[..., Coroutine[Any, Any, Any]], data_manager: DataManager
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Wrap (update, context, data_manager) handler as (update, context) handler."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        return await func(update, context, data_manager)
    return wrapper


def _job(
    func: Callable[..., Coroutine[Any, Any, Any]], data_manager: DataManager
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Wrap (context, data_manager) job as (context) job."""
    async def wrapper(context: ContextTypes.DEFAULT_TYPE) -> Any:
        return await func(context, data_manager)
    return wrapper


def setup_logging() -> None:
    """Setup logging configuration."""
    logger.setLevel(logging.INFO)
    fh = logging.StreamHandler(sys.stdout)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.warning("Update '%s' caused error '%s'", update, context.error)


async def process_application_queue(
    _: ContextTypes.DEFAULT_TYPE, data_manager: DataManager
) -> None:
    """Flush queued applications, status updates, channel operations, and user operations to Google Sheets."""
    try:
        data_manager.flush_all_queues()
        logger.debug("Successfully flushed all queues")
    except Exception as e:
        logger.error("Error in queue processing job: %s", e)


async def post_init(
    app: Application[Any, Any, Any, Any, Any, Any], data_manager: DataManager
) -> None:
    """Post initialization setup."""
    app.bot_data["data_manager"] = data_manager

    # Generate election areas if configured for current year
    election_year_int: Optional[int] = None
    if ELECTION_YEAR:
        try:
            election_year_int = int(ELECTION_YEAR)
        except ValueError:
            logger.error(
                "Invalid ELECTION_YEAR configuration %r; skipping election area generation",
                ELECTION_YEAR,
            )
    if election_year_int is not None and should_generate_areas(election_year_int):
        logger.info("Generating election areas for year %s", election_year_int)
        success = generate_election_areas(election_year_int)
        if not success:
            logger.error(
                "Failed to generate election areas for year %s", election_year_int
            )
    else:
        logger.debug("Skipping election area generation")

    jq = app.job_queue
    if jq is None:
        raise ValueError("JobQueue is None")

    # Schedule jobs
    jq.run_repeating(
        _job(parse_fiirumi_posts, data_manager),
        interval=60,
        first=datetime.datetime(2025, 8, 10, hour=0),
    )
    jq.run_repeating(
        _job(announce_new_responses, data_manager),
        interval=3600,
        first=datetime.datetime(2025, 8, 10, hour=0),
    )

    jq.run_repeating(
        _job(update_election_sheet, data_manager),
        interval=60,
        first=datetime.datetime(2025, 8, 10, hour=0),
    )

    jq.run_repeating(
        _job(process_application_queue, data_manager),
        interval=60,
        first=datetime.datetime(2025, 8, 10, hour=0, minute=0, second=10),
    )

    # Admin command handlers
    app.add_handler(CommandHandler("remove", _dm_ctx(remove_applicant, data_manager)))
    app.add_handler(CommandHandler("add_fiirumi", _dm(add_fiirumi_to_applicant, data_manager)))
    app.add_handler(CommandHandler("remove_fiirumi", _dm(unassociate_fiirumi, data_manager)))
    app.add_handler(CommandHandler("elected", _dm_ctx(add_elected_tag, data_manager)))
    app.add_handler(CommandHandler("combine", _dm_ctx(combine_applicants, data_manager)))

    # export_data removed; use Google Sheets directly for raw exports
    app.add_handler(CommandHandler("export_officials_website", _dm(export_officials_website, data_manager)))
    app.add_handler(CommandHandler("admin_help", admin_help))

    # User command handlers
    app.add_handler(CommandHandler("start", _dm(register_channel, data_manager)))
    app.add_handler(CommandHandler("stop", _dm(unregister_channel, data_manager)))
    app.add_handler(CommandHandler("lakana", _dm(show_election_sheet, data_manager)))
    app.add_handler(CommandHandler("sheet", _dm(show_election_sheet_en, data_manager)))
    app.add_handler(
        CommandHandler("hakemukset", _dm(applications, data_manager), filters.ChatType.PRIVATE)
    )
    app.add_handler(
        CommandHandler("applications", _dm(applications_en, data_manager), filters.ChatType.PRIVATE)
    )

    for name in STICKER_COMMANDS:
        async def _sticker_handler(
            update: Update, _: ContextTypes.DEFAULT_TYPE, sticker_name: str = name
        ) -> None:
            await send_sticker(update, sticker_name)
        app.add_handler(CommandHandler(name, _sticker_handler))

    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("apua", apua_command))

    # Admin approval callback handler
    app.add_handler(
        CallbackQueryHandler(
            _dm_ctx(handle_admin_approval, data_manager),
            pattern="^(approve_|reject_)",
        )
    )

    application_states: Dict[object, List[Any]] = {
        SELECTING_DIVISION: [
            CallbackQueryHandler(_dm_ctx(select_division, data_manager))
        ],
        SELECTING_ROLE: [
            CallbackQueryHandler(
                _dm_ctx(handle_multiple_application_choice, data_manager),
                pattern="^(continue_multiple|cancel_multiple)$",
            ),
            CallbackQueryHandler(
                _dm_ctx(handle_back_button, data_manager),
                pattern="^back$",
            ),
            CallbackQueryHandler(_dm_ctx(select_role, data_manager)),
        ],
        CONFIRMING_APPLICATION: [
            CallbackQueryHandler(_dm_ctx(confirm_application, data_manager))
        ],
    }

    # Application conversation handlers
    # Finnish application handler
    hae_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "hae",
                _dm_ctx(hae, data_manager),
                filters.ChatType.PRIVATE,
            )
        ],
        states=application_states,
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("hae", _dm_ctx(hae, data_manager)),
        ],
    )

    # English application handler
    apply_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "apply",
                _dm_ctx(apply, data_manager),
                filters.ChatType.PRIVATE,
            )
        ],
        states=application_states,
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("apply", _dm_ctx(apply, data_manager)),
        ],
    )

    app.add_handler(hae_handler)
    app.add_handler(apply_handler)

    # Register conversation (user info for applications)
    register_states: Dict[object, List[Any]] = {
        REGISTER_NAME: [
            MessageHandler(filters.TEXT & (~filters.COMMAND), register_name)
        ],
        REGISTER_EMAIL: [
            MessageHandler(filters.TEXT & (~filters.COMMAND), register_email)
        ],
        REGISTER_CONSENT: [
            CallbackQueryHandler(
                _dm_ctx(register_consent, data_manager),
                pattern="^register_consent_(yes|no)$",
            )
        ],
    }
    register_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "rekisteroidy",
                _dm_ctx(register_start_finnish, data_manager),
                filters.ChatType.PRIVATE,
            ),
            CommandHandler(
                "register",
                _dm_ctx(register_start_english, data_manager),
                filters.ChatType.PRIVATE,
            ),
        ],
        states=register_states,
        fallbacks=[CommandHandler("cancel", register_cancel)],
    )
    app.add_handler(register_handler)

    app.add_error_handler(error)  # type: ignore[arg-type]

    logger.info("Post init done.")


def main() -> None:
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

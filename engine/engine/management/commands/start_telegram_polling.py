import logging

import telegram.error
from django.core.management.base import BaseCommand
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from apps.telegram.client import TelegramClient
from apps.telegram.updates.update_manager import UpdateManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def start_telegram_polling():
    telegram_client = TelegramClient()

    telegram_client.delete_webhook()

    application = Application.builder().token(telegram_client.token).build()

    application.add_error_handler(error_handler)
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    application.add_handler(CallbackQueryHandler(handle_message))

    # start the long polling loop; blocks until interrupted
    application.run_polling()


async def error_handler(update, context):
    try:
        raise context.error
    except telegram.error.Conflict as e:
        logger.warning(f"Tried to getUpdates() using telegram long polling, but conflict exists, got error: {e}")


async def handle_message(update, context):
    logger.debug(f"Update from Telegram: {update}")

    UpdateManager.process_update(update)


class Command(BaseCommand):
    def handle(self, *args, **options):
        logger.info("Starting telegram polling...")
        start_telegram_polling()

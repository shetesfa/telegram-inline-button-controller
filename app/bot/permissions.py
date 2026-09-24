"""Security and administrator authorization checks."""

from functools import wraps
from typing import Any, Callable, Coroutine
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext.filters import UpdateFilter
from app.config import config
from app.utils.logging import logger


class AdminFilter(UpdateFilter):
    """Filter that matches only authorized administrators."""

    def filter(self, update: Update) -> bool:
        user = update.effective_user
        if not user:
            return False
        return config.is_admin(user.id)


admin_filter = AdminFilter()


def admin_required(
    func: Callable[
        [Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, Any]
    ]
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, Any]]:
    """
    Decorator for handlers to ensure only authorized admin IDs can execute actions.
    Unauthorized users receive a strict access-denied message.
    """

    @wraps(func)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any
    ) -> Any:
        user = update.effective_user
        if not user or not config.is_admin(user.id):
            user_info = f"ID={user.id if user else 'Unknown'}, Username=@{user.username if user and user.username else 'None'}"
            logger.warning(f"Unauthorized access attempt blocked: {user_info}")

            denied_text = (
                "⛔ <b>Access Denied</b>\n\n"
                "You are not authorized to use or configure this system.\n"
                "Your Telegram User ID is not listed in the administrator whitelist."
            )

            if update.callback_query:
                await update.callback_query.answer(
                    "⛔ Access Denied: Unauthorized administrator.", show_alert=True
                )
                try:
                    await update.callback_query.edit_message_text(
                        denied_text, parse_mode="HTML"
                    )
                except Exception:
                    pass
            elif update.effective_message:
                await update.effective_message.reply_text(
                    denied_text, parse_mode="HTML"
                )
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper

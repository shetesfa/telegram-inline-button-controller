"""Core post processor: intercepts new Telegram posts and attaches configured inline keyboards."""

import asyncio
from typing import Optional
from telegram import Update
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import ContextTypes
from app.services.button_service import ButtonService
from app.services.destination_service import DestinationService
from app.services.post_service import PostService
from app.services.system_service import SystemService
from app.utils.logging import logger


async def handle_incoming_post(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Main handler for newly published channel posts and group messages.
    Guarantees:
    - Only processes future incoming updates (no history reading).
    - Preserves original post content, text, media, captions, formatting completely.
    - Applies duplicate protection and album deduplication.
    - Errors are isolated per post/channel.
    """
    message = update.channel_post or update.message
    if not message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    message_id = message.message_id
    media_group_id = message.media_group_id

    try:
        # 1. Check Master Global Automation Switch
        if not await SystemService.is_global_automation_enabled():
            logger.debug(
                f"Global automation is OFF. Ignoring post (chat={chat_id}, msg={message_id})"
            )
            return

        # 2. Check if destination is registered
        destination = await DestinationService.get_by_chat_id(chat_id)
        if not destination:
            # Not a configured destination; ignore silently
            return

        # 3. Check if destination and automation are enabled
        if not destination.is_enabled:
            logger.debug(
                f"Destination '{destination.title}' (ID={destination.id}) is disabled. Skipping post."
            )
            return

        if not destination.automation_enabled:
            logger.debug(
                f"Automation for '{destination.title}' (ID={destination.id}) is paused. Skipping post."
            )
            return

        # 4. Check duplicate protection & album deduplication
        should_run, reason = await PostService.should_process(
            destination_id=destination.id,
            message_id=message_id,
            media_group_id=media_group_id,
        )
        if not should_run:
            logger.debug(
                f"Skipping post {message_id} in '{destination.title}': {reason}"
            )
            return

        # 5. Fetch active buttons for this destination
        buttons = await ButtonService.list_for_destination(
            destination_id=destination.id, active_only=True
        )
        if not buttons:
            logger.info(
                f"No active buttons configured for '{destination.title}' (ID={destination.id}). Post skipped."
            )
            await PostService.record_result(
                destination_id=destination.id,
                message_id=message_id,
                media_group_id=media_group_id,
                status="SKIPPED_NO_BUTTONS",
            )
            return

        # 6. Build the inline keyboard
        keyboard = ButtonService.build_inline_keyboard(
            buttons=buttons, layout_mode=destination.layout_mode
        )
        if not keyboard:
            return

        # 7. Apply the inline keyboard to the message with rate-limit retry support
        logger.info(
            f"Applying inline keyboard ({len(buttons)} buttons) to new post: "
            f"chat='{destination.title}' ({chat_id}), msg_id={message_id}, album={media_group_id}"
        )

        max_retries = 2
        success = False

        for attempt in range(max_retries + 1):
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=keyboard,
                )
                success = True
                break

            except RetryAfter as e:
                wait_time = min(e.retry_after, 5.0)
                logger.warning(
                    f"Telegram rate limit hit. Waiting {wait_time}s before retry (attempt {attempt + 1})..."
                )
                await asyncio.sleep(wait_time)

            except BadRequest as e:
                # E.g. "Message is not modified" or "Message to edit not found"
                err_msg = e.message.lower()
                if "message is not modified" in err_msg:
                    logger.debug(f"Message {message_id} already has desired markup.")
                    success = True
                    break
                elif "message can't be edited" in err_msg:
                    logger.warning(
                        f"Cannot edit message {message_id} in '{destination.title}': "
                        f"Bot may lack 'Edit Messages' permission or message type cannot take markup."
                    )
                    break
                else:
                    logger.error(
                        f"BadRequest while editing post {message_id} in '{destination.title}': {e.message}"
                    )
                    break

            except Forbidden as e:
                logger.error(
                    f"Forbidden: Bot lacks permissions or was removed from '{destination.title}': {e.message}"
                )
                break

            except TelegramError as e:
                logger.error(
                    f"Telegram API error on post {message_id} in '{destination.title}': {e.message}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(1.0)
                else:
                    break

        # 8. Record operational status
        final_status = "SUCCESS" if success else "FAILED"
        await PostService.record_result(
            destination_id=destination.id,
            message_id=message_id,
            media_group_id=media_group_id,
            status=final_status,
        )

        if success:
            logger.info(
                f"Successfully attached inline keyboard to post {message_id} in '{destination.title}'."
            )

    except Exception as e:
        logger.exception(
            f"Unexpected error processing post {message_id} in chat {chat_id}: {e}"
        )

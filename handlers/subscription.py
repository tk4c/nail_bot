# ============================================================
# handlers/subscription.py — Проверка подписки на канал
# ============================================================

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatMemberLeft,
    ChatMemberBanned,
)

from config import CHANNEL_ID, CHANNEL_LINK

from aiogram import Router

router = Router()


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на обязательный канал."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        # ChatMemberLeft и ChatMemberBanned — не подписан
        return not isinstance(member, (ChatMemberLeft, ChatMemberBanned))
    except Exception:
        # Если не удалось проверить — пропускаем (чтобы бот не ломался)
        return True


def subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопками «Подписаться» и «Проверить подписку»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")],
    ])

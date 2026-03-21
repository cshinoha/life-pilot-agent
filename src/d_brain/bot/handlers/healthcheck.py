"""Daily healthcheck — sends bot status at 09:00."""

import json
import logging
from datetime import date, datetime

from aiogram import Bot

from d_brain.config import get_settings
from d_brain.services.storage import VaultStorage

logger = logging.getLogger(__name__)


async def scheduled_healthcheck(bot: Bot, chat_id: int) -> None:
    """Send daily health status at 09:00."""
    settings = get_settings()
    storage = VaultStorage(settings.vault_path)

    today = date.today()
    yesterday = date.fromordinal(today.toordinal() - 1)

    # Count yesterday's entries
    daily_content = storage.read_daily(yesterday)
    entry_count = daily_content.count("\n## ") if daily_content else 0

    # Check GROW state
    grow_status = "—"
    grow_state_path = settings.vault_path / ".grow_state.json"
    if grow_state_path.exists():
        try:
            state = json.loads(grow_state_path.read_text())
            period = state.get("period", "?")
            done = state.get("done", False)
            grow_status = f"{period} ({'✅' if done else '⏳'})"
        except Exception:
            grow_status = "ошибка чтения"

    msg = (
        "✅ <b>Бот работает</b>\n\n"
        f"📅 Вчера: {entry_count} записей\n"
        f"📊 GROW: {grow_status}\n"
        f"⏰ {datetime.now().strftime('%H:%M')} · {today.isoformat()}"
    )

    try:
        await bot.send_message(chat_id, msg)
        logger.info("Healthcheck sent")
    except Exception:
        logger.exception("Failed to send healthcheck")

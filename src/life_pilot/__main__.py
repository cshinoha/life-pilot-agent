"""Entry point for running life-pilot as a module."""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point."""
    from life_pilot.bot.main import run_bot
    from life_pilot.config import get_settings

    settings = get_settings()
    logger.info("life-pilot starting...")
    logger.info("Vault path: %s", settings.vault_path)
    logger.info("Allowed users: %s", settings.allowed_user_ids or "all")

    await run_bot(settings)


if __name__ == "__main__":
    asyncio.run(main())

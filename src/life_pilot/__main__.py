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
    from life_pilot.services.factory import get_runner

    settings = get_settings()
    runtime_status = get_runner().get_runtime_status(trigger_bootstrap=True)
    logger.info("life-pilot starting...")
    logger.info("Vault path: %s", settings.vault_path)
    logger.info("Allowed users: %s", settings.allowed_user_ids or "all")
    if runtime_status["ready"]:
        logger.info("LLM runtime: %s", runtime_status["summary"])
    else:
        logger.warning("LLM runtime: %s", runtime_status["details"])

    await run_bot(settings)


if __name__ == "__main__":
    asyncio.run(main())

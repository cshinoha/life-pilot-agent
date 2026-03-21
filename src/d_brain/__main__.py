"""Entry point for running d-brain as a module."""

import asyncio
import logging
import signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point."""
    from d_brain.bot.main import run_bot
    from d_brain.config import get_settings

    settings = get_settings()
    logger.info("d-brain starting...")
    logger.info("Vault path: %s", settings.vault_path)
    logger.info("Allowed users: %s", settings.allowed_user_ids or "all")

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler(sig: int) -> None:
        logger.info("Shutting down gracefully... (signal %s)", signal.Signals(sig).name)
        shutdown_event.set()
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler, sig)

    await run_bot(settings)


if __name__ == "__main__":
    asyncio.run(main())

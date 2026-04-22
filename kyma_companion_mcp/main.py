"""Main entry point for Kyma Companion MCP Server."""

import asyncio
import logging
import sys

from .config import settings
from .server import run_server


def setup_logging() -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def main() -> None:
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting Kyma Companion MCP Server...")
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

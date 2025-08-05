"""
Main CLI entry point for fapilog v3.

This module provides the command-line interface for fapilog v3,
allowing users to configure, test, and manage the async-first
logging system.
"""

import asyncio
import sys
from typing import Optional

from ..core.settings import UniversalSettings
from ..core.logger import AsyncLogger


async def main() -> int:
    """Main CLI entry point."""
    try:
        # TODO: Implement CLI argument parsing
        settings = UniversalSettings()
        
        async with AsyncLogger.create(settings) as logger:
            await logger.info("Fapilog v3 CLI started")
            await logger.info("Async-first logging system initialized")
            
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cli_main() -> int:
    """CLI main function for non-async entry."""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(cli_main()) 
#!/usr/bin/env python3
"""
Entry point for the Discord bot.

Usage:
    # With environment variables
    export DISCORD_TOKEN="your_token"
    export GEMINI_API_KEY="your_key"
    python run_discord.py

    # Or with arguments
    python run_discord.py --account main --provider gemini --owner 123456789

Environment variables:
    DISCORD_TOKEN - Required. Your Discord bot token.
    GEMINI_API_KEY - Required if using Gemini (default).
    ANTHROPIC_API_KEY - Required if using Claude.
    OPENAI_API_KEY - Required if using OpenAI.
    BOT_OWNER_ID - Optional. Discord user ID to restrict access.
"""
import os
import sys
import argparse
import asyncio
import logging

# Ensure we can import from the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from discord_bot.bot import create_bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_discord")


def main():
    parser = argparse.ArgumentParser(description="OSRS Discord Bot")
    parser.add_argument(
        "--account", "-a",
        default="main",
        help="Account ID to control (default: main)"
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["gemini", "claude", "openai"],
        default="gemini",
        help="LLM provider (default: gemini)"
    )
    parser.add_argument(
        "--owner", "-o",
        type=int,
        default=None,
        help="Discord user ID to restrict access (optional)"
    )
    parser.add_argument(
        "--token", "-t",
        default=None,
        help="Discord bot token (or set DISCORD_TOKEN env var)"
    )

    args = parser.parse_args()

    # Get Discord token
    token = args.token or os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("No Discord token provided. Set DISCORD_TOKEN env var or use --token")
        sys.exit(1)

    # Get owner ID from env if not provided
    owner_id = args.owner or os.environ.get("BOT_OWNER_ID")
    if owner_id:
        owner_id = int(owner_id)

    # Verify LLM API key exists
    if args.provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    elif args.provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    elif args.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    logger.info(f"Starting bot with account={args.account}, provider={args.provider}")
    if owner_id:
        logger.info(f"Access restricted to user ID: {owner_id}")

    # Create and run bot
    bot = create_bot(
        llm_provider=args.provider,
        account_id=args.account,
        owner_id=owner_id
    )

    bot.run(token)


if __name__ == "__main__":
    main()

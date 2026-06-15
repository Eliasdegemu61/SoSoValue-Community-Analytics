from __future__ import annotations

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession

from .config import load_env, require_env


load_env()

API_ID = int(require_env("TELEGRAM_API_ID"))
API_HASH = require_env("TELEGRAM_API_HASH")


async def main() -> None:
    print("Starting Telegram login flow to generate TELEGRAM_STRING_SESSION...")
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start()
        session_string = client.session.save()
        print("\nCopy this into your GitHub repository secret TELEGRAM_STRING_SESSION:\n")
        print(session_string)


if __name__ == "__main__":
    asyncio.run(main())

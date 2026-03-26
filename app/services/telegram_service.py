from typing import List

import httpx

from app.core.config import settings


async def send_long_message(chat_id: int, text: str) -> None:
    chunks = split_message(text, settings.telegram_message_limit)
    for chunk in chunks:
        await send_telegram_message(chat_id, chunk)


def split_message(text: str, max_length: int = 4000) -> List[str]:
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        split_at = remaining.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def send_telegram_message(chat_id: int, text: str) -> None:
    url = f"{settings.telegram_api_base}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        response = await http_client.post(url, json=payload)
        response.raise_for_status()


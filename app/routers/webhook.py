import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Request

from app.core.config import settings
from app.services.content_extractor import (
    build_extraction_failure_message,
    clean_article_text,
    extract_content,
)
from app.services.llm_service import summarize_and_insight
from app.services.telegram_service import send_long_message

router = APIRouter()


@router.get("/")
def health() -> dict:
    return {
        "status": "ok",
        "version": "v2-no-echo",
        "app_version": settings.app_version,
    }


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    update = await request.json()
    background_tasks.add_task(process_message, update)
    return {"status": "ok"}


async def process_message(update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text") or ""

    if not chat_id:
        return

    url = extract_url(text)
    if not url:
        await send_long_message(chat_id, "URL이 포함된 메시지를 보내주세요.")
        return

    await send_long_message(chat_id, "링크를 분석 중입니다.")

    try:
        content = await extract_content(url)
        article_text = clean_article_text(content.text)

        if not article_text:
            failure_message = build_extraction_failure_message(url, content.error_reason)
            await send_long_message(chat_id, failure_message)
            return

        if content.fallback_used:
            await send_long_message(
                chat_id,
                "PDF 본문 추출에 실패하여 arXiv 초록 기반으로 분석합니다.",
            )

        result = await summarize_and_insight(
            article_text=article_text,
            source_type=content.source_type,
            title=content.title,
        )
        await send_long_message(chat_id, result)
    except Exception as exc:
        await send_long_message(chat_id, f"처리 중 오류가 발생했습니다: {exc}")


def extract_url(text: str) -> Optional[str]:
    match = re.search(r"(https?://[^\s]+)", text)
    return match.group(1) if match else None

import os
import re
import asyncio
from typing import Optional, List

import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from newspaper import Article
from openai import OpenAI

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
AZURE_OPENAI_DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TELEGRAM_MESSAGE_LIMIT = 4000

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=f"{AZURE_OPENAI_ENDPOINT}/openai/v1/"
)


@app.get("/")
def health():
    return {"status": "ok", "version": "v2-no-echo"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    update = await request.json()
    background_tasks.add_task(process_message, update)
    return {"status": "ok"}


async def process_message(update: dict):
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
        article_text = await fetch_article_text(url)
        article_text = clean_article_text(article_text)

        if not article_text:
            await send_long_message(chat_id, "본문을 추출하지 못했습니다.")
            return

        result = await translate_and_insight(article_text)
        await send_long_message(chat_id, result)

    except Exception as e:
        error_message = f"처리 중 오류가 발생했습니다: {str(e)}"
        await send_long_message(chat_id, error_message)


def extract_url(text: str) -> Optional[str]:
    match = re.search(r"(https?://[^\s]+)", text)
    return match.group(1) if match else None


async def fetch_article_text(url: str) -> str:
    return await asyncio.to_thread(_fetch_article_text_sync, url)


def _fetch_article_text_sync(url: str) -> str:
    article = Article(url)
    article.download()
    article.parse()
    return article.text.strip()


def clean_article_text(text: str, max_chars: int = 12000) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()[:max_chars]


async def translate_and_insight(article_text: str) -> str:
    prompt = build_prompt(article_text)
    return await asyncio.to_thread(_translate_and_insight_sync, prompt)


def _translate_and_insight_sync(prompt: str) -> str:
    response = client.responses.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        input=prompt,
    )
    return response.output_text.strip()


def build_prompt(article_text: str) -> str:
    return f"""
당신은 외신 번역 및 비즈니스 분석 보조자다.

아래 원문을 읽고 다음 규칙을 반드시 지켜라.

[역할]
- 정확한 한국어 번역가
- 실무형 비즈니스 분석가

[번역 규칙]
1. 한국어로 번역한다.
2. 직역 우선으로 번역한다.
3. 원문에 없는 내용을 추가하지 않는다.
4. 문장을 임의로 요약하거나 생략하지 않는다.
5. 고유명사, 숫자, 날짜, 회사명, 제품명은 정확히 유지한다.
6. 과도하게 자연스럽게 바꾸기보다 원문 의미 보존을 우선한다.

[인사이트 규칙]
1. 인사이트는 반드시 3개만 작성한다.
2. 단순 요약이 아니라 아래 3가지를 포함한다.
   - 왜 중요한가
   - 어떤 변화 또는 트렌드를 보여주는가
   - 기업, 실무자, 투자자 관점에서 어떤 시사점이 있는가
3. 추측은 하지 말고, 원문을 근거로 해석하라.

[출력 형식]
[번역]
여기에 전체 번역문

[인사이트]
1. 제목: ...
   설명: ...
2. 제목: ...
   설명: ...
3. 제목: ...
   설명: ...

[원문]
{article_text}
""".strip()


async def send_long_message(chat_id: int, text: str):
    chunks = split_message(text, TELEGRAM_MESSAGE_LIMIT)
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


async def send_telegram_message(chat_id: int, text: str):
    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        response = await http_client.post(url, json=payload)
        response.raise_for_status()
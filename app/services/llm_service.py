import asyncio
import re

from openai import OpenAI

from app.core.config import settings

_client = OpenAI(
    api_key=settings.azure_openai_api_key,
    base_url=settings.azure_openai_base_url,
)


def detect_korean_ratio(text: str) -> float:
    korean_chars = len(re.findall(r"[가-힣]", text))
    alpha_chars = len(re.findall(r"[A-Za-z가-힣]", text))
    if alpha_chars == 0:
        return 0.0
    return korean_chars / alpha_chars


async def translate_and_insight(
    article_text: str,
    mode: str,
    source_type: str,
    title: str,
) -> str:
    prompt = build_prompt(
        article_text=article_text,
        mode=mode,
        source_type=source_type,
        title=title,
    )
    return await asyncio.to_thread(_translate_and_insight_sync, prompt)


def _translate_and_insight_sync(prompt: str) -> str:
    response = _client.responses.create(
        model=settings.azure_openai_deployment,
        input=prompt,
    )
    return response.output_text.strip()


def build_prompt(article_text: str, mode: str, source_type: str, title: str) -> str:
    task_section = """
[작업 모드]
- 번역 + 인사이트

[작업 규칙]
1. 원문을 한국어로 번역한다.
2. 직역 우선으로 번역한다.
3. 원문에 없는 내용을 추가하지 않는다.
4. 문장을 임의로 요약하거나 생략하지 않는다.
5. 고유명사, 숫자, 날짜, 회사명, 제품명은 정확히 유지한다.
6. 과도하게 자연스럽게 바꾸기보다 원문 의미 보존을 우선한다.

[출력 형식]
[번역]
여기에 전체 번역문
""".strip()

    output_section = """
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
""".strip()

    if mode == "summarize":
        task_section = """
[작업 모드]
- 요약 + 인사이트

[작업 규칙]
1. 번역하지 말고 한국어로 요약한다.
2. 핵심 내용, 근거, 결론을 빠짐없이 담아 구조적으로 요약한다.
3. 원문에 없는 내용을 추가하지 않는다.
4. 과장하거나 단정하지 않는다.

[출력 형식]
[요약]
여기에 핵심 요약문
""".strip()
        output_section = """
[출력 형식]
[요약]
여기에 핵심 요약문

[인사이트]
1. 제목: ...
   설명: ...
2. 제목: ...
   설명: ...
3. 제목: ...
   설명: ...
""".strip()

    return f"""
당신은 외신 번역 및 비즈니스 분석 보조자다.

아래 입력 정보를 읽고 다음 규칙을 반드시 지켜라.

[역할]
- 정확한 한국어 분석가
- 실무형 비즈니스 분석가

{task_section}

[인사이트 규칙]
1. 인사이트는 반드시 3개만 작성한다.
2. 단순 요약이 아니라 아래 3가지를 포함한다.
   - 왜 중요한가
   - 어떤 변화 또는 트렌드를 보여주는가
   - 기업, 실무자, 투자자 관점에서 어떤 시사점이 있는가
3. 추측은 하지 말고, 원문을 근거로 해석하라.

{output_section}

[메타데이터]
- 소스 타입: {source_type}
- 제목: {title}
- 처리 모드: {mode}

[원문]
{article_text}
""".strip()


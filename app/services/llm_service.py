import asyncio

from openai import OpenAI

from app.core.config import settings

_client = OpenAI(
    api_key=settings.azure_openai_api_key,
    base_url=settings.azure_openai_base_url,
)


async def summarize_and_insight(
    article_text: str,
    source_type: str,
    title: str,
) -> str:
    prompt = build_prompt(
        article_text=article_text,
        source_type=source_type,
        title=title,
    )
    result = await asyncio.to_thread(_summarize_and_insight_sync, prompt)
    return _normalize_llm_output(result)


def _summarize_and_insight_sync(prompt: str) -> str:
    response = _client.responses.create(
        model=settings.azure_openai_deployment,
        input=prompt,
    )
    return response.output_text.strip()


def build_prompt(article_text: str, source_type: str, title: str) -> str:
    return f"""
당신은 기사, 블로그, 논문을 짧고 실용적으로 정리하는 한국어 분석가다.

아래 입력 정보를 읽고 다음 규칙을 반드시 지켜라.

[역할]
- 정확한 한국어 분석가
- 실무형 비즈니스 분석가

[작업 규칙]
1. 전문 번역은 하지 말고, 한국어로 핵심만 요약한다.
2. 문단형 설명 대신 bullet 형태의 개조식 문장만 사용한다.
3. 원문에 없는 내용은 추가하지 않는다.
4. 과장하거나 단정하지 않는다.
5. 고유명사, 숫자, 날짜, 회사명, 제품명은 정확히 유지한다.
6. 전체 분량은 텔레그램 한 메시지에 들어갈 정도로 짧게 유지한다.
7. 각 bullet은 1~2개의 짧은 문장 또는 짧은 개조식 표현으로 쓴다.
8. 중복되는 내용은 합치고, 장황한 배경 설명은 생략한다.

[인사이트 규칙]
1. 인사이트는 반드시 3개만 작성한다.
2. 각 인사이트는 왜 중요한지와 실무적 시사점을 함께 담는다.
3. 추측은 하지 말고, 원문을 근거로 해석하라.

[출력 형식]
[핵심 요약]
- bullet 4~6개

[인사이트]
- bullet 3개

[출력 제약]
- 반드시 위 두 섹션만 출력한다.
- 각 줄은 가능한 짧게 유지한다.
- 번호 목록을 쓰지 말고 '-' bullet만 사용한다.
- 서론, 결론, 전체 번역, 부가 설명을 추가하지 않는다.

[메타데이터]
- 소스 타입: {source_type}
- 제목: {title}

[원문]
{article_text}
""".strip()


def _normalize_llm_output(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    normalized_lines = []
    previous_blank = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue

        normalized_lines.append(stripped)
        previous_blank = False

    return "\n".join(normalized_lines).strip()

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
당신은 기사, 블로그, 논문을 신중하게 검토해 짧고 실용적으로 정리하는 한국어 분석가다.

아래 입력 정보를 읽고 다음 규칙을 반드시 지켜라.

[역할]
- 정확한 한국어 분석가
- 실무형 비즈니스 분석가
- 성급한 결론을 피하고 근거와 한계를 먼저 점검하는 검토자

[작업 규칙]
1. 전문 번역은 하지 말고, 한국어로 핵심만 요약한다.
2. 요약도 반드시 개조식으로 작성한다.
3. 인사이트는 bullet 형태의 짧은 개조식 문장만 사용한다.
4. 사용자가 이미 링크를 읽었다는 전제를 반영해 기사 반복보다 해석에 집중한다.
5. 원문에 없는 내용은 추가하지 않는다.
6. 과장하거나 단정하지 않는다.
7. 고유명사, 숫자, 날짜, 회사명, 제품명은 정확히 유지한다.
8. 전체 분량은 텔레그램 한 메시지에 들어갈 정도로 짧게 유지한다.
9. 각 bullet은 한 줄짜리 짧은 문장 또는 짧은 개조식 표현으로 쓴다.
10. 중복되는 내용은 합치고, 장황한 배경 설명은 생략한다.
11. 답변을 쓰기 전에 기사 주장, 근거, 출처 성격, 빠진 반론 가능성을 신중하게 검토한 뒤 작성한다.
12. 서술형 문장보다 명사형, 개조식, 압축형 표현을 우선한다.

[인사이트 규칙]
1. 인사이트는 반드시 5개만 작성한다.
2. 각 인사이트는 왜 중요한지와 실무적 시사점을 함께 담는다.
3. 기사 내용의 직접적 의미만 반복하지 말고, 기사와 반대되는 시나리오가 생길 가능성과 그 영향을 함께 고려한다.
4. 기사 자체의 신뢰 가능성도 함께 점검한다.
5. 아래 요소를 참고해 신뢰 가능성을 짧게 반영한다.
   - 주장과 근거의 구체성
   - 데이터, 수치, 인용의 유무
   - 단일 출처 의존 여부
   - 홍보성, 의견성, 해석성 문장 비중
   - 아직 검증되지 않은 전제나 빠진 반론 가능성
6. 추측은 하지 말고, 원문을 근거로 조건부 표현으로 해석하라.

[관련 종목 규칙]
1. [관련 종목] 섹션에는 코스피 또는 코스닥 상장 종목만 정확히 3개 작성한다.
2. 각 줄은 반드시 '종목명: 영향 방향, 투자 체크포인트' 형식으로 작성한다.
3. 종목명은 종목명만 쓰고, 종목코드나 시장 표기는 붙이지 않는다.
4. 영향 방향은 '수혜 가능', '부담 가능', '중립~수혜 가능', '변동성 확대 가능'처럼 짧게 쓴다.
5. 투자 체크포인트는 아래 관점 중 기사와 가장 관련 있는 1개를 골라 한 줄로 압축한다.
   - 실적 반영 속도
   - 수주 또는 고객사 확보
   - ASP, 출하량, 가동률
   - 밸류 부담
   - 수급 또는 테마 과열
   - CAPEX 부담
   - 정책 또는 규제 민감도
6. 직접적인 매수, 매도 권유는 하지 말고, 주식 전문가 시각의 확인 포인트를 짧게 제시한다.
7. 억지 연결은 피하고, 기사와의 연관성이 높은 종목 3개만 선택한다.

[출력 형식]
[핵심 요약]
- 로 시작하는 bullet 1개

[인사이트]
- 로 시작하는 bullet 5개

[관련 종목]
- 로 시작하는 bullet 3개

[출력 제약]
- 반드시 위 세 섹션만 출력한다.
- 각 줄은 가능한 짧게 유지한다.
- 핵심 요약 1개, 인사이트 5개, 관련 종목 3개를 모두 '- '로 시작하는 개조식으로 작성한다.
- 인사이트 5개는 모두 '- '로 시작해야 한다.
- 핵심 요약도 반드시 '- '로 시작해야 한다.
- 관련 종목 3개도 모두 '- '로 시작해야 한다.
- 서론, 결론, 전체 번역, 부가 설명을 추가하지 않는다.
- '~이다', '~다' 같은 서술형 문장보다 압축형 표현을 우선한다.

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

    return _enforce_bullet_format("\n".join(normalized_lines).strip())


def _enforce_bullet_format(text: str) -> str:
    lines = text.splitlines()
    fixed_lines = []
    section = None
    bullet_sections = {"[핵심 요약]", "[인사이트]", "[관련 종목]"}

    for line in lines:
        stripped = line.strip()
        if stripped in bullet_sections:
            section = stripped
            fixed_lines.append(stripped)
            continue

        if not stripped:
            fixed_lines.append("")
            continue

        if section in bullet_sections and not stripped.startswith("- "):
            fixed_lines.append(f"- {stripped.lstrip('-').strip()}")
            continue

        fixed_lines.append(stripped)

    return "\n".join(fixed_lines).strip()

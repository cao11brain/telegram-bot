import asyncio
import re
from html import unescape
from io import BytesIO
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from newspaper import Article
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from app.core.config import settings
from app.models.content import ExtractedContent


async def extract_content(url: str) -> ExtractedContent:
    return await asyncio.to_thread(_extract_content_sync, url)


def _extract_content_sync(url: str) -> ExtractedContent:
    arxiv_id = extract_arxiv_id(url)
    if arxiv_id:
        try:
            arxiv_title, arxiv_text = extract_arxiv_pdf_text(arxiv_id)
            if len(arxiv_text.strip()) < settings.arxiv_min_text_length:
                raise ValueError("PDF에서 충분한 본문을 추출하지 못했습니다.")
            return ExtractedContent(
                text=arxiv_text,
                title=arxiv_title,
                source_type="arxiv_pdf",
                fallback_used=False,
            )
        except Exception:
            arxiv_title, arxiv_abstract = extract_arxiv_abstract(arxiv_id)
            if not arxiv_abstract.strip():
                raise ValueError("arXiv 초록을 추출하지 못했습니다.")
            return ExtractedContent(
                text=arxiv_abstract,
                title=arxiv_title,
                source_type="arxiv_abs",
                fallback_used=True,
            )

    article_title = ""
    article_text = ""
    error_reason: Optional[str] = None

    try:
        article_title, article_text = fetch_article_sync(url)
        if len(article_text.strip()) >= settings.generic_min_text_length:
            return ExtractedContent(
                text=article_text,
                title=article_title,
                source_type="generic_web",
                fallback_used=False,
            )
        error_reason = "short_content_http"
    except Exception as exc:
        error_reason = classify_fetch_error(exc)

    try:
        browser_title, browser_text = extract_content_with_browser(url)
        if len(browser_text.strip()) >= settings.generic_min_text_length:
            return ExtractedContent(
                text=browser_text,
                title=browser_title or article_title,
                source_type="generic_browser",
                fallback_used=False,
            )
        if browser_text.strip():
            return ExtractedContent(
                text=browser_text,
                title=browser_title or article_title,
                source_type="generic_browser_partial",
                fallback_used=False,
                error_reason="partial_content",
            )
        error_reason = "short_content_browser"
    except Exception as exc:
        error_reason = classify_fetch_error(exc)

    return ExtractedContent(
        text=article_text.strip(),
        title=article_title,
        source_type="generic_web",
        fallback_used=False,
        error_reason=error_reason,
    )


def fetch_article_sync(url: str) -> tuple[str, str]:
    article = Article(url)
    article.download()
    article.parse()
    return article.title.strip(), article.text.strip()


def extract_content_with_browser(url: str) -> tuple[str, str]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=7000)
        except Exception:
            pass

        title = (page.title() or "").strip()
        best_text = extract_text_from_document(page)

        for frame in page.frames:
            if frame == page.main_frame:
                continue
            frame_text = extract_text_from_document(frame)
            if len(frame_text) > len(best_text):
                best_text = frame_text

        browser.close()
        return title, best_text.strip()


def extract_text_from_document(html_or_dom_context: Any) -> str:
    script = """
() => {
  const selectors = [
    ".se-main-container",
    "article",
    "main",
    "[role='main']",
    ".post-content",
    ".entry-content",
    ".article-content",
    "#content"
  ];

  const collectText = (root) => {
    if (!root) return "";
    const clone = root.cloneNode(true);
    clone.querySelectorAll("script,style,noscript,nav,footer,aside,form,button,svg").forEach((el) => el.remove());
    return (clone.innerText || "").replace(/\s+/g, " ").trim();
  };

  let best = "";
  for (const sel of selectors) {
    const nodes = document.querySelectorAll(sel);
    for (const node of nodes) {
      const text = collectText(node);
      if (text.length > best.length) best = text;
    }
  }

  if (!best) {
    best = collectText(document.body);
  }
  return best;
}
""".strip()
    try:
        return (html_or_dom_context.evaluate(script) or "").strip()
    except Exception:
        return ""


def extract_arxiv_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if not parsed.netloc.endswith("arxiv.org"):
        return None

    path = parsed.path.strip("/")
    abs_match = re.match(r"^abs/([0-9]{4}\.[0-9]{5}(?:v[0-9]+)?)$", path)
    if abs_match:
        return abs_match.group(1)

    pdf_match = re.match(r"^pdf/([0-9]{4}\.[0-9]{5}(?:v[0-9]+)?)\.pdf$", path)
    if pdf_match:
        return pdf_match.group(1)

    return None


def extract_arxiv_pdf_text(arxiv_id: str) -> tuple[str, str]:
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client_http:
        response = client_http.get(pdf_url)
        response.raise_for_status()
        pdf_bytes = response.content

    reader = PdfReader(BytesIO(pdf_bytes))
    page_texts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        page_texts.append(page_text.strip())

    full_text = "\n\n".join(text for text in page_texts if text)
    title = f"arXiv:{arxiv_id}"
    return title, full_text


def extract_arxiv_abstract(arxiv_id: str) -> tuple[str, str]:
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client_http:
        response = client_http.get(abs_url)
        response.raise_for_status()
        html = response.text

    title = extract_html_meta_content(html, "citation_title") or f"arXiv:{arxiv_id}"

    abstract = ""
    block_match = re.search(
        r'<blockquote class="abstract mathjax">(.*?)</blockquote>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if block_match:
        block_html = block_match.group(1)
        block_text = strip_html_tags(block_html)
        abstract = re.sub(r"^\s*Abstract:\s*", "", block_text, flags=re.IGNORECASE).strip()

    if not abstract:
        desc = extract_html_meta_content(html, "description") or ""
        abstract = re.sub(r"^\s*Abstract:\s*", "", desc, flags=re.IGNORECASE).strip()

    return title, abstract


def extract_html_meta_content(html: str, name: str) -> str:
    pattern = rf'<meta[^>]+name="{re.escape(name)}"[^>]+content="([^"]+)"'
    match = re.search(pattern, html, flags=re.IGNORECASE)
    if not match:
        return ""
    return unescape(match.group(1)).strip()


def strip_html_tags(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", value)
    compact = re.sub(r"\s+", " ", no_tags)
    return unescape(compact).strip()


def clean_article_text(text: str, max_chars: int = 12000) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \\t]+", " ", text)
    return text.strip()[:max_chars]


def classify_fetch_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "429" in message or "too many requests" in message:
        return "rate_limited"
    if "403" in message or "forbidden" in message:
        return "access_denied"
    if "captcha" in message:
        return "captcha"
    if "login" in message or "sign in" in message:
        return "login_required"
    if "name resolution" in message or "nodename nor servname" in message:
        return "dns_error"
    if "timeout" in message:
        return "timeout"
    return "fetch_failed"


def build_extraction_failure_message(url: str, error_reason: Optional[str]) -> str:
    reason_map = {
        "rate_limited": "사이트 요청 제한(429)으로 본문을 가져오지 못했습니다.",
        "access_denied": "사이트 접근이 차단(403)되어 본문을 가져오지 못했습니다.",
        "captcha": "CAPTCHA가 요구되어 자동 추출이 불가능했습니다.",
        "login_required": "로그인이 필요한 페이지로 보입니다.",
        "dns_error": "사이트 연결(DNS) 문제로 페이지에 접근하지 못했습니다.",
        "timeout": "페이지 로딩 시간이 초과되었습니다.",
        "short_content_http": "정적 추출 결과가 너무 짧았습니다.",
        "short_content_browser": "브라우저 렌더링 후에도 본문이 충분하지 않았습니다.",
        "partial_content": "본문 일부만 추출되었습니다.",
        "fetch_failed": "본문 추출 중 오류가 발생했습니다.",
    }
    reason_text = reason_map.get(error_reason or "", "본문 추출에 실패했습니다.")
    return (
        f"{reason_text}\n\n"
        f"대체 방법:\n"
        f"1. 모바일/원문 본문 링크를 다시 보내주세요.\n"
        f"2. 로그인이나 권한이 필요한 페이지인지 확인해주세요.\n"
        f"3. 본문 텍스트를 직접 보내주시면 요약과 인사이트를 제공할 수 있습니다.\n"
        f"(입력 URL: {url})"
    )

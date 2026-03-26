from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExtractedContent:
    text: str
    title: str
    source_type: str
    fallback_used: bool
    error_reason: Optional[str] = None


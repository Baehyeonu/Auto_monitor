"""
Shared name parsing helpers.
"""
from __future__ import annotations

import re
from typing import Iterable, Sequence


DEFAULT_ROLE_KEYWORDS = {
    "조교",
    "주강사",
    "멘토",
    "매니저",
    "코치",
    "개발자",
    "학생",
    "수강생",
    "교육생",
    "강사",
    "관리자",
    "운영자",
    "팀장",
    "회장",
    "강의",
    "실습",
    "프로젝트",
    "팀",
}


_PARTS_PATTERN = re.compile(r"[/_\-|\s.()@{}\[\]\*]+")
_PARTS_PATTERN_ALL = re.compile(r"[/_\-|\s.()@{}\[\]!\*]+")


def _normalize_role_keywords(role_keywords: Sequence[str] | None) -> set[str]:
    if role_keywords is None:
        return set(DEFAULT_ROLE_KEYWORDS)
    return {str(keyword) for keyword in role_keywords if keyword}


def _extract_korean_parts(parts: Iterable[str]) -> list[str]:
    korean_parts: list[str] = []
    for part in parts:
        if any("\uAC00" <= char <= "\uD7A3" for char in part):
            korean_only = "".join(c for c in part if "\uAC00" <= c <= "\uD7A3")
            if korean_only:
                korean_parts.append(korean_only)
    return korean_parts


def extract_name_only(
    zep_name: str,
    *,
    role_keywords: Sequence[str] | None = None,
    fallback_to_first_part: bool = True,
) -> str:
    """Extract the primary Korean name from a ZEP name."""
    if not zep_name:
        return ""

    cleaned = zep_name.strip("*").strip()
    parts = [part.strip() for part in _PARTS_PATTERN.split(cleaned) if part.strip()]

    korean_parts = _extract_korean_parts(parts)
    role_keywords_set = _normalize_role_keywords(role_keywords)
    filtered = [part for part in korean_parts if part not in role_keywords_set]

    if filtered:
        return filtered[-1]
    if korean_parts:
        return korean_parts[-1]
    if fallback_to_first_part and parts:
        return parts[0]
    return cleaned


def extract_all_korean_names(
    zep_name: str,
    *,
    role_keywords: Sequence[str] | None = None,
) -> list[str]:
    """Extract all candidate Korean names in reverse order."""
    if not zep_name:
        return []

    cleaned = zep_name.strip("*").strip()
    parts = [part.strip() for part in _PARTS_PATTERN_ALL.split(cleaned) if part.strip()]

    korean_parts = _extract_korean_parts(parts)
    role_keywords_set = _normalize_role_keywords(role_keywords)
    filtered = [part for part in korean_parts if part not in role_keywords_set]
    target_parts = filtered if filtered else korean_parts

    if target_parts:
        return list(reversed(target_parts))
    return [cleaned]

from __future__ import annotations

import re
from pathlib import Path

from pydantic import Field

from schemas.implementation.common import SchemaModel


class ImplementationSpec(SchemaModel):
    source_path: str = Field(description="Original spec file path.")
    service_name: str = Field(description="Name of the target education service.")
    target_framework: str = Field(
        default="streamlit",
        description="Target application framework. Currently only streamlit is supported.",
    )
    team_identity: str = Field(
        default="교육 서비스 구현 전문 AI Agent 팀",
        description="Identity of the implementation team.",
    )
    service_purpose: str = Field(description="What the target service is trying to achieve.")
    target_users: list[str] = Field(default_factory=list, description="Primary target users.")
    learning_goals: list[str] = Field(default_factory=list, description="Learning outcomes.")
    core_features: list[str] = Field(default_factory=list, description="Core MVP features.")
    total_count: int = Field(default=8, description="Expected total number of generated items.")
    items_per_type: int = Field(
        default=2,
        description="Reference item count per feature type for downstream prompts/context.",
    )
    content_interaction_direction: list[str] = Field(
        default_factory=list,
        description="Rules for content and interaction generation.",
    )
    excluded_scope: list[str] = Field(
        default_factory=list, description="Out-of-scope items for the MVP."
    )
    expected_outputs: list[str] = Field(
        default_factory=list,
        description="Expected files or artifacts from the implementation team.",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Checklist used to validate the implementation.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Implementation constraints extracted from the source spec.",
    )


def parse_markdown_spec(path: Path) -> ImplementationSpec:
    text = path.read_text(encoding="utf-8")
    title, sections = _parse_markdown_sections(text)
    content_interaction_direction = _section_list(sections, "콘텐츠 및 상호작용 방향")

    return ImplementationSpec(
        source_path=str(path),
        service_name=title,
        target_framework="streamlit",
        service_purpose=_section_text(sections, "서비스 목적"),
        target_users=_section_list(sections, "대상 사용자"),
        learning_goals=_extract_learning_goals(sections),
        core_features=_extract_core_features(sections, content_interaction_direction),
        total_count=8,
        items_per_type=2,
        content_interaction_direction=content_interaction_direction,
        excluded_scope=_section_list(sections, "제외 범위"),
        expected_outputs=_section_list(sections, "기대 산출물"),
        acceptance_criteria=_section_list(sections, "검수 기준"),
        constraints=[
            "기본 입력 원본은 Markdown spec이다.",
            "이번 검증 사례는 질문력 향상 퀴즈 서비스다.",
            "runtime은 환경변수 기반 LLM client를 사용한다.",
        ],
    )


def _parse_markdown_sections(text: str) -> tuple[str, dict[str, list[str]]]:
    lines = text.splitlines()
    title = "교육 서비스 구현 명세서"
    current_section: str | None = None
    sections: dict[str, list[str]] = {}

    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections.setdefault(current_section, [])
            continue
        if current_section is not None:
            sections[current_section].append(line.rstrip())

    return title, sections


def _section_text(sections: dict[str, list[str]], title: str) -> str:
    lines = sections.get(title, [])
    cleaned = [_clean_bullet(line) for line in lines if line.strip()]
    return " ".join(cleaned)


def _section_list(sections: dict[str, list[str]], title: str) -> list[str]:
    lines = sections.get(title, [])
    results: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = _clean_bullet(stripped)
        if cleaned:
            results.append(cleaned)
    return results


def _clean_bullet(text: str) -> str:
    return re.sub(r"^[-*]\s*", "", text).strip()


def _extract_learning_goals(sections: dict[str, list[str]]) -> list[str]:
    canonical_dimensions = ["구체성", "맥락성", "목적성", "종합성"]
    extracted: list[str] = []
    for line in _section_list(sections, "학습 목표"):
        for dimension in canonical_dimensions:
            if dimension in line and dimension not in extracted:
                extracted.append(dimension)
    return extracted or _section_list(sections, "학습 목표")


def _extract_core_features(
    sections: dict[str, list[str]],
    content_interaction_direction: list[str],
) -> list[str]:
    for line in content_interaction_direction:
        if "유형은 예를 들어" not in line:
            continue
        snippet = line.split("유형은 예를 들어", 1)[1]
        snippet = snippet.split("처럼 구성할 수", 1)[0]
        candidates = [part.strip(" .") for part in snippet.split(",")]
        normalized = [_normalize_core_feature(candidate) for candidate in candidates if candidate.strip()]
        deduped: list[str] = []
        for feature in normalized:
            if feature and feature not in deduped:
                deduped.append(feature)
        if deduped:
            return deduped
    return _section_list(sections, "핵심 기능")


def _normalize_core_feature(feature: str) -> str:
    normalized = feature.strip()
    replacements = {
        "빠진 요소 찾기": "질문에서 빠진 요소 찾기",
        "모호한 질문 다시 쓰기": "모호한 질문 고치기",
    }
    return replacements.get(normalized, normalized)

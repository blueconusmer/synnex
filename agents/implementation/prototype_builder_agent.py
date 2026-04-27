"""Prototype builder agent for generating the Streamlit MVP application files."""

from __future__ import annotations

from pathlib import Path

from clients.llm import LLMClient
from loaders import load_planning_package
from orchestrator.app_source import build_content_filename, build_streamlit_app_source
from schemas.implementation.common import GeneratedFile
from schemas.implementation.prototype_builder import (
    PrototypeBuilderInput,
    PrototypeBuilderOutput,
)

from agents.implementation.helpers import dump_model, load_prompt_text, make_label


def run_prototype_builder_agent(
    input_model: PrototypeBuilderInput,
    llm_client: LLMClient,
) -> PrototypeBuilderOutput:
    """Generate app code artifacts for the current education-service MVP."""
    _ = llm_client
    _ = load_prompt_text
    _ = dump_model

    spec = input_model.implementation_spec
    service_name = spec.service_name or input_model.spec_intake_output.service_summary.split(" ")[0]
    content_filename = build_content_filename(service_name)
    app_source = _build_app_source(input_model)
    runtime_notes = [
        f"app.py는 outputs/{content_filename}을 읽는다.",
        "streamlit run app.py로 실행한다.",
    ]
    integration_notes = [
        f"{content_filename}이 outputs/ 아래에 존재해야 한다.",
    ]
    if _is_planning_package_dir(Path(spec.source_path)):
        runtime_notes.append("생성된 app.py는 Quest 세션 기반 화면(S0~S5)으로 동작한다.")
        integration_notes.append(
            "score_rules, grade_levels, grade_thresholds는 app.py 생성 시 상수로 삽입된다."
        )
    else:
        runtime_notes.append("planning package 입력이 아니면 generic viewer fallback을 사용한다.")
        integration_notes.append("generic viewer는 전체 콘텐츠를 한 번에 보여준다.")

    return PrototypeBuilderOutput(
        agent=make_label(
            "Prototype Builder Agent",
            "MVP 서비스 코드 생성 Agent",
        ),
        service_name=service_name or "교육 서비스 MVP",
        app_entrypoint="app.py",
        generated_files=[
            GeneratedFile(
                path="app.py",
                description="Self-contained Streamlit MVP app generated from service contents.",
                content=app_source,
            )
        ],
        runtime_notes=runtime_notes,
        integration_notes=integration_notes,
    )


def _build_app_source(input_model: PrototypeBuilderInput) -> str:
    spec = input_model.implementation_spec
    service_name = spec.service_name or "교육 서비스 MVP"
    content_filename = build_content_filename(service_name)
    source_path = Path(spec.source_path)

    if _is_planning_package_dir(source_path):
        package = load_planning_package(source_path)
        score_rules = dict(package.evaluation_spec.score_rules)
        grade_levels = list(package.evaluation_spec.grade_levels)
        grade_thresholds = _normalize_grade_thresholds(
            score_rules.get("service_grades", {}),
            grade_levels,
        )
        return build_streamlit_app_source(
            service_name=service_name,
            content_filename=content_filename,
            screens=list(package.interface_spec.screens),
            api_endpoints=list(package.interface_spec.api_endpoints),
            score_rules=score_rules,
            grade_levels=grade_levels,
            grade_thresholds=grade_thresholds,
        )

    return build_streamlit_app_source(
        service_name=service_name,
        content_filename=content_filename,
    )


def _normalize_grade_thresholds(
    service_grades: object,
    grade_levels: list[str],
) -> dict[str, dict[str, int | None]]:
    if not isinstance(service_grades, dict):
        return {}

    thresholds: dict[str, dict[str, int | None]] = {}
    for grade in grade_levels:
        raw_rule = service_grades.get(grade)
        min_score = 0
        max_score: int | None = None
        if isinstance(raw_rule, (list, tuple)) and raw_rule:
            first = raw_rule[0]
            second = raw_rule[1] if len(raw_rule) > 1 else None
            min_score = int(first) if first is not None else 0
            max_score = int(second) if second is not None else None
        thresholds[grade] = {
            "min_score": min_score,
            "max_score": max_score,
        }
    return thresholds


def _is_planning_package_dir(path: Path) -> bool:
    expected_files = {
        "constitution.md",
        "data_schema.json",
        "state_machine.md",
        "prompt_spec.md",
        "interface_spec.md",
        "pytest.py",
    }
    return path.is_dir() and all((path / file_name).exists() for file_name in expected_files)

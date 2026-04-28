from __future__ import annotations

from pathlib import Path

from agents.implementation.prototype_builder_agent import run_prototype_builder_agent
from loaders import load_planning_package, planning_package_to_implementation_spec
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.prototype_builder import PrototypeBuilderInput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"


def _build_package_content_output(fake: FakeLLMClient, service_name: str) -> ContentInteractionOutput:
    prompt = "\n".join(
        [
            f"- service_name: {service_name}",
            '- content_types: ["multiple_choice", "question_improvement"]',
            '- learning_goals: ["구체성", "맥락성", "목적성"]',
            "- total_count: 3",
            "- items_per_type: 2",
        ]
    )
    return fake.generate_json(prompt=prompt, response_model=ContentInteractionOutput)


def test_prototype_builder_materializes_llm_generated_app_from_planning_package() -> None:
    fake = FakeLLMClient()
    package = load_planning_package(PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, PACKAGE_DIR)

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(fake, spec.service_name),
            implementation_spec=spec,
        ),
        fake,
    )

    source = output.generated_files[0].content

    assert output.target_framework == "streamlit"
    assert output.is_supported is True
    assert output.unsupported_reason == ""
    assert output.generation_mode == "llm_generated"
    assert output.fallback_used is False
    assert "LLM_GENERATED_APP_MARKER" in source
    assert "def api_session_start()" in source
    assert "def api_quest_submit(user_response: Any)" in source
    assert "def api_session_result()" in source
    assert "question_quest_contents.json" in source
    assert "OUTPUT_PATH = APP_DIR / \"outputs\" / CONTENT_FILENAME" in source
    assert "CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]" in source
    assert "load_planning_package" not in source
    assert "constitution.md" not in source

    prompt = fake.prompts[-1]
    assert "# Interface Spec" in prompt
    assert "# State Machine" in prompt
    assert '"service_name": "question_quest"' in prompt or "service_name: question_quest" in prompt
    assert "data_schema" in prompt
    assert "prompt_spec" in prompt
    assert "target_framework: streamlit" in prompt
    assert package.service_meta.purpose[:20] in prompt


def test_prototype_builder_uses_fallback_when_llm_call_fails() -> None:
    fake = FakeLLMClient(fail_app_generation=True)
    package = load_planning_package(PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, PACKAGE_DIR)

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(fake, spec.service_name),
            implementation_spec=spec,
        ),
        fake,
    )

    assert output.generation_mode == "fallback_template"
    assert output.fallback_used is True
    assert "LLM_CALL_FAILED" in output.builder_errors
    assert "FALLBACK_USED" in output.builder_errors
    assert "LLM_CALL_FAILED" in output.fallback_reason
    assert "def api_session_start()" in output.generated_files[0].content


def test_prototype_builder_uses_fallback_when_llm_output_invalid() -> None:
    fake = FakeLLMClient(invalid_app_generation=True)
    package = load_planning_package(PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, PACKAGE_DIR)

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(fake, spec.service_name),
            implementation_spec=spec,
        ),
        fake,
    )

    assert output.generation_mode == "fallback_template"
    assert output.fallback_used is True
    assert "LLM_OUTPUT_INVALID" in output.builder_errors
    assert "FALLBACK_USED" in output.builder_errors
    assert "LLM_OUTPUT_INVALID" in output.fallback_reason


def test_prototype_builder_rejects_root_first_content_loading_contract() -> None:
    root_first_source = '''import json
import os
import streamlit as st

CONTENT_PATH = "question_quest_contents.json"
if not os.path.exists(CONTENT_PATH):
    with open("outputs/question_quest_contents.json", encoding="utf-8") as file:
        data = json.load(file)
else:
    with open(CONTENT_PATH, encoding="utf-8") as file:
        data = json.load(file)

if not data:
    st.warning("콘텐츠 파일을 찾지 못했습니다.")
st.write(data)
'''
    fake = FakeLLMClient(app_source=root_first_source)
    package = load_planning_package(PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, PACKAGE_DIR)

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(fake, spec.service_name),
            implementation_spec=spec,
        ),
        fake,
    )

    assert output.generation_mode == "fallback_template"
    assert output.fallback_used is True
    assert "LLM_OUTPUT_INVALID" in output.builder_errors
    assert "outputs/{content_filename}" in output.fallback_reason


def test_prototype_builder_returns_unsupported_output_for_react() -> None:
    fake = FakeLLMClient()
    package = load_planning_package(PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, PACKAGE_DIR).model_copy(
        update={"target_framework": "react"}
    )

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(fake, spec.service_name),
            implementation_spec=spec,
        ),
        fake,
    )

    assert output.target_framework == "react"
    assert output.is_supported is False
    assert "not supported yet" in output.unsupported_reason
    assert "streamlit" in output.unsupported_reason
    assert output.generated_files == []
    assert output.app_entrypoint == ""


def test_prototype_builder_distinguishes_invalid_target_framework() -> None:
    fake = FakeLLMClient()
    package = load_planning_package(PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, PACKAGE_DIR).model_copy(
        update={"target_framework": "stramlit"}
    )

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(fake, spec.service_name),
            implementation_spec=spec,
        ),
        fake,
    )

    assert output.target_framework == "stramlit"
    assert output.is_supported is False
    assert output.generated_files == []
    assert (
        output.unsupported_reason
        == "target_framework 'stramlit' is not recognized. "
        "Known values: fastapi, nextjs, react, streamlit."
    )

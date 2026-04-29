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


def _extract_function_block(source: str, name: str, next_name: str) -> str:
    return source.split(f"def {name}", 1)[1].split(f"def {next_name}", 1)[0]


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
    assert "current_screen" in source
    assert "SCREEN_MULTIPLE_CHOICE_RESULT" in source
    assert "SCREEN_IMPROVEMENT_RESULT" in source
    assert "st.rerun()" in source
    assert "st.experimental_rerun" not in source
    assert "load_planning_package" not in source
    assert "constitution.md" not in source

    submit_block = _extract_function_block(
        source,
        "api_quest_submit(user_response: Any) -> dict[str, Any]:",
        "api_session_result() -> dict[str, Any]:",
    )
    assert 'quest["choices"]' not in submit_block
    assert 'quest.get("choices"' not in submit_block
    assert 'quest["item_id"]' not in submit_block

    prompt = fake.prompts[-1]
    assert "# Interface Spec" in prompt
    assert "# State Machine" in prompt
    assert '"service_name": "question_quest"' in prompt or "service_name: question_quest" in prompt
    assert "data_schema" in prompt
    assert "prompt_spec" in prompt
    assert "target_framework: streamlit" in prompt
    assert package.service_meta.purpose[:20] in prompt
    assert "quest_id" in prompt
    assert "current_screen" in prompt
    assert "st.rerun()" in prompt
    assert "interaction_units(primary contract)" in prompt
    assert '"interaction_mode": "quiz"' in prompt or "interaction_mode:\nquiz" in prompt
    assert "primary contract" in prompt


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


def test_prototype_builder_rejects_improvement_evaluator_arity_mismatch() -> None:
    arity_mismatch_source = '''from pathlib import Path
from typing import Any

import streamlit as st

CONTENT_FILENAME = "question_quest_contents.json"
APP_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT_RESULT = "S4"
current_screen = "S3"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def evaluate_improvement_question(user_response: str, original_question: str, topic_context: str):
    return {}, "좋아졌어요.", 20


def api_session_start() -> dict[str, Any]:
    return {"quests": []}


def api_quest_submit(user_response: Any) -> dict[str, Any]:
    quest = {
        "quest_id": "quest-1",
        "quest_type": "question_improvement",
        "difficulty": "main",
        "original_question": "이거 뭐야?",
        "topic_context": "국어 숙제",
        "options": [],
        "desired_answer_form": "예시",
    }
    evaluate_improvement_question(
        user_response,
        quest["original_question"],
        quest["topic_context"],
        quest["desired_answer_form"],
    )
    return {"ok": True}


def api_session_result() -> dict[str, Any]:
    return {}


def render_multiple_choice_screen() -> None:
    st.write("mc")


def render_multiple_choice_result() -> None:
    st.write("mc-result")


def render_improvement_screen() -> None:
    st.write("improve")


def render_improvement_result() -> None:
    st.write("improve-result")


def main() -> None:
    if resolve_content_path() is None:
        st.warning("콘텐츠 파일을 찾지 못했습니다.")
    st.rerun()


main()
'''
    fake = FakeLLMClient(app_source=arity_mismatch_source)
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
    assert "evaluate_improvement_question call passes 4 positional args" in output.fallback_reason


def test_prototype_builder_rejects_raw_content_fields_in_submit_flow() -> None:
    raw_field_source = '''from pathlib import Path
from typing import Any

import streamlit as st

CONTENT_FILENAME = "question_quest_contents.json"
APP_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT_RESULT = "S4"
current_screen = "S1"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def api_session_start() -> dict[str, Any]:
    return {"quests": []}


def api_quest_submit(user_response: Any) -> dict[str, Any]:
    quest = {"choices": ["A", "B"], "correct_choice": "A"}
    if user_response == quest["choices"][0]:
        st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT
    else:
        st.session_state.current_screen = SCREEN_IMPROVEMENT_RESULT
    return {"ok": True}


def api_session_result() -> dict[str, Any]:
    return {}


def render_multiple_choice_screen() -> None:
    quest = {"item_id": "item-1", "options": ["A", "B"]}
    st.write(quest["item_id"])


def render_multiple_choice_result() -> None:
    st.write("result")


def render_improvement_screen() -> None:
    st.write("improve")


def render_improvement_result() -> None:
    st.write("feedback")


def main() -> None:
    if resolve_content_path() is None:
        st.warning("콘텐츠 파일을 찾지 못했습니다.")
    st.rerun()


main()
'''
    fake = FakeLLMClient(app_source=raw_field_source)
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
    assert "normalized quest fields only" in output.fallback_reason


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

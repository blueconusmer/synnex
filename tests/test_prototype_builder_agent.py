from __future__ import annotations

import json
from pathlib import Path

from agents.implementation.prototype_builder_agent import run_prototype_builder_agent
from loaders import load_input_intake, load_planning_package, planning_package_to_implementation_spec
from orchestrator.app_source import build_content_filename
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.prototype_builder import PrototypeBuilderInput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
QUEST_V2_PACKAGE_DIR = REPO_ROOT / "inputs" / "260429_퀘스트_v2"
CHATBOT_PACKAGE_DIR = REPO_ROOT / "inputs" / "260428_챗봇"


def _build_package_content_output(
    fake: FakeLLMClient,
    service_name: str,
    *,
    content_types: list[str] | None = None,
    total_count: int = 3,
    items_per_type: int = 2,
) -> ContentInteractionOutput:
    content_types = content_types or ["multiple_choice", "question_improvement"]
    prompt = "\n".join(
        [
            f"- service_name: {service_name}",
            f"- content_types: {json.dumps(content_types, ensure_ascii=False)}",
            f"- learning_goals: {json.dumps(['구체성', '맥락성', '목적성'], ensure_ascii=False)}",
            f"- total_count: {total_count}",
            f"- items_per_type: {items_per_type}",
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


def test_prototype_builder_materializes_llm_generated_v2_app_without_fallback() -> None:
    fake = FakeLLMClient()
    package = load_planning_package(QUEST_V2_PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, QUEST_V2_PACKAGE_DIR)

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(
                fake,
                spec.service_name,
                content_types=[
                    "multiple_choice",
                    "situation_card",
                    "question_improvement",
                    "situation_card",
                    "battle",
                ],
                total_count=5,
                items_per_type=1,
            ),
            implementation_spec=spec,
        ),
        fake,
    )

    source = output.generated_files[0].content
    prompt = fake.prompts[-1]

    assert output.generation_mode == "llm_generated"
    assert output.fallback_used is False
    assert "LLM_GENERATED_APP_MARKER" in source
    assert "current_screen" in source
    assert "SCREEN_BATTLE" in source
    assert "SCREEN_BATTLE_RESULT" in source
    assert "SCREEN_BATTLE_COMPLETED" in source
    assert "SCREEN_SESSION_RESULT" in source
    assert "st.session_state.current_screen = SCREEN_BATTLE_RESULT" in source
    assert "st.session_state.current_screen = SCREEN_BATTLE_COMPLETED" in source
    assert "st.session_state.current_screen = SCREEN_SESSION_RESULT" in source
    assert "builder_runtime_contract" in prompt
    assert "requires_battle: true" in prompt
    assert "required_screen_constants" in prompt
    assert "multiple_choice → situation_card → question_improvement → situation_card → battle" in prompt


def test_prototype_builder_materializes_llm_generated_coaching_app_without_legacy_quests() -> None:
    fake = FakeLLMClient()
    intake_result = load_input_intake(CHATBOT_PACKAGE_DIR)
    assert intake_result.implementation_spec is not None
    spec = intake_result.implementation_spec
    content_output = fake.generate_json(
        prompt="\n".join(
            [
                f"- service_name: {spec.service_name}",
                f"- content_types: {json.dumps(spec.core_features, ensure_ascii=False)}",
                f"- learning_goals: {json.dumps(spec.learning_goals, ensure_ascii=False)}",
                f"- total_count: {spec.total_count}",
                "- items_per_type: 0",
                "- interaction_mode: coaching",
            ]
        ),
        response_model=ContentInteractionOutput,
    )

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=content_output,
            implementation_spec=spec,
        ),
        fake,
    )

    source = output.generated_files[0].content

    assert output.generation_mode == "llm_generated"
    assert output.fallback_used is False
    assert 'get("interaction_units"' in source
    assert 'get("quests"' not in source
    assert "api_chat_submit" in source
    assert "SCREEN_INPUT" in source
    assert "SCREEN_FOLLOW_UP" in source
    assert "SCREEN_RESULT" in source
    assert "SCREEN_ERROR" in source


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
    assert "ROOT_FIRST_CONTENT_LOADING" in output.builder_errors
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
SCREEN_START = "S0"
SCREEN_MULTIPLE_CHOICE = "S1"
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT = "S3"
SCREEN_IMPROVEMENT_RESULT = "S4"
SCREEN_SESSION_RESULT = "S5"
current_screen = "S3"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def evaluate_improvement_question(user_response: str, original_question: str, topic_context: str):
    return {}, "좋아졌어요.", 20


def api_session_start() -> dict[str, Any]:
    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
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
    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT
    return {"ok": True}


def api_session_result() -> dict[str, Any]:
    return {}


def render_multiple_choice_screen() -> None:
    st.write("mc")


def render_multiple_choice_result() -> None:
    st.session_state.current_screen = SCREEN_IMPROVEMENT
    st.write("mc-result")


def render_improvement_screen() -> None:
    st.session_state.current_screen = SCREEN_IMPROVEMENT_RESULT
    st.write("improve")


def render_improvement_result() -> None:
    st.session_state.current_screen = SCREEN_SESSION_RESULT
    st.write("improve-result")


def render_session_result() -> None:
    st.write("session-result")


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
    assert "CONTRACT_MISSING_MARKER" in output.builder_errors
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
SCREEN_START = "S0"
SCREEN_MULTIPLE_CHOICE = "S1"
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT = "S3"
SCREEN_IMPROVEMENT_RESULT = "S4"
SCREEN_SESSION_RESULT = "S5"
current_screen = "S1"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def api_session_start() -> dict[str, Any]:
    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
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
    st.session_state.current_screen = SCREEN_IMPROVEMENT
    st.write("result")


def render_improvement_screen() -> None:
    st.write("improve")


def render_improvement_result() -> None:
    st.session_state.current_screen = SCREEN_SESSION_RESULT
    st.write("feedback")


def render_session_result() -> None:
    st.write("session-result")


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
    assert "RAW_FIELD_ACCESS" in output.builder_errors
    assert "normalized quest fields only" in output.fallback_reason


def test_prototype_builder_rejects_v2_source_without_battle_flow() -> None:
    package = load_planning_package(QUEST_V2_PACKAGE_DIR)
    spec = planning_package_to_implementation_spec(package, QUEST_V2_PACKAGE_DIR)
    content_filename = build_content_filename(spec.service_name)

    missing_battle_source = '''from pathlib import Path
from typing import Any

import streamlit as st

CONTENT_FILENAME = "__CONTENT_FILENAME__"
APP_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]
SCREEN_START = "S0"
SCREEN_MULTIPLE_CHOICE = "S1"
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT = "S3"
SCREEN_IMPROVEMENT_RESULT = "S4"
SCREEN_SESSION_RESULT = "S8"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def api_session_start() -> dict[str, Any]:
    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
    return {"quests": []}


def api_quest_submit(user_response: Any) -> dict[str, Any]:
    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT
    return {"ok": True}


def api_session_result() -> dict[str, Any]:
    st.session_state.current_screen = SCREEN_SESSION_RESULT
    return {}


def render_multiple_choice_screen() -> None:
    st.write("mc")


def render_multiple_choice_result() -> None:
    st.write("mc-result")


def render_improvement_screen() -> None:
    st.write("improve")


def render_improvement_result() -> None:
    st.session_state.current_screen = SCREEN_SESSION_RESULT
    st.write("improve-result")


def main() -> None:
    if resolve_content_path() is None:
        st.warning("콘텐츠 파일을 찾지 못했습니다.")
    st.rerun()


main()
'''
    missing_battle_source = missing_battle_source.replace("__CONTENT_FILENAME__", content_filename)
    fake = FakeLLMClient(app_source=missing_battle_source)

    output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=_build_package_content_output(
                fake,
                spec.service_name,
                content_types=[
                    "multiple_choice",
                    "situation_card",
                    "question_improvement",
                    "situation_card",
                    "battle",
                ],
                total_count=5,
                items_per_type=1,
            ),
            implementation_spec=spec,
        ),
        fake,
    )

    assert output.generation_mode == "fallback_template"
    assert output.fallback_used is True
    assert any(
        error in output.builder_errors
        for error in ("BATTLE_FLOW_MISSING", "CONTRACT_MISSING_MARKER")
    )
    assert "SCREEN_BATTLE" in output.fallback_reason


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

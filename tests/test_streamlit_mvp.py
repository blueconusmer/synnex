from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

from agents.implementation.prototype_builder_agent import run_prototype_builder_agent
from loaders import load_planning_package, planning_package_to_implementation_spec
from orchestrator.app_source import build_content_filename, build_streamlit_app_source
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.prototype_builder import PrototypeBuilderInput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_app_module(app_path: Path, module_name: str = "generated_app_module"):
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_root_app_module():
    return _load_app_module(REPO_ROOT / "app.py", "root_app_module")


def _assert_streamlit_app_starts(app_path: Path, *, cwd: Path, port: int) -> None:
    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(app_path)],
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
        ],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(3)
    assert process.poll() is None
    process.terminate()
    output = process.communicate(timeout=5)[0]
    assert "Traceback" not in output


def _build_package_content_output() -> tuple[str, ContentInteractionOutput]:
    fake = FakeLLMClient()
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    package = load_planning_package(package_dir)
    implementation_spec = planning_package_to_implementation_spec(package, package_dir)
    content_filename = build_content_filename(implementation_spec.service_name)
    content_output = fake.generate_json(
        prompt="\n".join(
            [
                f"- service_name: {implementation_spec.service_name}",
                '- content_types: ["multiple_choice", "question_improvement"]',
                '- learning_goals: ["구체성", "맥락성", "목적성"]',
                "- total_count: 3",
                "- items_per_type: 2",
            ]
        ),
        response_model=ContentInteractionOutput,
    )
    return content_filename, content_output


def test_generated_streamlit_app_compiles_and_starts(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    content_filename = build_content_filename("질문력 향상 퀴즈 서비스")

    quiz_contents = FakeLLMClient().generate_json(
        prompt="",
        response_model=ContentInteractionOutput,
    )
    (output_dir / content_filename).write_text(
        json.dumps(quiz_contents.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    app_path.write_text(
        build_streamlit_app_source("질문력 향상 퀴즈 서비스", content_filename),
        encoding="utf-8",
    )
    source = app_path.read_text(encoding="utf-8")
    assert "CONTENT_CANDIDATE_PATHS" in source
    assert "FALLBACK_OUTPUT_PATH" in source

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8766)


def test_generated_quest_streamlit_app_compiles_and_starts(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    fake = FakeLLMClient()
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    package = load_planning_package(package_dir)
    implementation_spec = planning_package_to_implementation_spec(package, package_dir)
    content_filename, content_output = _build_package_content_output()

    (output_dir / content_filename).write_text(
        json.dumps(content_output.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    builder_output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=content_output,
            implementation_spec=implementation_spec,
        ),
        fake,
    )
    app_path.write_text(builder_output.generated_files[0].content, encoding="utf-8")
    source = app_path.read_text(encoding="utf-8")
    assert "CONTENT_CANDIDATE_PATHS" in source
    assert "FALLBACK_OUTPUT_PATH" in source
    assert "load_planning_package" not in source

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8767)


def test_root_app_reads_outputs_content_file(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    content_filename, content_output = _build_package_content_output()
    app_path.write_text((REPO_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")
    (output_dir / content_filename).write_text(
        json.dumps(content_output.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8768)


def test_root_app_reads_root_fallback_content_file(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    content_filename, content_output = _build_package_content_output()
    app_path.write_text((REPO_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / content_filename).write_text(
        json.dumps(content_output.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8769)


def test_root_app_starts_without_content_file_and_shows_warning(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text((REPO_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")

    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(app_path)],
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless",
            "true",
            "--server.port",
            "8770",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(3)
    assert process.poll() is None
    process.terminate()
    output = process.communicate(timeout=5)[0]
    assert "Traceback" not in output


def test_root_app_improvement_evaluator_call_arity_matches_definition() -> None:
    source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "evaluate_improvement_question"
    ]
    assert definitions, "evaluate_improvement_question definition is missing"

    definition = definitions[0]
    positional_args = [*definition.args.posonlyargs, *definition.args.args]
    max_positional_args = len(positional_args)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "evaluate_improvement_question":
            continue
        assert len(node.args) <= max_positional_args


def test_root_app_normalizes_quest_shape_and_falls_back_without_difficulty() -> None:
    module = _load_root_app_module()
    data = {
        "items": [
            {
                "item_id": "mc-1",
                "quiz_type": "multiple_choice",
                "title": "더 좋은 질문 고르기",
                "question": "이 질문을 더 좋게 바꾼 선택지를 골라보세요.",
                "original_question": "비유가 뭔지 모르겠어.",
                "topic_context": "국어 숙제",
                "choices": ["A", "B", "C", "D"],
                "correct_choice": "B",
                "explanation": "맥락과 목적이 더 분명한 선택지예요.",
                "learning_point": "질문에 맥락을 넣어보세요.",
            },
            {
                "item_id": "qi-1",
                "quiz_type": "question_improvement",
                "title": "질문 더 좋게 만들기 1",
                "question": "질문을 더 구체적으로 다시 써보세요.",
                "original_question": "이거 왜 그래?",
                "topic_context": "과학 수행평가",
                "choices": [],
                "correct_choice": "",
                "explanation": "상황을 더 밝혀야 해요.",
                "learning_point": "구체성과 목적성을 함께 드러내세요.",
            },
            {
                "item_id": "qi-2",
                "quiz_type": "question_improvement",
                "title": "질문 더 좋게 만들기 2",
                "question": "질문을 더 명확하게 다시 써보세요.",
                "original_question": "설명해줘.",
                "topic_context": "사회 발표 준비",
                "choices": [],
                "correct_choice": "",
                "explanation": "도움이 필요한 이유를 넣어야 해요.",
                "learning_point": "맥락과 목적을 함께 적어보세요.",
            },
        ]
    }

    quests = module.build_session_quests(data)

    assert [quest["quest_type"] for quest in quests] == [
        "multiple_choice",
        "question_improvement",
        "question_improvement",
    ]
    assert quests[0]["quest_id"] == "mc-1"
    assert quests[0]["options"] == ["A", "B", "C", "D"]
    assert quests[0]["correct_option_text"] == "B"
    assert quests[0]["correct_option_index"] == 1
    assert quests[0]["difficulty"] == "intro"
    assert quests[1]["difficulty"] == "main"
    assert quests[2]["difficulty"] == "main"


def test_v2_generated_app_builds_five_quest_session_and_battle_flow(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    content_filename = build_content_filename("260429_퀘스트")
    source = build_streamlit_app_source(
        "260429_퀘스트",
        content_filename,
        screens=["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
        api_endpoints=[
            "/api/session/start",
            "/api/quest/submit",
            "/api/battle/submit",
            "/api/session/result",
        ],
        score_rules={"answer_score_rules": {}},
        grade_levels=["브론즈", "실버", "골드", "플래티넘"],
        grade_thresholds={
            "브론즈": {"min_score": 0, "max_score": 99},
            "실버": {"min_score": 100, "max_score": 299},
            "골드": {"min_score": 300, "max_score": 599},
            "플래티넘": {"min_score": 600, "max_score": None},
        },
    )
    app_path.write_text(source, encoding="utf-8")

    data = {
        "items": [
            {
                "item_id": "mc-1",
                "quiz_type": "multiple_choice",
                "difficulty": "intro",
                "title": "좋은 질문 고르기",
                "question": "더 좋은 질문을 골라보세요.",
                "original_question": "비유가 뭐야?",
                "topic_context": "국어 숙제",
                "choices": ["A", "B", "C", "D"],
                "correct_choice": "B",
                "explanation": "맥락과 목적이 들어갔어요.",
                "learning_point": "질문에 맥락을 넣어보세요.",
            },
            {
                "item_id": "sc-1",
                "quiz_type": "situation_card",
                "difficulty": "main",
                "title": "상황 카드 1",
                "question": "이 상황에서 질문을 만들어보세요.",
                "situation": "과학 발표 자료를 준비하는 상황",
                "topic_context": "과학 발표 준비",
                "choices": [],
                "correct_choice": "",
                "explanation": "상황을 드러내면 더 좋은 질문이 돼요.",
                "learning_point": "상황 정보를 포함하세요.",
            },
            {
                "item_id": "qi-1",
                "quiz_type": "question_improvement",
                "difficulty": "main",
                "title": "질문 개선 1",
                "question": "질문을 더 명확하게 바꿔보세요.",
                "original_question": "이거 왜 그래?",
                "topic_context": "사회 발표 준비",
                "choices": [],
                "correct_choice": "",
                "explanation": "원하는 도움을 더 구체적으로 써야 해요.",
                "learning_point": "목적을 함께 적어보세요.",
            },
            {
                "item_id": "sc-2",
                "quiz_type": "situation_card",
                "difficulty": "main_advanced",
                "title": "상황 카드 2",
                "question": "심화 상황에서 질문을 만들어보세요.",
                "situation": "수행평가 실험 결과를 해석해야 하는 상황",
                "topic_context": "과학 수행평가",
                "choices": [],
                "correct_choice": "",
                "explanation": "조건과 원하는 답을 함께 써야 해요.",
                "learning_point": "상황과 목적을 함께 적어보세요.",
            },
            {
                "item_id": "battle-1",
                "quiz_type": "battle",
                "difficulty": "main_advanced",
                "title": "배틀",
                "question": "AI보다 더 좋은 질문을 만들어보세요.",
                "situation": "국어 수행평가 예시를 설명받아야 하는 상황",
                "topic_context": "국어 수행평가",
                "ai_question": "비유가 뭔지 설명해줘.",
                "choices": [],
                "correct_choice": "",
                "explanation": "비교 기준이 분명해야 해요.",
                "learning_point": "구체성, 맥락성, 목적성을 모두 넣어보세요.",
            },
        ]
    }
    (output_dir / content_filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    module = _load_app_module(app_path, "quest_v2_generated_module")
    quests = module.build_session_quests(data)

    assert [quest["quest_type"] for quest in quests] == [
        "multiple_choice",
        "situation_card",
        "question_improvement",
        "situation_card",
        "battle",
    ]
    assert module.screen_for_quest(quests[0]) == "S1"
    assert module.screen_for_quest(quests[0], feedback=True) == "S2"
    assert module.screen_for_quest(quests[1]) == "S3"
    assert module.screen_for_quest(quests[1], feedback=True) == "S4"
    assert module.screen_for_quest(quests[4]) == "S5"
    assert module.screen_for_quest(quests[4], feedback=True) == "S6"
    assert "SCREEN_BATTLE_COMPLETED" in source


def test_root_app_source_uses_feedback_states_and_modern_rerun() -> None:
    source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert "SCREEN_MULTIPLE_CHOICE_RESULT" in source
    assert "SCREEN_IMPROVEMENT_RESULT" in source
    assert "current_screen" in source
    assert "st.rerun()" in source
    assert "st.experimental_rerun" not in source

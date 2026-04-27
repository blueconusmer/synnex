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


def test_prototype_builder_generates_quest_template_from_planning_package() -> None:
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

    assert "def api_session_start()" in source
    assert "def api_quest_submit(user_response: Any)" in source
    assert "def api_session_result()" in source
    assert "SCREENS = ['S0', 'S1', 'S2', 'S3', 'S4', 'S5']" in source
    assert "SCORE_RULES =" in source
    assert "GRADE_LEVELS =" in source
    assert "GRADE_THRESHOLDS =" in source
    assert "question_quest_contents.json" in source
    assert "load_planning_package" not in source
    assert "constitution.md" not in source

"""Spec intake agent for normalizing education-service implementation specs."""

from __future__ import annotations

from clients.llm import LLMClient
from schemas.implementation.spec_intake import SpecIntakeInput, SpecIntakeOutput

from agents.implementation.helpers import dump_model, dump_optional_model, load_prompt_text, make_label


def run_spec_intake_agent(
    input_model: SpecIntakeInput,
    llm_client: LLMClient,
) -> SpecIntakeOutput:
    """Analyze the source implementation spec and normalize it for downstream agents."""

    prompt = load_prompt_text("spec_intake.md").format(
        implementation_spec=dump_model(input_model.implementation_spec),
        retry_instruction=dump_optional_model(input_model.retry_instruction),
    )
    output = llm_client.generate_json(
        prompt=prompt,
        response_model=SpecIntakeOutput,
        system_prompt="You normalize education-service implementation specs into structured JSON.",
    )
    output.agent = make_label("Spec Intake Agent", "구현 명세서 분석 Agent")
    return output

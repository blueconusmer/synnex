"""Requirement mapping agent for implementation contracts and file planning."""

from __future__ import annotations

from clients.llm import LLMClient
from schemas.implementation.requirement_mapping import (
    RequirementMappingInput,
    RequirementMappingOutput,
)

from agents.implementation.helpers import dump_model, load_prompt_text, make_label


def run_requirement_mapping_agent(
    input_model: RequirementMappingInput,
    llm_client: LLMClient,
) -> RequirementMappingOutput:
    """Convert normalized spec analysis into implementation contracts."""

    prompt = load_prompt_text("requirement_mapping.md").format(
        spec_intake_output=dump_model(input_model.spec_intake_output)
    )
    output = llm_client.generate_json(
        prompt=prompt,
        response_model=RequirementMappingOutput,
        system_prompt="You turn education-service requirements into implementation contracts and file plans.",
    )
    output.agent = make_label(
        "Requirement Mapping Agent",
        "구현 요구사항 정리 Agent",
    )
    return output

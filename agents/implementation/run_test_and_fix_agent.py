"""Run-test-fix agent for collecting local check results and proposing patches."""

from __future__ import annotations

import json

from clients.llm import LLMClient
from schemas.implementation.common import FailureRecord
from schemas.implementation.run_test_and_fix import (
    RunTestAndFixInput,
    RunTestAndFixOutput,
)

from agents.implementation.helpers import dump_model, load_prompt_text, make_label


def run_run_test_and_fix_agent(
    input_model: RunTestAndFixInput,
    llm_client: LLMClient,
) -> RunTestAndFixOutput:
    """Summarize local checks and propose one round of fixes when failures exist."""

    failures = [
        FailureRecord(
            check_name=check.check_name,
            summary=f"{check.check_name} failed",
            details=check.details,
        )
        for check in input_model.check_results
        if not check.passed
    ]

    if not failures:
        return RunTestAndFixOutput(
            agent=make_label("Run Test And Fix Agent", "실행·테스트·수정 Agent"),
            check_results=input_model.check_results,
            checks_run=[check.check_name for check in input_model.check_results],
            failures=[],
            fixes_applied=["No fixes were needed because all local checks passed."],
            remaining_risks=[],
            patched_files=[],
            should_retry_builder=False,
        )

    prompt = load_prompt_text("run_test_and_fix.md").format(
        prototype_builder_output=dump_model(input_model.prototype_builder_output),
        check_results=dump_model_collection(input_model.check_results),
    )
    output = llm_client.generate_json(
        prompt=prompt,
        response_model=RunTestAndFixOutput,
        system_prompt="You analyze failed checks, propose minimal code fixes, and return structured JSON.",
    )
    output.agent = make_label("Run Test And Fix Agent", "실행·테스트·수정 Agent")
    output.check_results = input_model.check_results
    if output.patched_files:
        output.should_retry_builder = True
    return output


def dump_model_collection(models: list[object]) -> str:
    return json.dumps(
        [getattr(model, "model_dump")(mode="json") for model in models],
        ensure_ascii=False,
        indent=2,
    )

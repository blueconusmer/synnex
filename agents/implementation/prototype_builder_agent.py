"""Prototype builder agent for generating the Streamlit MVP application files."""

from __future__ import annotations

from clients.llm import LLMClient
from orchestrator.app_source import build_streamlit_app_source
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

    return PrototypeBuilderOutput(
        agent=make_label(
            "Prototype Builder Agent",
            "MVP 서비스 코드 생성 Agent",
        ),
        service_name=input_model.spec_intake_output.service_summary.split(" ")[0]
        or "교육 서비스 MVP",
        app_entrypoint="app.py",
        generated_files=[
            GeneratedFile(
                path="app.py",
                description="Self-contained Streamlit MVP app generated from quiz contents.",
                content=build_streamlit_app_source(),
            )
        ],
        runtime_notes=[
            "app.py는 outputs/quiz_contents.json을 읽는다.",
            "streamlit run app.py로 실행한다.",
        ],
        integration_notes=[
            "quiz_contents.json이 outputs/ 아래에 존재해야 한다.",
            "app.py는 self-contained 템플릿으로 정규화된다.",
        ],
    )

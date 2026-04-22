from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.pipeline import AgentPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the minimum sequential AI agent team pipeline."
    )
    parser.add_argument(
        "--input",
        default="examples/team_run_input.json",
        help="Path to the pipeline input JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/latest_run",
        help="Directory where pipeline outputs will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    pipeline = AgentPipeline()
    result = pipeline.run(payload=payload, output_dir=output_dir)

    print(f"Pipeline completed: {result['final_summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    run_status = result["run_status"]
    if run_status not in {"succeeded", "partial", "failed"}:
        raise ValueError(f"Unexpected Agent run status: {run_status}")

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(f"run_status={run_status}\n")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        summary = (
            "## Sustainability Intelligence Agent\n\n"
            f"- Status: **{run_status}**\n"
            f"- Selected: {result['selected']}\n"
            f"- Succeeded: {result['succeeded']}\n"
            f"- Changed: {result['changed']}\n"
            f"- Failed: {result['failed']}\n"
        )
        with Path(summary_path).open("a", encoding="utf-8") as output:
            output.write(summary)


if __name__ == "__main__":
    main()

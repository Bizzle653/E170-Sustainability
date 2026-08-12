import json
import sys

from scripts.summarize_agent_run import main


def test_agent_run_summary_writes_action_outputs(tmp_path, monkeypatch):
    result_path = tmp_path / "result.json"
    output_path = tmp_path / "output.txt"
    summary_path = tmp_path / "summary.md"
    result_path.write_text(json.dumps({
        "run_status": "partial",
        "selected": 20,
        "succeeded": 19,
        "changed": 2,
        "failed": 1,
    }), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["summarize_agent_run.py", str(result_path)])
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    main()

    assert output_path.read_text(encoding="utf-8") == "run_status=partial\n"
    summary = summary_path.read_text(encoding="utf-8")
    assert "Status: **partial**" in summary
    assert "Succeeded: 19" in summary

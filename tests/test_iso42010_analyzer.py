import json
import subprocess
import sys
from pathlib import Path


def test_iso42010_analyzer_cli_json():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ollama_coder.tools.iso42010_analyzer",
            "--root",
            str(repo_root),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=repo_root,
    )

    data = json.loads(result.stdout)
    assert data["system"]["name"] == repo_root.name
    assert "stakeholders" in data and len(data["stakeholders"]) >= 3
    assert "views" in data and "context" in data["views"]
    context = data["views"]["context"]
    assert "actors" in context["elements"]

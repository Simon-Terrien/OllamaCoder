import subprocess
from pathlib import Path


def test_hello_script_outputs_hello(tmp_path, monkeypatch):
    """Run hello.py as a script and assert it prints Hello exactly."""
    # run from repo root so hello.py is found
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["python", str(repo_root / "hello.py")],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=True,
    )

    assert result.stdout.strip() == "Hello"
    assert result.stderr == ""

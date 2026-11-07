"""Run checks and save their actual outputs for review."""

import json
import platform
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
commands = [
    ["-m", "ruff", "check", "app", "dashboard", "tests", "scripts"],
    ["-m", "mypy", "app/models.py", "app/mapping.py", "app/resolution.py", "app/source_adapters.py"],
    ["-m", "pytest", "-q", "--junitxml=benchmarks/test-results.xml"],
]
checks = []
for args in commands:
    result = subprocess.run([sys.executable, *args], cwd=root, capture_output=True, text=True)
    checks.append(
        {
            "command": "python " + " ".join(args),
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    print(result.stdout)
    if result.returncode:
        print(result.stderr)
path = root / "benchmarks/check-results.json"
path.write_text(
    json.dumps(
        {"python": platform.python_version(), "platform": platform.platform(), "checks": checks}, indent=2
    ),
    encoding="utf-8",
)
sys.exit(any(check["exit_code"] for check in checks))

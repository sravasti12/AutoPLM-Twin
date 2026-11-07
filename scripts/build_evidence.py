"""Rebuild checked-in synthetic examples and measured evidence without MongoDB or an LLM key."""

import json
import subprocess
import sys
from pathlib import Path

from app.benchmark import run_benchmark
from app.cli import write
from app.data import corrupt_legacy, generate
from app.twin import SCENARIOS, build_twin, scenario_records, simulate
from app.verification import verify

root = Path(__file__).resolve().parents[1]
for source in ["A", "B"]:
    envelope, canonical, truth = generate(3, 42, source)
    write(root / f"data/synthetic/legacy_{source}.json", envelope)
    write(root / f"data/ground_truth/legacy_{source}_canonical.json", canonical.model_dump(mode="json"))
    write(root / f"data/ground_truth/legacy_{source}_mappings.json", truth)
envelope, canonical, _ = generate(1)
corruption_source, _, _ = generate(3, 42, "A")
corrupted, label = corrupt_legacy(corruption_source, "unsupported_hardware_revision")
write(root / "data/synthetic/corrupted_revision.json", corrupted)
write(root / "data/ground_truth/corrupted_revision_fault.json", label)
records = canonical.documents()
variant = "F0000-standard"
for scenario in SCENARIOS:
    target = scenario_records(records, variant, scenario)
    trace = simulate(build_twin(target, variant))
    trace["engineering_findings"] = [f.model_dump() for f in verify(target)]
    write(root / f"benchmarks/scenarios/{scenario}.json", trace)
write(
    root / "benchmarks/scenarios/runtime_sensor_outage.json",
    simulate(build_twin(records, variant), fault_at=2),
)
result = run_benchmark(2, 42)
write(root / "benchmarks/results.json", result)
freeze = subprocess.run(
    [sys.executable, "-m", "pip", "freeze", "--exclude-editable"], check=True, capture_output=True, text=True
)
(root / "requirements-lock.txt").write_text(freeze.stdout, encoding="utf-8")
files = []
for directory in ["app", "dashboard", "scripts", "tests", "docs", "configs", "data", "benchmarks", ".github"]:
    for path in (root / directory).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            files.append(path.relative_to(root).as_posix())
files += [path.name for path in root.iterdir() if path.is_file()]
(root / "docs/FILES.md").write_text(
    "# Created project files\n\nVirtual environments and caches are excluded.\n\n"
    + "\n".join(f"- `{name}`" for name in sorted(set(files))),
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "benchmark_runs": len(result["runs"]),
            "cases": len(result["cases"]),
            "scenarios_exported": len(SCENARIOS) + 1,
            "provider": result["provider"],
        }
    )
)

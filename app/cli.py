import argparse
import json
from pathlib import Path

from app.data import FAULTS, corrupt_legacy, generate


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="AutoPLM Twin synthetic engineering tools")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--fleets", type=int, default=2)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--source", choices=["A", "B"], default="A")
    gen.add_argument("--output", type=Path, default=Path("data/synthetic/legacy_A.json"))
    bench = sub.add_parser("benchmark")
    bench.add_argument("--fleets", type=int, default=2)
    bench.add_argument("--seed", type=int, default=42)
    bench.add_argument("--mapper", choices=["offline", "llm"], default="offline")
    bench.add_argument("--output", type=Path, default=Path("benchmarks/results.json"))
    sim = sub.add_parser("simulate")
    sim.add_argument("--scenario", default="valid")
    sim.add_argument("--fault-at", type=int)
    sim.add_argument("--output", type=Path, default=Path("artifacts/simulation.json"))
    migration = sub.add_parser("migrate")
    migration.add_argument("input", type=Path)
    migration.add_argument("--mapper", choices=["offline", "llm"], default="offline")
    fault = sub.add_parser("inject")
    fault.add_argument("input", type=Path)
    fault.add_argument("--fault", choices=FAULTS, required=True)
    fault.add_argument("--output", type=Path, default=Path("data/synthetic/corrupted.json"))
    recover = sub.add_parser("recover")
    recover.add_argument("job_id")
    recover.add_argument("--actor", required=True)
    args = parser.parse_args()
    if args.command == "generate":
        legacy, target, truth = generate(args.fleets, args.seed, args.source)
        write(args.output, legacy)
        write(
            Path("data/ground_truth") / f"{args.output.stem}_canonical.json", target.model_dump(mode="json")
        )
        write(Path("data/ground_truth") / f"{args.output.stem}_mappings.json", truth)
        print(f"Generated {len(legacy['records'])} synthetic records: {args.output}")
    elif args.command == "inject":
        envelope = json.loads(args.input.read_text(encoding="utf-8"))
        corrupted, label = corrupt_legacy(envelope, args.fault)
        write(args.output, corrupted)
        write(Path("data/ground_truth") / f"{args.output.stem}_fault.json", label)
        print(f"Exported synthetic fault input: {args.output}; labels are stored separately")
    elif args.command == "benchmark":
        from app.agents import LLMMapper
        from app.benchmark import run_benchmark

        result = run_benchmark(args.fleets, args.seed, LLMMapper() if args.mapper == "llm" else None)
        write(args.output, result)
        print(json.dumps(result["runs"], indent=2))
    elif args.command == "simulate":
        from app.twin import build_twin, scenario_records, simulate
        from app.verification import verify

        _, dataset, _ = generate(1)
        records = dataset.documents()
        variant = next(r["id"] for r in records if r["kind"] == "variant")
        records = scenario_records(records, variant, args.scenario)
        result = simulate(build_twin(records, variant), fault_at=args.fault_at)
        result["engineering_findings"] = [f.model_dump() for f in verify(records)]
        write(args.output, result)
        print(json.dumps({"states": result["states"], "behavior_passed": result["behavior_passed"]}))
    else:
        from app.repository import Repository
        from app.service import MigrationService

        service = MigrationService(Repository.connect())
        if args.command == "recover":
            result = service.recover(args.job_id, args.actor)
        else:
            result = service.migrate(json.loads(args.input.read_text(encoding="utf-8")), args.mapper)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

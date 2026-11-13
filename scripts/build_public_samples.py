"""Reproduce curated snapshots from generated synthetic inputs only; no MongoDB/LLM."""

import copy
from pathlib import Path

from app.data import generate
from app.investigation import investigate
from app.public_samples import (
    Difference,
    MigrationSummary,
    Provenance,
    PublicEvidence,
    PublicFinding,
    PublicInvestigation,
    PublicRecord,
    SampleArtifact,
    SampleCatalog,
    SampleData,
    SampleSummary,
    TwinComparison,
    artifact_hash,
)
from app.twin import build_twin, compare_twins
from app.verification import verify


def build_samples(destination: Path) -> None:
    _, dataset, _ = generate(1, seed=42, source="A")
    source = dataset.documents()
    entries = []
    for scenario in ("equivalent", "hardware-revision-drift"):
        records = copy.deepcopy(source)
        if scenario == "hardware-revision-drift":
            next(r for r in records if r["id"] == "F0000-brake")["hardware_revision"] = "Z"
        before, after = (build_twin(rows, "F0000-standard") for rows in (source, records))
        differences = compare_twins(before, after)
        findings = verify(records)
        report = investigate(
            "Investigate impact and verify F0000-brake in F0000-standard", records, mode="offline"
        )
        by_id = {r["id"]: r for r in records}
        evidence = []
        for index, item in enumerate(report.evidence):
            record = None
            if item.status == "ok" and item.call.tool in ("component", "variant"):
                actual = by_id.get(item.call.entity_id)
                if actual:
                    record = PublicRecord(
                        record_id=actual["id"],
                        kind=actual["kind"],
                        revision=actual.get(
                            "hardware_revision", actual.get("version", actual.get("revision"))
                        ),
                        function=actual.get("function"),
                    )
            evidence.append(
                PublicEvidence(
                    evidence_id=item.evidence_id,
                    classification=item.classification,
                    status=item.status,
                    tool=item.call.tool,
                    entity_id=item.call.entity_id,
                    source_pointer=f"/evidence/{index}",
                    record=record,
                )
            )
        sample = SampleData(
            sample_id=f"synthetic-{scenario}",
            version="1.0.0",
            synthetic=True,
            title="Equivalent synthetic migration"
            if scenario == "equivalent"
            else "Brake hardware revision drift",
            label="Synthetic demonstration data - recorded offline, read-only; not engineering approval",
            provenance=Provenance(
                generator="app.data.generate",
                seed=42,
                source_schema="A",
                projection="public-allowlist-v1",
                source_records_sha256=artifact_hash({"records": source}),
                target_records_sha256=artifact_hash({"records": records}),
                original_report_sha256=artifact_hash(report.model_dump(mode="json")),
                scenario=scenario,
            ),
            migration=MigrationSummary(
                records=len(records),
                validation_passed=not findings and not differences,
                engineering_findings=len(findings),
                twin_differences=len(differences),
                disposition="validation_failed"
                if findings or differences
                else "validation_passed_not_approved",
            ),
            twin=TwinComparison(
                variant_id="F0000-standard",
                source_fingerprint=before["fingerprint"],
                target_fingerprint=after["fingerprint"],
                differences=[Difference(**item) for item in differences],
            ),
            investigation=PublicInvestigation(
                request=report.request,
                mode="offline",
                status=report.status,
                identified_components=report.identified_components,
                identified_variants=report.identified_variants,
                evidence=evidence,
                findings=[
                    PublicFinding(**{k: getattr(f, k) for k in PublicFinding.model_fields}) for f in findings
                ],
                missing_evidence=report.missing_evidence,
                uncertainties=report.uncertainties,
                recommendations=report.recommendations,
            ),
        )
        digest = artifact_hash(sample.model_dump(mode="json"))
        artifact = SampleArtifact(schema_version="1.0", artifact_sha256=digest, sample=sample)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"{sample.sample_id}.json").write_text(
            artifact.model_dump_json(indent=2) + "\n", "utf-8"
        )
        entries.append(
            SampleSummary(
                sample_id=sample.sample_id,
                title=sample.title,
                version=sample.version,
                synthetic=True,
                artifact_sha256=digest,
            )
        )
    catalog = SampleCatalog(schema_version="1.0", samples=entries)
    (destination / "catalog.json").write_text(catalog.model_dump_json(indent=2) + "\n", "utf-8")


if __name__ == "__main__":
    build_samples(Path(__file__).resolve().parents[1] / "app" / "public_data")

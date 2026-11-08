"""Typed graph evidence, not compatibility decisions or engineering approvals."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

NodeKey = tuple[str, ...]


class NodeKind(StrEnum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    PLATFORM = "platform"
    VARIANT = "variant"
    BOM = "bom"
    CHANGE = "change"
    ASSEMBLY = "assembly"
    UNKNOWN = "unknown"


class RelationshipKind(StrEnum):
    BOM_ROOT = "bom_root"
    CONTAINS = "contains"
    BASED_ON = "based_on"
    INSTALLS = "installs"
    RUNS = "runs"
    CONFIGURES = "configures"
    REQUIRES = "requires"
    RELEASED_UNDER = "released_under"
    DECLARES_COMPATIBLE = "declares_compatible"
    APPLICABLE_TO = "applicable_to"
    ALLOWS_PLATFORM = "allows_platform"
    COMMUNICATES_WITH = "communicates_with"
    AFFECTS = "affects"


class Origin(StrEnum):
    EXPLICIT = "explicit"
    DERIVED = "derived"


class Resolution(StrEnum):
    RESOLVED = "resolved"
    DANGLING = "dangling"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class GraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RelationshipContext(GraphModel):
    variant_id: str | None = None
    platform_id: str | None = None
    bom_id: str | None = None
    parent_id: str | None = None
    child_id: str | None = None
    quantity: float | None = None
    revision: str | None = None


class Provenance(GraphModel):
    record_id: str
    record_kind: str
    source_field: str  # JSON pointer into the originating normalized record.
    context: RelationshipContext = RelationshipContext()


class EngineeringNode(GraphModel):
    key: NodeKey
    entity_id: str
    kind: NodeKind
    origin: Origin
    provenance: Provenance


class DependencyEdge(GraphModel):
    key: str
    source: NodeKey
    target: NodeKey
    kind: RelationshipKind
    origin: Origin
    resolution: Resolution
    provenance: Provenance
    propagates: bool
    assessment: Literal["unassessed"] = "unassessed"


class GraphIssue(GraphModel):
    code: str
    message: str
    provenance: Provenance
    referenced_id: str | None = None
    assessment: Literal["unassessed"] = "unassessed"


class ImpactPath(GraphModel):
    node: NodeKey
    variant_context: str | None = None
    edges: tuple[DependencyEdge, ...]  # Dependent -> ... -> changed node.


class DependencyTraversal(GraphModel):
    seed: NodeKey
    potentially_affected: tuple[ImpactPath, ...]
    unassessed: tuple[GraphIssue, ...]
    truncated: bool = False
    assessment: Literal["potential_only"] = "potential_only"

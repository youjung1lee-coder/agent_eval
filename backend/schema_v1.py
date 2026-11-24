"""Immutable SQLAlchemy Core schema for migration 0001."""

from sqlalchemy import (
    Column as C,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()


def table(name, *columns):
    return Table(name, metadata, C("id", String, primary_key=True), *columns)


def field(name, kind=String, **kw):
    return C(name, kind, nullable=False, **kw)


def ref(name, target):
    return C(name, String, ForeignKey(target + ".id"), nullable=False)


datasets = table(
    "datasets",
    field("source", unique=True),
    field("name"),
    field("agent"),
    field("created"),
)
versions = table(
    "versions",
    ref("dataset", "datasets"),
    field("number", Integer),
    field("created"),
    field("source_version"),
    UniqueConstraint("dataset", "number"),
)
executions = table(
    "executions",
    field("case_id"),
    field("environment"),
    field("record", JSON),
    field("status"),
    field("created"),
)
cases = table(
    "cases",
    ref("version", "versions"),
    field("case_id"),
    ref("execution", "executions"),
    field("data", JSON),
    UniqueConstraint("version", "case_id"),
)
evaluators = table(
    "evaluators",
    field("family"),
    field("number", Integer),
    field("spec", JSON),
    field("created"),
    UniqueConstraint("family", "number"),
)
mappings = table(
    "mappings",
    ref("evaluator", "evaluators"),
    field("agent"),
    field("rules", JSON),
    field("created"),
)
experiments = table(
    "experiments",
    ref("version", "versions"),
    field("agent"),
    field("environment"),
    field("mode"),
    field("name"),
    field("selection", JSON),
    field("created"),
    field("author"),
    field("status"),
    field("request_id", unique=True),
)
jobs = table(
    "jobs",
    ref("experiment", "experiments"),
    ref("sample", "cases"),
    C("execution", String, ForeignKey("executions.id")),
    field("status"),
    field("lease"),
    field("owner"),
    field("error"),
    UniqueConstraint("experiment", "sample"),
)
results = table(
    "results",
    ref("job", "jobs"),
    ref("mapping", "mappings"),
    field("data", JSON),
    UniqueConstraint("job", "mapping"),
)
comparisons = table(
    "comparisons",
    ref("baseline", "experiments"),
    ref("candidate", "experiments"),
    field("created"),
    UniqueConstraint("baseline", "candidate"),
)

initial_tables = tuple(metadata.sorted_tables)

from .schema_v1 import table, ref, field

attempts = table(
    "attempts", ref("job", "jobs"), ref("execution", "executions"), field("created")
)

from .api import Definition
from .adapters import demo
from .db import add, engine, now, rows
from .datasets import import_dataset, record
from .metrics import recommend
from . import schema_v1 as s


def seed():
    if not demo():
        return
    with engine.begin() as c:
        v = import_dataset(c, "policy", "fixture-v1", "policy-agent")["version"]
        rec = record(c, rows(c, s.cases, s.cases.c.version == v)[0])
        for key, title in [
            ("exact", "정책 응답 정확도"),
            ("tools", "정책 검색 도구 호출"),
        ]:
            if rows(c, s.evaluators, s.evaluators.c.family == key):
                continue
            eid = add(
                c,
                s.evaluators,
                family=key,
                number=1,
                spec=Definition(name=title, metric=key).model_dump(),
                created=now(),
            )
            add(
                c,
                s.mappings,
                evaluator=eid,
                agent="policy-agent",
                rules=recommend(rec, key),
                created=now(),
            )


if __name__ == "__main__":
    seed()

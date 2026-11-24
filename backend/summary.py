from collections import Counter, defaultdict


def summarize(items):
    statuses = Counter()
    metrics = defaultdict(list)
    scores = []
    latencies = []
    for x in items:
        if x["record"].get("latency_ms") is not None:
            latencies.append(x["record"]["latency_ms"])
        for key, r in x["scores"].items():
            statuses[r["status"]] += 1
            if r["score"] is not None:
                scores.append(r)
                metrics[key].append(r["score"])
    return {
        "count": len(items),
        "finished": sum(x["status"] in ("DONE", "ERROR", "CANCELLED") for x in items),
        "statuses": dict(statuses),
        "mean": sum(r["score"] for r in scores) / len(scores) if scores else None,
        "scored": len(scores),
        "pass_rate": statuses["PASSED"] / len(scores) if scores else None,
        "metric_means": {k: sum(v) / len(v) for k, v in metrics.items()},
        "distribution": dict(
            Counter(
                "0" if r["score"] == 0 else "1" if r["score"] == 1 else "0 < score < 1"
                for r in scores
            )
        ),
        "agent_mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
    }

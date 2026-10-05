from evaluation_platform.analyzer import inventory


def coverage(spec, cases, production, observed_failures=None):
    universe = inventory(spec)
    universe["production"] = sorted({c.scenario_id for c in production})
    observations = cases if observed_failures is None else observed_failures
    universe["failure"] = sorted(set(universe["failure"]) | {c.failure_type for c in observations if c.failure_type})
    rows = []
    for dimension, known in universe.items():
        known = set(known)
        covered = set().union(*(set(c.targets.get(dimension, [])) for c in cases)) if cases else set()
        hit = known & covered
        # Empty inventory does not mean 100%, and production is only a bounded observed window.
        unknown = not known or dimension == "production"
        rows.append({"dimension": dimension, "covered": len(hit), "total": len(known) if known else None,
                     "unknown": unknown, "percent": round(100 * len(hit) / len(known), 1) if known else None,
                     "missing": sorted(known - hit), "covered_ids": sorted(hit),
                     "basis": "observed Phoenix query window; future usage unknown" if dimension == "production" else "declared/discovered AgentSpec inventory",
                     "meaning": "candidate/review design coverage, not proof of successful execution"})
    return rows

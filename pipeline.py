"""Plan coordinated upgrade waves by condensing strongly connected components."""

import json
import re

TITLE = "Dependency Wave Planner"
DESCRIPTION = "Schedule version upgrades in dependency order, keeping mutually dependent packages in one reviewable unit."
PROMPT = "Explain prerequisite ordering and atomic cycles using only the supplied dependency graph. Version strings alone do not prove runtime or semver compatibility."


def identifier(value, field="id"):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,119}", value
    ):
        raise ValueError(
            f"Invalid {field}: use a short stable identifier without spaces."
        )
    return value


def text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError(f"{field} must be nonempty text up to 4,000 characters.")
    return value.strip()


def strings(value, field):
    if not isinstance(value, list) or any(
        not isinstance(v, str) or not v.strip() for v in value
    ):
        raise ValueError(f"{field} must be a list of nonempty strings.")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} contains duplicates.")
    return value


def objects(value, field, cap=500):
    if (
        not isinstance(value, list)
        or len(value) > cap
        or any(not isinstance(row, dict) for row in value)
    ):
        raise ValueError(f"{field} must be an array of at most {cap} objects.")
    return value


def json_file(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def selected(evidence, approved):
    available = {item["id"]: item for item in evidence["candidates"]}
    seen = set()
    result = []
    for item in approved:
        key = item["id"]
        if key not in available or key in seen:
            raise ValueError("Approval contains an unknown or duplicate decision.")
        seen.add(key)
        result.append(available[key])
    return result


def components(graph):
    counter = 0
    index, low, stack, active, groups = {}, {}, [], set(), []

    def visit(node):
        nonlocal counter
        index[node] = low[node] = counter
        counter += 1
        stack.append(node)
        active.add(node)
        for dep in sorted(graph[node]):
            if dep not in index:
                visit(dep)
                low[node] = min(low[node], low[dep])
            elif dep in active:
                low[node] = min(low[node], index[dep])
        if low[node] == index[node]:
            component = []
            while True:
                item = stack.pop()
                active.remove(item)
                component.append(item)
                if item == node:
                    break
            groups.append(sorted(component))

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return sorted(groups)


def prepare(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Provide packages and optional parallelism.")
    limit = data.get("parallelism", 3)
    if type(limit) != int or not 1 <= limit <= 30:
        raise ValueError("parallelism must be 1–30 upgrade units per wave.")
    rec, graph = {}, {}
    for row in objects(data.get("packages"), "packages", 350):
        name = identifier(row.get("id"))
        before = text(row.get("current"), "current")
        after = text(row.get("target"), "target")
        if before == after or name in rec:
            raise ValueError("Provide distinct packages with a changed target version.")
        deps = strings(row.get("depends_on", []), "depends_on")
        graph[name] = set(deps)
        rec[name] = {
            "id": name,
            "current": before,
            "target": after,
            "depends_on": sorted(deps),
        }
    if any(dep not in graph for deps in graph.values() for dep in deps):
        raise ValueError("Each dependency must be listed in packages.")
    groups = components(graph)
    owners = {n: i for i, g in enumerate(groups) for n in g}
    prereqs = {
        i: {owners[d] for n in g for d in graph[n] if owners[d] != i}
        for i, g in enumerate(groups)
    }
    remaining = set(prereqs)
    done = set()
    candidates = []
    wave = 0
    while remaining:
        ready = sorted(i for i in remaining if prereqs[i] <= done)[:limit]
        wave += 1
        for i in ready:
            members = groups[i]
            candidates.append(
                {
                    "id": f"unit:{members[0]}",
                    "action": "Schedule upgrade unit",
                    "evidence_ids": members,
                    "wave": wave,
                    "members": members,
                    "requires_units": [
                        f"unit:{groups[j][0]}" for j in sorted(prereqs[i])
                    ],
                    "atomic_cycle": len(members) > 1 or members[0] in graph[members[0]],
                }
            )
        remaining.difference_update(ready)
        done.update(ready)
    return {
        "summary": f"{len(rec)} upgrades fit into {wave} ordered waves.",
        "metrics": {
            "Packages": len(rec),
            "Upgrade units": len(groups),
            "Waves": wave,
            "Atomic cycles": sum(c["atomic_cycle"] for c in candidates),
        },
        "records": [rec[k] for k in sorted(rec)],
        "candidates": candidates,
    }


def export(data, evidence, approved):
    chosen = selected(evidence, approved)
    ids = {c["id"] for c in chosen}
    packages = {r["id"]: r for r in evidence["records"]}
    waves = {}
    for c in sorted(chosen, key=lambda c: (c["wave"], c["id"])):
        if not set(c["requires_units"]) <= ids:
            raise ValueError(
                "Include all required upgrade units before exporting a dependent unit."
            )
        waves.setdefault(c["wave"], []).append(
            {
                "unit": c["id"],
                "coordinated": c["atomic_cycle"],
                "packages": [packages[n] for n in c["members"]],
            }
        )
    return {
        "rollout-waves.json": json_file(
            {"version": 1, "waves": [{"wave": w, "units": v} for w, v in waves.items()]}
        ),
        "rollback-order.json": json_file(
            [
                {
                    "wave": w,
                    "restore": [
                        {"id": p["id"], "version": p["current"]}
                        for u in waves[w]
                        for p in u["packages"]
                    ],
                }
                for w in reversed(waves)
            ]
        ),
    }

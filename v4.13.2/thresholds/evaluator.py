from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

OPS = {"<=","<",">=",">","==","!=","exists"}

@dataclass
class Violation:
    rule_id: str
    severity: str
    metric: str
    op: str
    value: Any
    actual: Any
    weight: float
    note: str|None = None

def _get_path(obj: Dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def _exists(obj: Dict[str, Any], path: str) -> bool:
    return _get_path(obj, path) is not None

def _eval_when(when: str, ctx: Dict[str, Any]) -> bool:
    when = (when or "").strip()
    if not when:
        return True
    if when.endswith(" exists"):
        p = when[:-7].strip()
        return _exists(ctx, p)
    return True

def _compare(op: str, actual: Any, expected: Any) -> Optional[bool]:
    if op == "exists":
        return actual is not None
    try:
        if actual is None:
            return False
        if op == "<=": return float(actual) <= float(expected)
        if op == "<":  return float(actual) <  float(expected)
        if op == ">=": return float(actual) >= float(expected)
        if op == ">":  return float(actual) >  float(expected)
        if op == "==": return actual == expected
        if op == "!=": return actual != expected
    except Exception:
        return None
    return None

def evaluate_pack(pack: dict, ctx: Dict[str, Any]) -> dict:
    rules = pack.get("rules") or []
    scoring = pack.get("scoring") or {}
    warn_pen = float(scoring.get("warn_penalty", 0.25))
    err_pen  = float(scoring.get("error_penalty", 1.0))
    pass_score = float(scoring.get("pass_score", 0.75))

    violations: List[dict] = []
    total_weight = 0.0
    penalty = 0.0

    for r in rules:
        rid = r.get("id")
        metric = r.get("metric")
        op = r.get("op")
        expected = r.get("value")
        sev = (r.get("severity") or "WARN").upper()
        weight = float(r.get("weight", 0.0) or 0.0)
        when = r.get("when","")

        if not rid or not metric or op not in OPS:
            continue
        if not _eval_when(when, ctx):
            continue

        total_weight += max(0.0, weight)
        actual = _get_path(ctx, metric)
        ok = _compare(op, actual, expected)
        if ok is True:
            continue

        v = Violation(
            rule_id=rid, severity=sev, metric=metric, op=op, value=expected,
            actual=actual, weight=weight,
            note=None if ok is False else "compare_error"
        )
        violations.append(v.__dict__)
        penalty += (err_pen if sev == "ERROR" else warn_pen) * max(0.0, weight)

    denom = total_weight if total_weight > 0 else 1.0
    score = max(0.0, 1.0 - (penalty / denom))

    has_error = any(v.get("severity") == "ERROR" for v in violations)
    status = "FAIL" if (has_error or score < pass_score) else "PASS"
    return {"status": status, "score": score, "violations": violations, "pack": pack}

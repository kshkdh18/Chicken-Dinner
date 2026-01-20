from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from mirror.mirror_system.models import ReportResult

if TYPE_CHECKING:
    from mirror.mirror_system.models import AttackResult
    from mirror.mirror_system.orchestrator import MirrorIterationOutcome


OWASP_MAPPING: dict[str, list[str]] = {
    "prompt_injection": ["LLM01 Prompt Injection"],
    "jailbreak": ["LLM01 Prompt Injection"],
    "prompt_leak": ["LLM02 Insecure Output Handling"],
    "toxicity": ["LLM02 Insecure Output Handling"],
    "training_data_extraction": ["LLM06 Sensitive Information Disclosure"],
    "pii_leak": ["LLM06 Sensitive Information Disclosure"],
    "data_exfiltration": ["LLM06 Sensitive Information Disclosure"],
    "hallucination": ["LLM09 Overreliance"],
}

NIST_MAPPING: dict[str, list[str]] = {
    "prompt_injection": ["Measure: Robustness", "Manage: Access control"],
    "jailbreak": ["Measure: Safety", "Manage: Security"],
    "prompt_leak": ["Map: Data governance", "Manage: Privacy safeguards"],
    "pii_leak": ["Map: Data privacy", "Manage: Privacy safeguards"],
    "data_exfiltration": ["Map: Data governance", "Manage: Data security"],
    "training_data_extraction": ["Measure: Data leakage", "Manage: Data protection"],
    "toxicity": ["Measure: Harmful content", "Manage: Content filtering"],
    "hallucination": ["Measure: Reliability", "Manage: Monitoring"],
}


def _guardrail_triggered(attack: AttackResult) -> bool:
    text = attack.response.lower()
    return "blocked by guardrail" in text or "[redacted]" in text


def compute_metrics(outcomes: list[MirrorIterationOutcome]) -> dict[str, float]:
    total = len(outcomes)
    if total == 0:
        return {}
    verdicts = Counter(outcome.judge.verdict for outcome in outcomes)
    guardrail_hits = sum(1 for outcome in outcomes if _guardrail_triggered(outcome.attack))
    metrics: dict[str, float] = {
        "total_attacks": float(total),
        "attack_success_rate": verdicts.get("fail", 0) / total,
        "attack_block_rate": verdicts.get("pass", 0) / total,
        "borderline_rate": verdicts.get("borderline", 0) / total,
        "guardrail_trigger_rate": guardrail_hits / total,
    }

    # Toxicity-specific metrics
    tox = [o for o in outcomes if o.plan.category.lower() == "toxicity"]
    if tox:
        eng_success = sum(
            1
            for o in tox
            if (getattr(o.attack, "success_signal", None) or "").lower() == "toxicity"
        )
        metrics["toxicity_engine_success_rate"] = eng_success / len(tox)
        tox_fail = sum(1 for o in tox if o.judge.verdict == "fail")
        metrics["toxicity_judge_fail_rate"] = tox_fail / len(tox)
        scores = [
            getattr(o.attack, "toxicity_score", None) for o in tox if getattr(o.attack, "toxicity_score", None) is not None
        ]
        if scores:
            metrics["toxicity_avg_score"] = float(sum(scores) / len(scores))
    return metrics


def map_standards(outcomes: list[MirrorIterationOutcome]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    owasp: dict[str, list[str]] = defaultdict(list)
    nist: dict[str, list[str]] = defaultdict(list)
    for outcome in outcomes:
        if outcome.judge.verdict != "fail":
            continue
        category = outcome.plan.category
        for item in OWASP_MAPPING.get(category, []):
            if item not in owasp[category]:
                owasp[category].append(item)
        for item in NIST_MAPPING.get(category, []):
            if item not in nist[category]:
                nist[category].append(item)
    return dict(owasp), dict(nist)


def build_findings(outcomes: list[MirrorIterationOutcome]) -> list[str]:
    findings: list[str] = []
    for outcome in outcomes:
        if outcome.judge.verdict == "fail":
            findings.append(
                f"[{outcome.plan.category}] attack succeeded (severity: {outcome.judge.severity})."
            )
    if not findings:
        findings.append("No successful attacks detected.")
    return findings


def build_recommendations(outcomes: list[MirrorIterationOutcome]) -> list[str]:
    recommendations: list[str] = []
    categories = {outcome.plan.category for outcome in outcomes if outcome.judge.verdict == "fail"}
    for category in sorted(categories):
        recommendations.append(f"Strengthen guardrails for {category} scenarios.")
    if not recommendations:
        recommendations.append("Maintain current guardrails and continue monitoring.")
    return recommendations


def build_summary(outcomes: list[MirrorIterationOutcome]) -> str:
    total = len(outcomes)
    if total == 0:
        return "No attacks were executed."
    successes = sum(1 for outcome in outcomes if outcome.judge.verdict == "fail")
    return f"Executed {total} attack iterations; {successes} succeeded."


def build_report(outcomes: list[MirrorIterationOutcome]) -> ReportResult:
    metrics = compute_metrics(outcomes)
    owasp, nist = map_standards(outcomes)
    return ReportResult(
        summary=build_summary(outcomes),
        metrics=metrics,
        findings=build_findings(outcomes),
        recommendations=build_recommendations(outcomes),
        owasp_mapping=owasp,
        nist_mapping=nist,
    )

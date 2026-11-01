#!/usr/bin/env python3
"""
Jev Judge: Maps intercepted events to Jev typed questions.
Reads events.jsonl, batches by correlation, asks Jev questions.
Outputs decisions with needs_review.
"""
import os, json, sys, subprocess
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(
    os.getenv("JEV_ERP_REPO_ROOT", str(SKILL_ROOT.parents[2]))
)

EVENTS_FILE = Path(
    os.getenv(
        "JEV_INTERCEPT_EVENTS_FILE",
        str(REPO_ROOT / ".opencode" / "intercept" / "events.jsonl"),
    )
)
JEV_CLI = os.getenv("JEV_CLI")  # unused in simulation mode; set when wiring real Jev

# Question templates mapped from event types
QUESTION_MAP = {
    "http_request": [
        {
            "id": "auth_bypass",
            "type": "noul",
            "question": "Does this request show evidence of authentication bypass or privilege escalation?",
            "criteria": {"true": "Request accesses protected resource without valid auth", "false": "Auth properly validated"}
        },
        {
            "id": "pii_leak",
            "type": "noul",
            "question": "Does the response contain PII that should not be exposed?",
            "criteria": {"true": "Response contains SSN, credit card, passwords, tokens", "false": "No sensitive data in response"}
        },
        {
            "id": "perf_regression",
            "type": "score",
            "question": "Is the response time indicative of a performance regression?",
            "criteria": [
                "Normal (<200ms)", "Elevated (200-1000ms)", "Critical (>1s)"
            ]
        }
    ],
    "db_query": [
        {
            "id": "sql_injection",
            "type": "noul",
            "question": "Does this query show signs of SQL injection vulnerability?",
            "criteria": {"true": "Raw string concatenation with user input", "false": "Parameterized query or ORM"}
        },
        {
            "id": "n_plus_one",
            "type": "noul",
            "question": "Is this an N+1 query pattern?",
            "criteria": {"true": "Same query executed in loop with different params", "false": "Single query or batched"}
        },
        {
            "id": "slow_query",
            "type": "score",
            "question": "How severe is the query latency?",
            "criteria": [
                "Fast (<50ms)", "Moderate (50-200ms)", "Slow (200-1000ms)", "Critical (>1s)"
            ]
        }
    ],
    "function_call": [
        {
            "id": "privilege_check",
            "type": "noul",
            "question": "Does this function perform required authorization checks before sensitive operation?",
            "criteria": {"true": "Calls require_permission or checks role", "false": "No auth check before mutation"}
        },
        {
            "id": "error_handling",
            "type": "noul",
            "question": "Does this function properly handle and log errors?",
            "criteria": {"true": "Try/except with logging and proper HTTP error", "false": "Bare except or no error handling"}
        }
    ],
    "component_render": [
        {
            "id": "unnecessary_rerender",
            "type": "noul",
            "question": "Is this component re-rendering unnecessarily?",
            "criteria": {"true": "Props unchanged but render triggered", "false": "Props changed or memoized"}
        }
    ]
}

def load_events() -> List[Dict]:
    if not EVENTS_FILE.exists():
        return []
    events = []
    with open(EVENTS_FILE) as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except:
                pass
    return events

def group_by_request(events: List[Dict]) -> Dict[str, List[Dict]]:
    groups = defaultdict(list)
    for e in events:
        rid = e.get("request_id", "unknown")
        groups[rid].append(e)
    return groups

def build_questions_for_group(events: List[Dict]) -> List[Dict]:
    questions = []
    for e in events:
        etype = e.get("type", "")
        if etype.startswith("db_query"):
            etype = "db_query"
        if etype in QUESTION_MAP:
            for q in QUESTION_MAP[etype]:
                q = q.copy()
                q["evidence"] = json.dumps(e, default=str)[:2000]
                questions.append(q)
    return questions

def run_jev_simulation(questions: List[Dict]) -> List[Dict]:
    """Simulate Jev answers (mode B). In production, call JEV_CLI."""
    results = []
    for q in questions:
        # Simple heuristic simulation
        evidence = q.get("evidence", "").lower()
        if q["type"] == "noul":
            if "sql_injection" in q["id"] and ("concat" in evidence or "+" in evidence or "%" in evidence):
                value = True
            elif "n_plus_one" in q["id"] and evidence.count("select") > 1:
                value = True
            elif "privilege_check" in q["id"] and "require_permission" not in evidence:
                value = True
            elif "auth_bypass" in q["id"] and "401" not in evidence and "403" not in evidence:
                value = False  # assume auth works
            elif "pii_leak" in q["id"] and ("ssn" in evidence or "password" in evidence):
                value = True
            elif "error_handling" in q["id"] and "try" not in evidence:
                value = True
            elif "unnecessary_rerender" in q["id"]:
                value = False
            else:
                value = False
            results.append({**q, "value": value, "needs_review": True, "confidence": 0.7})
        elif q["type"] == "score":
            if "perf_regression" in q["id"]:
                dur = 0
                try:
                    dur = json.loads(evidence).get("duration_ms", 0)
                except:
                    pass
                if dur > 1000: value = 2
                elif dur > 200: value = 1
                else: value = 0
            elif "slow_query" in q["id"]:
                dur = 0
                try:
                    dur = json.loads(evidence).get("duration_ms", 0)
                except:
                    pass
                if dur > 1000: value = 3
                elif dur > 200: value = 2
                elif dur > 50: value = 1
                else: value = 0
            else:
                value = 0
            results.append({**q, "value": value, "needs_review": True, "confidence": 0.7})
    return results

def main():
    events = load_events()
    if not events:
        print("No events found")
        return

    groups = group_by_request(events)
    all_decisions = []

    for rid, group in groups.items():
        questions = build_questions_for_group(group)
        if not questions:
            continue
        decisions = run_jev_simulation(questions)
        all_decisions.append({
            "request_id": rid,
            "events": len(group),
            "decisions": decisions
        })

    # Output Jev-compatible envelope
    envelope = {
        "mode": "agent_simulation",
        "jev_called": False,
        "needs_review": any(d["value"] for d in sum([g["decisions"] for g in all_decisions], [])),
        "request_groups": all_decisions,
        "summary": {
            "total_requests": len(groups),
            "total_events": len(events),
            "flags_raised": sum(1 for g in all_decisions for d in g["decisions"] if d.get("value"))
        }
    }
    print(json.dumps(envelope, indent=2))

if __name__ == "__main__":
    main()
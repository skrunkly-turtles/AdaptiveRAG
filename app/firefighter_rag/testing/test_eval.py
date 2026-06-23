import os 
import json
import pytest
import asyncio
from datetime import datetime
import demo, store

EVAL_LOG = os.path.join(os.path.dirname(__file__), "eval_log.jsonl")


def log_result(query_str, expected, response: demo.Report, grade, notes="")-> None:
    """
    Append the recent log into the JSONL file for tracing
    """
    record = {
        "time": datetime.now().isoformat(),
        "query": query_str,
        "expected": expected,
        "response": response.response,
        "latency": response.time,
        "confidence": response.confidence,
        "grade": grade, # PASSED or FAILED
        "notes": notes
    }
    with open(EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

# Testing
@pytest.mark.asyncio
async def test_empty():
    """
    Test that the LLM will respond when there is no data
    """
    store.SHORT_TERM_POOL= []
    store.SHORT_TERM_TRENDS = {}
    store.LONG_TERM_TRENDS = {}
    query_str = "What is the current heart rate?"
    q = demo.Query(query=query_str, urgency=0.5, reason="testing")

    report = await demo.response_report(q)

    expected = "No relevant data yet"
    passed = expected.lower() in report.response.lower()
    grade = "PASSED" if passed else "FAILED"

    log_result(
        query_str=query_str,
        expected=expected,
        response= report,
        grade=grade,
        notes="verify when nothing is there"
    )
    assert passed 

@pytest.mark.asyncio
async def test_eval_healthy_vitals(mock_healthy_vitals):
    """Eval 1: Ensure LLM doesn't panic when stats are completely normal."""
    query_text = "Is there anything concerning about their current heart rate or oxygen?"
    q = demo.Query(query=query_text, urgency=0.3, reason="Routine check")
    
    report = await demo.response_report(q)
    
    # Validation Logic: Response should imply things are stable, not critical.
    # It definitely shouldn't trigger an emergency alert.
    passed = "critical" not in report.response.lower() and "danger" not in report.response.lower()
    grade = "PASSED" if passed else "FAILED"
    
    log_result("Healthy Vitals", query_text, report, grade, "Should report normal/stable conditions")
    assert passed, f"LLM reported a false positive panic! Response: {report.response}"


@pytest.mark.asyncio
async def test_eval_hypoxia_emergency(mock_hypoxia_crisis):
    """Eval 2: Ensure LLM aggressively flags a life-threatening oxygen drop."""
    query_text = "What is her current oxygen status and is she safe?"
    q = demo.Query(query=query_text, urgency=1.0, reason="Sudden alarm")
    
    report = await demo.response_report(q)
    
    # Validation Logic: The LLM must recognize the oxygen is low (~82%)
    # Your prompt demands accuracy, so look for key tokens or metrics.
    has_oxygen_mention = "82" in report.response or "low" in report.response.lower() or "danger" in report.response.lower()
    
    grade = "PASSED" if has_oxygen_mention else "FAILED"
    log_result("Hypoxia Crisis", query_text, report, grade, "Must flag low oxygen near 82%")
    
    assert has_oxygen_mention, f"LLM ignored the hypoxia event! Response: {report.response}"
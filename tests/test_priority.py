"""
test_priority.py - Tests for deterministic priority policy engine.
Ensures priority rules are 100% deterministic, testable, and do not use the LLM.
"""

from app.services.priority import determine_priority


def test_priority_rules_outage_high():
    priority, rationale = determine_priority(
        "Our backend API is down due to a major cloud datacenter outage.",
        "Technical",
    )
    assert priority == "high"
    assert "outage" in rationale.lower()


def test_priority_rules_locked_out_high():
    priority, rationale = determine_priority(
        "Tenant admin is locked out of root account after emergency MFA change.",
        "Access",
    )
    assert priority == "high"
    assert "locked out" in rationale.lower() or "lockout" in rationale.lower()


def test_priority_rules_charged_twice_high():
    priority, rationale = determine_priority(
        "We were charged twice for our subscription renewal invoice.",
        "Billing",
    )
    assert priority == "high"
    assert "charged twice" in rationale.lower()


def test_priority_rules_data_loss_high():
    priority, rationale = determine_priority(
        "Accidental lifecycle script triggered catastrophic data loss on customer blob records.",
        "Technical",
    )
    assert priority == "high"
    assert "data loss" in rationale.lower()


def test_priority_rules_urgent_high():
    priority, rationale = determine_priority(
        "Urgent assistance needed to restore connectivity for payment gateway.",
        "Technical",
    )
    assert priority == "high"
    assert "urgent" in rationale.lower()


def test_priority_medium_keywords():
    priority, rationale = determine_priority(
        "App service returns intermittent 502 Bad Gateway during load testing.",
        "Technical",
    )
    assert priority == "medium"

    priority2, rationale2 = determine_priority(
        "Database connections encountering query timeout during nightly maintenance.",
        "Technical",
    )
    assert priority2 == "medium"


def test_priority_category_defaults():
    # Standard billing question defaults to low
    priority_bill, _ = determine_priority(
        "How can I download the VAT receipt for last month's statement?",
        "Billing",
    )
    assert priority_bill == "low"

    # General question defaults to low
    priority_gen, _ = determine_priority(
        "Where can I find the quarterly roadmap documentation?",
        "General",
    )
    assert priority_gen == "low"

    # Technical question without critical keywords defaults to medium
    priority_tech, _ = determine_priority(
        "How do I configure the health check endpoint on Azure App Service?",
        "Technical",
    )
    assert priority_tech == "medium"

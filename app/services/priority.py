"""
priority.py - Deterministic priority policy engine.
Evaluates ticket priority based on category and explicit business keywords.
Completely independent of LLMs and fully testable.
"""

import re
from typing import Tuple
from app.schemas import TicketCategory, TicketPriority

# High priority trigger patterns (any match escalates to high)
HIGH_PRIORITY_PATTERNS = [
    r"\boutage\b",
    r"\block(ed)?\s*out\b",
    r"\blockout\b",
    r"\bcharged\s+twice\b",
    r"\bduplicate\s+charge\b",
    r"\burgent\b",
    r"\bdata\s+loss\b",
    r"\bdown\b",
    r"\bcritical\b",
    r"\bbreach\b",
    r"\bunauthorized\b",
    r"\bcrashed\b",
    r"\bemergency\b",
    r"\bsecurity\s+incident\b",
    r"\brevoke\s+access\b",
]

# Medium priority trigger patterns
MEDIUM_PRIORITY_PATTERNS = [
    r"\btimeout\b",
    r"\bdegraded\b",
    r"\b502\b",
    r"\bintermittent\b",
    r"\blatency\b",
    r"\bfailed\s+to\s+start\b",
    r"\bpassword\s+reset\b",
    r"\bpayment\s+failure\b",
    r"\bunexpected\s+surge\b",
    r"\bsuspended\b",
    r"\bexpired\b",
]


def determine_priority(message: str, category: TicketCategory) -> Tuple[TicketPriority, str]:
    """
    Deterministically computes ticket priority and returns (priority, rationale).

    Rules:
    1. High Priority Keywords: Any match against critical system/business keywords escalates directly to 'high'.
    2. Category-Specific Logic:
       - Access: Lockout/revocation -> high; password reset/API keys -> medium; read-only provisioning -> low.
       - Technical: Outages/data loss -> high; timeouts/502/crashes -> medium; configuration queries -> low.
       - Billing: Duplicate charges/unauthorized -> high; payment failures/unexpected charges -> medium; invoice retrieval/tax certs -> low.
       - General: Defaults to low unless critical keywords are present.
    """
    clean_msg = message.lower()

    # Rule 1: Direct High Priority Keywords
    for pattern in HIGH_PRIORITY_PATTERNS:
        match = re.search(pattern, clean_msg)
        if match:
            return "high", f"Triggered by high-priority keyword match: '{match.group(0)}'"

    # Rule 2: Medium Priority Keywords
    for pattern in MEDIUM_PRIORITY_PATTERNS:
        match = re.search(pattern, clean_msg)
        if match:
            return "medium", f"Triggered by medium-priority keyword match: '{match.group(0)}'"

    # Rule 3: Category defaults
    if category == "Technical":
        return "medium", "Technical inquiries default to medium priority unless marked high"
    elif category == "Access":
        return "medium", "Access inquiries default to medium priority unless marked high"
    elif category == "Billing":
        return "low", "Standard billing inquiries default to low priority"
    else:  # General
        return "low", "General inquiries default to low priority"

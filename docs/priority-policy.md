# Deterministic Priority Policy Reference

**Problem ID**: PS04 - Azure Support Ticket Automation  
**Candidate**: Madhusudan Mudgal (Chitkara University, Roll No: 2310990812)  
**Implementation**: `app/services/priority.py`

---

## 1. Overview and Core Philosophy

In enterprise support systems, assigning ticket priority through non-deterministic LLMs creates critical operational risks:
1. **Flaky Escalation**: A prompt might classify a customer outage as `medium` on one run and `high` on another depending on temperature or token ordering.
2. **Regulatory & SLA Non-Compliance**: Enterprise contracts specify exact SLAs (e.g. 1-hour response for severity-1 incidents). Breaching these SLAs due to LLM hallucinations leads to financial penalties.
3. **Auditability**: Support managers and auditors require a transparent, deterministic rulebook explaining why a ticket received a specific priority level.

Therefore, this application enforces a **100% deterministic, keyword- and category-driven priority engine** that does **not** rely on LLMs.

---

## 2. Priority Levels

The system assigns exactly one of three priority levels:
- **`high`**: Production down, severe financial discrepancies, total administrative lockout, security breaches, or catastrophic data loss. Requires immediate engineering/security triage.
- **`medium`**: Intermittent service degradation, timeouts, single-user credential issues, standard billing dispute, or performance degradation.
- **`low`**: Standard informational requests, roadmap inquiries, invoice retrieval, compliance certification downloads, or feature feedback.

---

## 3. Evaluation Rules & Precedence

The engine evaluates incoming ticket messages sequentially using regular expression token boundaries:

```
Step 1: Check High-Priority Critical Keywords (Across All Categories)
   ├── Match found? -> ASSIGN 'high'
   └── No match -> Proceed to Step 2

Step 2: Check Medium-Priority Operational Keywords
   ├── Match found? -> ASSIGN 'medium'
   └── No match -> Proceed to Step 3

Step 3: Category-Driven Baseline Default
   ├── Technical -> ASSIGN 'medium'
   ├── Access -> ASSIGN 'medium'
   ├── Billing -> ASSIGN 'low'
   └── General -> ASSIGN 'low'
```

---

## 4. Keyword Rules Matrix

### High-Priority Trigger Patterns (`high`)
Matching any of these case-insensitive regex patterns escalates the ticket directly to `high`:

| Pattern / Keyword | Domain | Operational Rationale |
| :--- | :--- | :--- |
| `\boutage\b` | Technical | Production cluster or service completely unavailable |
| `\bdown\b` | Technical | Full downtime event reported |
| `\bdata\s+loss\b` | Technical | Critical data integrity failure requiring immediate restoration |
| `\bcrashed\b` | Technical | Repeated service crash or unhandled failure |
| `\block(ed)?\s*out\b` | Access | User or administrator unable to access tenant |
| `\blockout\b` | Access | Emergency MFA or credential lockout |
| `\brevoke\s+access\b` | Access / Security | Terminated personnel or compromised session isolation |
| `\bbreach\b` / `\bsecurity\s+incident\b` | Security | Suspected compromise or unauthorized activity |
| `\bunauthorized\b` | Access / Security | 401/403 security failures on critical API pathways |
| `\bcharged\s+twice\b` | Billing | Duplicate transaction on corporate payment method |
| `\bduplicate\s+charge\b` | Billing | Billing dispute with immediate financial consequence |
| `\burgent\b` / `\bemergency\b` / `\bcritical\b` | Cross-Domain | Explicit urgent escalation language |

### Medium-Priority Trigger Patterns (`medium`)
If no high-priority keyword is triggered, the engine checks for operational degradation:

| Pattern / Keyword | Domain | Operational Rationale |
| :--- | :--- | :--- |
| `\btimeout\b` | Technical | SQL or network query exceeding timeout threshold |
| `\b502\b` | Technical | Bad Gateway HTTP response between reverse proxy and container |
| `\bdegraded\b` / `\blatency\b` | Technical | Suboptimal response times without full downtime |
| `\bintermittent\b` | Technical | Non-deterministic errors affecting a subset of requests |
| `\bfailed\s+to\s+start\b` | Technical | VM or container provisioning failure |
| `\bpassword\s+reset\b` | Access | Non-emergency credential update for single contractor/user |
| `\bpayment\s+failure\b` | Billing | Card charge failed; grace period applies before suspension |
| `\bunexpected\s+surge\b` | Billing | Bandwidth egress or capacity bill spike inquiry |
| `\bsuspended\b` / `\bexpired\b` | Technical / Access | VM state or API key expiration |

---

## 5. Category Defaults & Team Assignment Table

When a ticket does not match any explicit keyword triggers, it receives a default priority and is routed to its designated team:

| Category | Default Priority | Assigned Team | Team Scope |
| :--- | :--- | :--- | :--- |
| **Technical** | `medium` | `Engineering Support` | AKS, VMs, Azure SQL, Blob storage, Front Door, networking |
| **Access** | `medium` | `IT Security / Identity` | Entra ID, MFA recovery, Okta SSO, RBAC roles, TAP generation |
| **Billing** | `low` | `Finance Support` | Invoice downloads, tax certificates, VAT, EA agreement updates |
| **General** | `low` | `Customer Care` | SLAs, business hours, SOC2/ISO certificates, roadmaps, feedback |

---

## 6. Verification and Unit Tests

The priority engine is verified by comprehensive unit tests in `tests/test_priority.py`:
- `test_priority_rules_outage_high`: Verifies "outage" triggers `high`.
- `test_priority_rules_locked_out_high`: Verifies "locked out" triggers `high`.
- `test_priority_rules_charged_twice_high`: Verifies "charged twice" triggers `high`.
- `test_priority_rules_data_loss_high`: Verifies "data loss" triggers `high`.
- `test_priority_rules_urgent_high`: Verifies "urgent" triggers `high`.
- `test_priority_medium_keywords`: Verifies "502" and "timeout" trigger `medium`.
- `test_priority_category_defaults`: Verifies standard category defaults (`low` for Billing/General, `medium` for Technical).

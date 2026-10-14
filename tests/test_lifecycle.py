"""
test_lifecycle.py - Tests for support ticket state machine and approval lifecycle.
State progression: received -> draft_generated -> (needs_review) -> approved -> ready.
"""

from fastapi.testclient import TestClient


def test_draft_not_ready_before_approval(client: TestClient):
    ticket_payload = {
        "ticket_id": "TCK-LIFE-001",
        "message": "Need help verifying SSL certificates for Azure Front Door custom domain.",
    }
    response = client.post("/tickets", json=ticket_payload)
    assert response.status_code == 201
    ticket = response.json()

    # Draft must NOT be 'ready' before an explicit human approval call
    assert ticket["status"] in ["draft_generated", "needs_review"]
    assert ticket["status"] != "ready"


def test_approval_success_marks_ready(client: TestClient):
    ticket_payload = {
        "ticket_id": "TCK-LIFE-002",
        "message": "Where can I find the SOC2 compliance report?",
    }
    client.post("/tickets", json=ticket_payload)

    # Approve ticket
    approve_res = client.post("/tickets/TCK-LIFE-002/approve")
    assert approve_res.status_code == 200
    data = approve_res.json()
    assert "approved and marked ready" in data["message"].lower()
    assert data["ticket"]["status"] == "ready"

    # Confirm GET /tickets/{id} also shows 'ready'
    get_res = client.get("/tickets/TCK-LIFE-002")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "ready"


def test_approval_nonexistent_ticket_returns_404(client: TestClient):
    res = client.post("/tickets/DOES-NOT-EXIST-404/approve")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_double_approval_returns_409_conflict(client: TestClient):
    ticket_payload = {
        "ticket_id": "TCK-LIFE-003",
        "message": "General billing question about monthly cycle dates.",
    }
    client.post("/tickets", json=ticket_payload)

    # First approval succeeds
    res1 = client.post("/tickets/TCK-LIFE-003/approve")
    assert res1.status_code == 200
    assert res1.json()["ticket"]["status"] == "ready"

    # Second approval call returns 409 Conflict
    res2 = client.post("/tickets/TCK-LIFE-003/approve")
    assert res2.status_code == 409
    assert "already been approved" in res2.json()["detail"].lower()


def test_team_routing_assignments(client: TestClient):
    """Each category must map to its documented support team (deterministic config table)."""
    cases = [
        ("TCK-ROUTE-1", "We were charged twice for the same Azure subscription this month.", "Finance Support"),
        ("TCK-ROUTE-2", "Production App Service is returning 502 errors intermittently.", "Engineering Support"),
        ("TCK-ROUTE-3", "User account is locked out after failed MFA attempts.", "IT Security / Identity"),
        ("TCK-ROUTE-4", "How do I request a copy of our Azure SLA compliance certificate?", "Customer Care"),
    ]
    for ticket_id, message, expected_team in cases:
        res = client.post("/tickets", json={"ticket_id": ticket_id, "message": message})
        assert res.status_code == 201, f"Ticket {ticket_id} creation failed: {res.json()}"
        data = res.json()
        assert data["assigned_team"] == expected_team, (
            f"Ticket {ticket_id}: expected team '{expected_team}', got '{data['assigned_team']}' "
            f"(category={data['category']})"
        )

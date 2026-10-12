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

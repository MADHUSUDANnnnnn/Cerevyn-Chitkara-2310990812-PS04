"""
test_api.py - Tests for REST API endpoints: creation, retrieval, filtering, validation, and health.
"""

from fastapi.testclient import TestClient


def test_create_ticket_success(client: TestClient):
    payload = {
        "ticket_id": "TEST-TCK-001",
        "message": "Our primary database is experiencing high query latency and connection pool exhaustion.",
    }
    response = client.post("/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["ticket_id"] == "TEST-TCK-001"
    assert data["category"] in ["Technical", "Billing", "Access", "General"]
    assert data["priority"] in ["low", "medium", "high"]
    assert data["assigned_team"] in [
        "Finance Support",
        "Engineering Support",
        "IT Security / Identity",
        "Customer Care",
    ]
    assert len(data["summary"]) > 0
    assert len(data["draft_response"]) > 0
    assert data["status"] in ["draft_generated", "needs_review"]
    assert data["draft_source"] in ["llm", "template"]
    assert "created_at" in data
    assert "updated_at" in data


def test_duplicate_ticket_id_returns_409(client: TestClient):
    payload = {
        "ticket_id": "TEST-DUP-001",
        "message": "First submission regarding billing questions.",
    }
    res1 = client.post("/tickets", json=payload)
    assert res1.status_code == 201

    # Second submission with same ticket_id
    res2 = client.post("/tickets", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_empty_or_whitespace_message_returns_422(client: TestClient):
    # Empty message
    res1 = client.post("/tickets", json={"ticket_id": "TCK-VAL-1", "message": ""})
    assert res1.status_code == 422

    # Whitespace only message
    res2 = client.post("/tickets", json={"ticket_id": "TCK-VAL-2", "message": "   \n\t  "})
    assert res2.status_code == 422


def test_missing_ticket_id_returns_422(client: TestClient):
    res = client.post("/tickets", json={"message": "Valid message but missing ticket_id."})
    assert res.status_code == 422

    # Empty whitespace ticket_id
    res_empty = client.post("/tickets", json={"ticket_id": "   ", "message": "Valid message."})
    assert res_empty.status_code == 422


def test_get_ticket_by_id(client: TestClient):
    payload = {
        "ticket_id": "TCK-GET-001",
        "message": "Inquiry regarding SOC2 compliance certificate download.",
    }
    client.post("/tickets", json=payload)

    # Fetch existing
    res = client.get("/tickets/TCK-GET-001")
    assert res.status_code == 200
    assert res.json()["ticket_id"] == "TCK-GET-001"

    # Fetch nonexistent returns 404
    res_404 = client.get("/tickets/NONEXISTENT-999")
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()


def test_list_tickets_with_status_filter(client: TestClient):
    client.post("/tickets", json={"ticket_id": "TCK-LIST-1", "message": "Outage on web server."})
    client.post("/tickets", json={"ticket_id": "TCK-LIST-2", "message": "General question about pricing tiers."})

    # List all
    res_all = client.get("/tickets")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 2

    # List with status filter
    res_filtered = client.get("/tickets?status=draft_generated")
    assert res_filtered.status_code == 200
    for t in res_filtered.json():
        assert t["status"] == "draft_generated"


def test_health_endpoints(client: TestClient):
    # GET /health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    assert res_health.json()["database"] == "ok"

    # GET /health/llm
    res_llm = client.get("/health/llm")
    assert res_llm.status_code == 200
    data = res_llm.json()
    assert "configured" in data
    assert "reachable" in data
    assert "message" in data


def test_metrics_evaluation_endpoint(client: TestClient):
    res = client.get("/metrics/evaluation")
    assert res.status_code == 200
    data = res.json()
    assert "embedding_classifier" in data
    assert "keyword_baseline" in data
    assert "dataset_split" in data

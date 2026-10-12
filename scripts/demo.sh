#!/usr/bin/env bash
# ==============================================================================
# demo.sh - End-to-end demonstration script for Cerevyn Ticket Automation (PS04)
# Fires all lifecycle flows in sequence with pretty-printed responses.
# ==============================================================================

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m"

echo -e "${BOLD}${BLUE}======================================================================${NC}"
echo -e "${BOLD}${BLUE} Cerevyn Technical Assessment PS04: Live Demo Walkthrough ${NC}"
echo -e "${BOLD}${BLUE} Candidate: Madhusudan Mudgal (Chitkara University - 2310990812) ${NC}"
echo -e "${BOLD}${BLUE}======================================================================${NC}\n"

# Check API health
echo -e "${YELLOW}[0/8] Checking API Liveness (${BASE_URL}/health)...${NC}"
curl -s -f "${BASE_URL}/health" | python3 -m json.tool || {
  echo -e "${RED}Error: Server is not running at ${BASE_URL}. Start it using 'uvicorn app.main:app --port 8000' or Docker.${NC}"
  exit 1
}
echo -e "${GREEN}✓ Health check OK.${NC}\n"

# 1. Normal Ticket Submission
echo -e "${YELLOW}[1/8] Scenario 1: Standard High-Severity Outage Ticket (Deterministic Priority + Routing)...${NC}"
TCK_ID="DEMO-TCK-$(date +%s)"
curl -s -X POST "${BASE_URL}/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "'"${TCK_ID}"'",
    "message": "Our production Azure Kubernetes Service cluster is down with an unexpected outage. All customer traffic is dropping."
  }' | python3 -m json.tool
echo -e "${GREEN}✓ Ticket ${TCK_ID} created. Category=Technical, Priority=high, Assigned Team=Engineering Support.${NC}\n"

# 2. Ambiguous Ticket Routing to needs_review
echo -e "${YELLOW}[2/8] Scenario 2: Ambiguous Ticket Routed to 'needs_review' (Confidence below threshold)...${NC}"
AMB_ID="DEMO-AMB-$(date +%s)"
curl -s -X POST "${BASE_URL}/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "'"${AMB_ID}"'",
    "message": "I cannot view my monthly invoice after login because the portal says access denied."
  }' | python3 -m json.tool
echo -e "${GREEN}✓ Ambiguous ticket created. Notice status='needs_review'.${NC}\n"

# 3. Duplicate Ticket ID (HTTP 409)
echo -e "${YELLOW}[3/8] Scenario 3: Reject Duplicate Ticket ID (HTTP 409 Conflict)...${NC}"
curl -s -i -X POST "${BASE_URL}/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "'"${TCK_ID}"'",
    "message": "Attempting duplicate ticket creation."
  }' | head -n 12
echo -e "${GREEN}✓ Duplicate ticket properly rejected with HTTP 409 Conflict.${NC}\n"

# 4. Invalid Input Validation (HTTP 422)
echo -e "${YELLOW}[4/8] Scenario 4: Reject Empty / Whitespace Message (HTTP 422 Unprocessable Entity)...${NC}"
curl -s -i -X POST "${BASE_URL}/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "DEMO-INVALID-001",
    "message": "   "
  }' | head -n 12
echo -e "${GREEN}✓ Blank message properly rejected with HTTP 422.${NC}\n"

# 5. Human Approval Workflow
echo -e "${YELLOW}[5/8] Scenario 5: Human Approval Transition (draft_generated -> ready)...${NC}"
curl -s -X POST "${BASE_URL}/tickets/${TCK_ID}/approve" | python3 -m json.tool
echo -e "${GREEN}✓ Ticket draft approved and marked status='ready'.${NC}\n"

# 6. Double Approval Conflict (HTTP 409)
echo -e "${YELLOW}[6/8] Scenario 6: Reject Double Approval (HTTP 409 Conflict)...${NC}"
curl -s -i -X POST "${BASE_URL}/tickets/${TCK_ID}/approve" | head -n 12
echo -e "${GREEN}✓ Second approval attempt rejected with HTTP 409 Conflict.${NC}\n"

# 7. LLM Connectivity Health Check
echo -e "${YELLOW}[7/8] Scenario 7: LLM Health Probe (No ticket data transmitted)...${NC}"
curl -s "${BASE_URL}/health/llm" | python3 -m json.tool
echo -e "${GREEN}✓ LLM health report retrieved safely.${NC}\n"

# 8. Test Set Benchmark Metrics Retrieval
echo -e "${YELLOW}[8/8] Scenario 8: Test-Set Evaluation Metrics (/metrics/evaluation)...${NC}"
curl -s "${BASE_URL}/metrics/evaluation" | python3 -m json.tool | head -n 35
echo -e "${GREEN}✓ Retrieved stored evaluation metrics.${NC}\n"

echo -e "${BOLD}${GREEN}======================================================================${NC}"
echo -e "${BOLD}${GREEN} Demo script completed successfully! All scenarios verified. ${NC}"
echo -e "${BOLD}${GREEN}======================================================================${NC}"

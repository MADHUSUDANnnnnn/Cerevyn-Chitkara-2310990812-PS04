# 3-5 Minute Technical Demo Walkthrough Guide

**Problem Statement**: PS04 - Azure Support Ticket Automation  
**Candidate**: Madhusudan Mudgal (Chitkara University, Roll No: 2310990812)  
**Target Audience**: Technical Assessment Panel / Hiring Manager

---

## 1. Demo Checklist & Preparation (30 Seconds)

1. **Terminal 1**: Start the application locally:
   ```bash
   uvicorn app.main:app --port 8000
   ```
2. **Terminal 2**: Have `scripts/demo.sh` ready or execute the curl requests below.
3. **Verify Environment**:
   - `GROQ_API_KEY` configured in `.env` for live LLM mode (`draft_source: "llm"`).
   - Unset or empty `GROQ_API_KEY` for deterministic template mode (`draft_source: "template"`).

---

## 2. Minute 1: Triage, Classification & Deterministic Priority

### Step 1: Submit a Critical Production Outage Ticket
Explain to the evaluator: *"We submit an unformatted user complaint about an AKS cluster outage. Notice how our sentence embedding model classifies it as Technical, our deterministic engine escalates it to high priority due to the outage keyword, and it routes directly to Engineering Support without relying on an LLM for routing."*

```bash
curl -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "DEMO-TCK-001",
    "message": "Our production Azure Kubernetes Service cluster is down with an unexpected outage. All customer traffic is dropping."
  }' | jq
```

**Key Points to Highlight**:
- `category`: `"Technical"` (via SentenceTransformers + Logistic Regression).
- `priority`: `"high"` (triggered by keyword regex `outage`).
- `assigned_team`: `"Engineering Support"`.
- `status`: `"draft_generated"`.
- `draft_source`: `"llm"` (or `"template"` if offline).
- Grounded draft incorporates help-center guidance on incident triaging.

---

## 3. Minute 2: Ambiguity Handling & Guardrails

### Step 2: Submit an Ambiguous Multi-Domain Ticket
Explain: *"Now we submit a borderline inquiry: a user reporting an access denied error when attempting to view billing invoices. This touches both Billing and Access. Our model calculates confidence. Because the confidence is below our cross-validation threshold (0.35), the ticket is routed to `needs_review` instead of guessing."*

```bash
curl -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "DEMO-AMB-001",
    "message": "I can not see my invoice after login. The billing tab says access denied when I click view statements."
  }' | jq
```

**Key Points to Highlight**:
- `status`: `"needs_review"`.
- Demonstrates true human-in-the-loop protection against automated errors.

### Step 3: Input Validation & Duplicate Rejection
Explain: *"Our REST API enforces strict validation. If an agent tries to reuse `DEMO-TCK-001`, the API rejects it with HTTP 409 Conflict."*

```bash
curl -i -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "DEMO-TCK-001",
    "message": "Duplicate ID test."
  }'
```

And submitting blank or whitespace-only bodies triggers HTTP 422:
```bash
curl -i -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"ticket_id": "INVALID-1", "message": "   "}'
```

---

## 4. Minute 3: State Machine & Human Approval Workflow

### Step 4: Approve the Ticket Draft
Explain: *"In our lifecycle, no response is ever sent or marked ready automatically. A human support lead must inspect the draft and explicitly approve it. We call `POST /tickets/{id}/approve`."*

```bash
curl -X POST http://localhost:8000/tickets/DEMO-TCK-001/approve | jq
```

**Key Points to Highlight**:
- Status moves from `draft_generated` -> `approved` -> `ready`.
- Attempting to approve the same ticket again returns **HTTP 409 Conflict**:
  ```bash
  curl -i -X POST http://localhost:8000/tickets/DEMO-TCK-001/approve
  ```

---

## 5. Minute 4: LLM Fallback & Graceful Degradation

### Step 5: Offline / Unset Key Demonstration
Explain: *"To prove that our architecture has zero hard dependency on external vendors, we can unset `GROQ_API_KEY` or simulate a gateway timeout. The app continues to operate seamlessly using our deterministic `TemplateClient` without crashing."*

1. Stop server, run with empty key:
   ```bash
   GROQ_API_KEY="" uvicorn app.main:app --port 8000
   ```
2. Submit a ticket:
   ```bash
   curl -X POST http://localhost:8000/tickets \
     -H "Content-Type: application/json" \
     -d '{
       "ticket_id": "DEMO-OFFLINE-001",
       "message": "Where can I download our monthly billing breakdown?"
     }' | jq
   ```
3. Notice:
   - `draft_source`: `"template"`.
   - The summary and response are cleanly generated from the grounded KB article.
   - `GET /health/llm` reports `configured: false` with zero sensitive data leaks.

---

## 6. Minute 5: Benchmarks, CI, and Container Execution

### Step 6: View Live Evaluation Metrics
```bash
curl http://localhost:8000/metrics/evaluation | jq .embedding_classifier
```
Explain: *"The embedding classifier achieves 90% accuracy on our locked test set, outperforming keyword baselines on semantic phrasing."*

### Step 7: Run the Automated Script
Execute the all-in-one demo script:
```bash
./scripts/demo.sh
```

### Step 8: Container Run
```bash
docker run -p 8000:8000 --env-file .env cerevyn-ticket-app:latest
```
Show that the container starts up offline instantly because the embedding model weights were pre-cached at build time.

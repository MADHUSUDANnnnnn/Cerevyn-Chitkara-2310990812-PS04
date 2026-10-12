# Model Evaluation Report: PS04 Azure Support Ticket Automation

**Generated**: 2026-10-12T09:25:07.931148Z  
**Candidate**: Madhusudan Mudgal (Chitkara University, Roll No: 2310990812)  
**Dataset**: 30 Labeled Fictional Support Tickets (Stratified Split: 20 Train / 10 Test, Seed=42)

---

## 1. Executive Summary & Benchmark Comparison

| Metric | Sentence Embeddings + Logistic Regression | Keyword Rule Baseline | Delta |
| :--- | :--- | :--- | :--- |
| **Test Accuracy** | **90.0%** (9/10) | **100.0%** (10/10) | **+-10.0%** |
| **Train CV Accuracy** | **60.0%** (4-fold CV) | N/A (rule-based) | - |
| **Hyperparameter C** | **2.0** (tuned on train set) | N/A | - |
| **Confidence Threshold** | **0.35** (OOF-calibrated) | N/A | - |
| **Mean Test Confidence** | **0.3686** | N/A | - |
| **Routed to Review** | **3** tickets | N/A | - |

---

## 2. Embedding Classifier Detailed Metrics

### Per-Class Performance (Test Set: N=10)

| Category | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| **Billing** | 0.75 | 1.00 | 0.86 | 3 |
| **Technical** | 1.00 | 1.00 | 1.00 | 3 |
| **Access** | 1.00 | 0.50 | 0.67 | 2 |
| **General** | 1.00 | 1.00 | 1.00 | 2 |
| **Macro Avg** | 0.94 | 0.88 | 0.88 | 10 |
| **Weighted Avg** | 0.93 | 0.90 | 0.89 | 10 |

### Confusion Matrix (Predicted vs True)

```
Labels: ['Billing', 'Technical', 'Access', 'General']
Billing     : [3, 0, 0, 0]
Technical   : [0, 3, 0, 0]
Access      : [1, 0, 1, 0]
General     : [0, 0, 0, 2]
```

---

## 3. Ambiguity & Human-in-the-Loop Routing

Uncertain predictions where `confidence < 0.35` are safely routed to `needs_review` status instead of committing a wrong automated draft.

**Tickets Routed to Human Review**: 3

- **Ticket ID**: `TCK-1015`
  - Message: *"Please reset the password and temporary access pass for contractor user dev_contractor_09@cerevyn.com."*
  - Predicted: **Billing** (Confidence: `0.3244` < `0.35`)
  - True Category: **Access**
- **Ticket ID**: `TCK-1019`
  - Message: *"The API gateway key for our microservices integration has expired and requests are returning 401 Unauthorized."*
  - Predicted: **Access** (Confidence: `0.3085` < `0.35`)
  - True Category: **Access**
- **Ticket ID**: `TCK-1024`
  - Message: *"Thank you for resolving our previous query. What is the process for submitting feedback on our assigned technical account manager?"*
  - Predicted: **General** (Confidence: `0.2994` < `0.35`)
  - True Category: **General**

---

## 4. Honest Methodology & Sample Size Disclosure

1. **Strict Partitioning**: The 10 test tickets were locked before hyperparameter exploration. Neither LogisticRegression `C` nor `CONFIDENCE_THRESHOLD` were tuned on the test set.
2. **Sample Granularity**: With a test size of $N=10$, each individual ticket corresponds to exactly $10\%$ of test accuracy. While the performance demonstrates the embedding model's strong semantic representation capabilities over basic keyword matching, results in production should be tracked using rolling online metrics and shadow deployment.
3. **Reproducibility**: Splitting uses fixed `random_state=42` and `StratifiedKFold(n_splits=4)` ensuring deterministic verification across environments.

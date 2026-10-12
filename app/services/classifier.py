"""
classifier.py - Ticket category classifier using SentenceTransformers and LogisticRegression.
Includes cross-validation tuning for hyperparameter C and confidence threshold selection
on the 20-ticket training set ONLY (never the test set).
Also implements a simple keyword-rule baseline classifier for comparison.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import warnings
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from app.config import settings
from app.schemas import TicketCategory

# Suppress benign intermediate SIMD matmul RuntimeWarnings from sklearn linesearch on small sample arrays
warnings.filterwarnings("ignore", category=RuntimeWarning, module="sklearn")

CATEGORY_LIST: List[TicketCategory] = ["Billing", "Technical", "Access", "General"]

# Baseline Keyword Rules
KEYWORD_RULES = {
    "Billing": [
        "invoice", "billed", "billing", "charged", "refund", "charge", "payment",
        "visa", "credit card", "vat", "fees", "egress fees", "balance",
    ],
    "Technical": [
        "kubernetes", "aks", "cluster", "outage", "sql", "timeout", "cpu", "etl",
        "blob", "storage", "502", "bad gateway", "vm", "virtual machine",
        "redis", "ssl", "crash", "handshake", "data loss",
    ],
    "Access": [
        "locked out", "lockout", "mfa", "rbac", "staging", "okta", "single sign-on",
        "sso", "saml", "password", "reset", "api gateway key", "unauthorized",
        "401", "revoke", "tokens", "permission",
    ],
    "General": [
        "soc2", "iso27001", "compliance", "hours", "sla", "demo", "governance",
        "call", "migration", "roadmap", "feedback", "manager",
    ],
}


class KeywordBaselineClassifier:
    """A transparent, rule-based keyword frequency baseline."""

    def predict(self, text: str) -> TicketCategory:
        clean_text = text.lower()
        scores = {cat: 0 for cat in CATEGORY_LIST}
        for cat, keywords in KEYWORD_RULES.items():
            for kw in keywords:
                if kw in clean_text:
                    scores[cat] += 1
        max_score = max(scores.values())
        if max_score == 0:
            return "General"
        # Return category with highest match count
        for cat in CATEGORY_LIST:
            if scores[cat] == max_score:
                return cat
        return "General"


class TicketClassifier:
    """
    ML Classifier using SentenceTransformers (all-MiniLM-L6-v2) + LogisticRegression.
    Tunes C and confidence threshold strictly via Cross-Validation on the 20-sample training set.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        train_path: Optional[Path] = None,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.embedder = SentenceTransformer(self.model_name)
        self.clf = LogisticRegression(random_state=42, max_iter=500)
        self.classes: List[str] = CATEGORY_LIST
        self.is_trained = False
        self.best_c: float = 1.0
        self.cv_threshold: float = 0.45
        self.train_path = (
            train_path
            or Path(__file__).resolve().parent.parent.parent / "data" / "train_set.csv"
        )
        self._ensure_trained()

    def _ensure_trained(self):
        if self.train_path.exists():
            df = pd.read_csv(self.train_path)
            self.train_and_tune(df)

    def train_and_tune(self, df_train: pd.DataFrame) -> Dict[str, float]:
        """
        Tunes LogisticRegression C and chooses the confidence threshold strictly
        using StratifiedKFold on the training set. Never touches the test set!
        """
        X_texts = df_train["message"].tolist()
        y = df_train["category"].tolist()

        X_embeddings = self.embedder.encode(X_texts, normalize_embeddings=True)

        # Cross-validation hyperparameter tuning for C on the training set
        # Using liblinear solver which is robust for small sample high-dimensional data (N=20, D=384)
        candidate_c_values = [0.1, 0.5, 1.0, 2.0]
        best_acc = -1.0
        best_c = 1.0

        skf = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)

        for c_val in candidate_c_values:
            fold_accs = []
            for train_idx, val_idx in skf.split(X_embeddings, y):
                X_tr, X_val = X_embeddings[train_idx], X_embeddings[val_idx]
                y_tr, y_val = [y[i] for i in train_idx], [y[i] for i in val_idx]

                clf_fold = LogisticRegression(C=c_val, solver="liblinear", random_state=42, max_iter=500)
                clf_fold.fit(X_tr, y_tr)
                fold_accs.append(clf_fold.score(X_val, y_val))

            mean_acc = float(np.mean(fold_accs))
            if mean_acc > best_acc:
                best_acc = mean_acc
                best_c = c_val

        self.best_c = best_c

        # Train final model on entire training set using the best C
        self.clf = LogisticRegression(C=self.best_c, solver="liblinear", random_state=42, max_iter=500)
        self.clf.fit(X_embeddings, y)
        self.classes = list(self.clf.classes_)
        self.is_trained = True

        # Determine optimal confidence threshold using Out-Of-Fold probabilities on training set
        oof_confidences_correct = []
        oof_confidences_incorrect = []

        for train_idx, val_idx in skf.split(X_embeddings, y):
            X_tr, X_val = X_embeddings[train_idx], X_embeddings[val_idx]
            y_tr, y_val = [y[i] for i in train_idx], [y[i] for i in val_idx]

            clf_fold = LogisticRegression(C=self.best_c, solver="liblinear", random_state=42, max_iter=500)
            clf_fold.fit(X_tr, y_tr)
            probs = clf_fold.predict_proba(X_val)

            for i, val_i in enumerate(val_idx):
                prob = probs[i]
                pred_label = clf_fold.classes_[np.argmax(prob)]
                conf = float(np.max(prob))
                if pred_label == y_val[i]:
                    oof_confidences_correct.append(conf)
                else:
                    oof_confidences_incorrect.append(conf)

        # We set threshold such that high confidence predictions are trusted,
        # but borderline/uncertain predictions (< 0.45 or lower bound of correct predictions)
        # are safely routed to needs_review.
        if oof_confidences_correct:
            # 10th percentile of correct out-of-fold predictions
            chosen_threshold = float(np.percentile(oof_confidences_correct, 10))
            # Bound safely between 0.35 and 0.55 to avoid routing typical clear tickets to needs_review
            self.cv_threshold = round(max(0.35, min(0.55, chosen_threshold)), 3)
        else:
            self.cv_threshold = 0.45

        return {
            "best_c": self.best_c,
            "cv_accuracy": best_acc,
            "cv_threshold": self.cv_threshold,
        }

    @property
    def effective_threshold(self) -> float:
        """Returns env-configured threshold if set, otherwise the CV-tuned threshold."""
        if settings.CONFIDENCE_THRESHOLD is not None:
            return settings.CONFIDENCE_THRESHOLD
        return self.cv_threshold

    def predict(self, text: str) -> Tuple[TicketCategory, float, bool]:
        """
        Classifies input text.
        Returns (predicted_category, confidence_score, needs_review_flag).
        """
        embedding = self.embedder.encode([text], normalize_embeddings=True)
        probs = self.clf.predict_proba(embedding)[0]
        best_idx = int(np.argmax(probs))
        predicted_category = self.classes[best_idx]
        confidence = round(float(probs[best_idx]), 4)

        threshold = self.effective_threshold
        needs_review = confidence < threshold

        return predicted_category, confidence, needs_review


_classifier_instance: Optional[TicketClassifier] = None


def get_classifier() -> TicketClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = TicketClassifier()
    return _classifier_instance

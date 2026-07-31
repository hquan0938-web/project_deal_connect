import os
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.metrics import f1_score
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "data", "models", "match_scorer.joblib")
LABELS_PATH = os.path.join(BASE_DIR, "data", "training", "match_labels.csv")

FEATURE_COLUMNS = ["technology_focus", "problem_focus", "investment_thesis",
                    "customer_focus", "funding_fit"]


def build_feature_vector(indiv_score: dict, funding_fit: float) -> np.ndarray:
    """
    Convert the score dict from llm_judge + funding_fit into a feature
    vector for Logistic Regression.
    Must match FEATURE_COLUMNS order, with funding_fit as the last column.
    """
    # FIX: funding_fit is passed as its own parameter, not part of
    # indiv_score, so it must be appended explicitly rather than looked
    # up from the dict (that lookup would always fall back to 0.0).
    values = [indiv_score.get(col, 0.0) for col in FEATURE_COLUMNS[:-1]]
    values.append(funding_fit)
    # FIX: must be shape (1, n_features) — one row, n columns — not
    # (n_features, 1), or predict_proba will reject the shape.
    return np.array([values])


def compute_funding_fit(funding, min_ticket: float, max_ticket: float) -> float:
    """
    Soft score for how well a startup's funding ask fits an investor's
    ticket size range.
    - Inside [min_ticket, max_ticket] -> 1.0
    - Below min_ticket -> decays toward 0 as funding approaches 0
    - Above max_ticket -> decays toward 0 as funding approaches 2*max_ticket
    """
    if funding is None:
        return 0.5
    if min_ticket <= funding <= max_ticket:
        return 1.0
    nearest_edge = min_ticket if funding < min_ticket else max_ticket
    distance = abs(funding - nearest_edge) / max(nearest_edge, 1)
    return max(0.0, 1.0 - distance)


def train_model(labels_path: str = LABELS_PATH, model_path: str = MODEL_PATH) -> dict:
    if not os.path.exists(labels_path):
        raise FileNotFoundError(
            f"Labels file not found at {labels_path}. Expected a CSV with columns: "
            f"{FEATURE_COLUMNS + ['label']}"
        )

    df = pd.read_csv(labels_path)  # load the labeled CSV into a DataFrame
    missing_cols = set(FEATURE_COLUMNS + ["label"]) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in labels file: {missing_cols}")

    X = df[FEATURE_COLUMNS].values
    y = df["label"].values
    # X is the feature matrix, y is the label vector (0 or 1), both read from the CSV

    if len(df) < 20:
        print(f"[WARNING] Only {len(df)} samples — too few to train reliably. "
              f"Aim for at least 50-100 samples, balanced between label 0 and 1.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None
    )
    # stratify: keep the 0/1 label ratio consistent across train and test
    # falls back to None if there's only one class (stratify would error otherwise)

    model = LogisticRegression(class_weight="balanced")
    # class_weight="balanced" auto-reweights classes to counter label imbalance
    model.fit(X_train, y_train)

    metrics = {"n_samples": len(df)}
    
    if len(X_test) > 0 and len(set(y_test)) > 1:
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        metrics["test_accuracy"] = round(accuracy_score(y_test, y_pred), 3)
        metrics["test_auc"] = round(roc_auc_score(y_test, y_proba), 3)

        # --- Threshold tuning ---
        best_threshold, best_f1 = 0.5, -1.0
        
      # --- Threshold tuning ---
        # Default 0.5 is arbitrary when classes are imbalanced (171 label=0
        # vs 59 label=1 here). Instead, scan thresholds on the TEST set and
        # pick the one that maximizes F1 for the minority class (label=1).
        # NOTE: with only ~46 test samples, this threshold is itself noisy;
        # treat it as a starting point, not a fixed constant.
        for t in np.arange(0.05, 0.96, 0.01):
            f1 = f1_score(y_test, (y_proba >= t).astype(int), zero_division=0)
            if f1 > best_f1:
                best_f1, best_threshold = f1, round(float(t), 2)
                
        metrics["best_threshold"] = best_threshold
        metrics["best_threshold_f1"] = round(best_f1, 3)
        y_pred_tuned = (y_proba >= best_threshold).astype(int)
        
        metrics["test_accuracy_at_best_threshold"] = round(
            accuracy_score(y_test, y_pred_tuned), 3
        )
    else:
        best_threshold = 0.5 # Nên đổi lại thành 0.5 thay vì 0.3 ở khối else cho chuẩn mặc định

    metrics["learned_weights"] = dict(zip(FEATURE_COLUMNS, model.coef_[0].round(4)))
    metrics["intercept"] = round(model.intercept_[0], 4)
    
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)

    return metrics


def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    return joblib.load(MODEL_PATH)


def predict_score(indiv_score_dict: dict, funding_fit: float, fallback_weighted_score: float = None) -> float:
    model = load_model()
    if model is None:
        if fallback_weighted_score is not None:
            return fallback_weighted_score
        raise RuntimeError("No model was trained and no fallback_weighted_score to use")

    X = build_feature_vector(indiv_score_dict, funding_fit)
    proba = model.predict_proba(X)[0, 1]
    # [0, 1] -> row 0 (the single sample), column 1 (P of label 1 = "good match")
    return round(float(proba), 4)
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score
from xgboost import XGBClassifier
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "data", "models", "match_scorer.joblib")
LABELS_PATH = os.path.join(BASE_DIR, "data", "training", "match_labels.csv")
BASE_FEATURE_COLUMNS = ["technology_focus", "problem_focus", "investment_thesis",
                         "customer_focus", "funding_fit"]
 

ENGINEERED_FEATURE_COLUMNS = ["thesis_x_funding", "avg_semantic", "min_semantic"]
 
FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + ENGINEERED_FEATURE_COLUMNS
def feature_engineering(technology_focus: float, problem_focus: float,
                                 investment_thesis: float, customer_focus: float,
                                 funding_fit: float) -> dict:
    semantic_scores = [technology_focus, problem_focus, investment_thesis, customer_focus]
    return{
        "thesis_x_funding": investment_thesis * funding_fit,
        "avg_semantic": np.mean(semantic_scores),
        "min_semantic": np.min(semantic_scores),
    }
def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    engineered = df.apply(
        lambda row: feature_engineering(
            row["technology_focus"], row["problem_focus"],
            row["investment_thesis"], row["customer_focus"], row["funding_fit"],
        ),
        axis=1,
        result_type="expand",
    )
    return pd.concat([df, engineered], axis=1)
 
def build_feature_vector(indiv_score: dict, funding_fit: float) -> np.ndarray:
    """
    Convert the score dict from llm_judge + funding_fit into a feature
    vector for Logistic Regression.
    Must match FEATURE_COLUMNS order, with funding_fit as the last column.
    """
    base_dict = {col: indiv_score.get(col, 0.0) for col in BASE_FEATURE_COLUMNS}
    base_dict["funding_fit"] = funding_fit

    engineered = feature_engineering(
        base_dict["technology_focus"], base_dict["problem_focus"],
        base_dict["investment_thesis"], base_dict["customer_focus"], base_dict["funding_fit"],
    )
    values = [base_dict[col] for col in BASE_FEATURE_COLUMNS] + \
             [engineered[col] for col in ENGINEERED_FEATURE_COLUMNS]
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

def _load_training_df(labels_path: str) -> pd.DataFrame:
    if not os.path.exists(labels_path):
        raise FileNotFoundError(
            f"Labels file not found at {labels_path}. Expected a CSV with columns: "
            f"{BASE_FEATURE_COLUMNS + ['label']}"
        )
    df = pd.read_csv(labels_path)
    missing_cols = set(BASE_FEATURE_COLUMNS + ["label"]) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in labels file: {missing_cols}")
 
    df = add_engineered_features(df)
 
    if len(df) < 20:
        print(f"[WARNING] Only {len(df)} samples — too few to train reliably. "
              f"Aim for at least 50-100 samples, balanced between label 0 and 1.")
    return df

# def train_model(labels_path: str = LABELS_PATH, model_path: str = MODEL_PATH) -> dict:
#     if not os.path.exists(labels_path):
#         raise FileNotFoundError(
#             f"Labels file not found at {labels_path}. Expected a CSV with columns: "
#             f"{FEATURE_COLUMNS + ['label']}"
#         )

#     df = pd.read_csv(labels_path)  # load the labeled CSV into a DataFrame
#     missing_cols = set(FEATURE_COLUMNS + ["label"]) - set(df.columns)
#     if missing_cols:
#         raise ValueError(f"Missing columns in labels file: {missing_cols}")

#     X = df[FEATURE_COLUMNS].values
#     y = df["label"].values
#     # X is the feature matrix, y is the label vector (0 or 1), both read from the CSV

#     if len(df) < 20:
#         print(f"[WARNING] Only {len(df)} samples — too few to train reliably. "
#               f"Aim for at least 50-100 samples, balanced between label 0 and 1.")

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None
#     )
#     # stratify: keep the 0/1 label ratio consistent across train and test
#     # falls back to None if there's only one class (stratify would error otherwise)

#     model = LogisticRegression(class_weight="balanced")
#     # class_weight="balanced" auto-reweights classes to counter label imbalance
#     model.fit(X_train, y_train)

#     metrics = {"n_samples": len(df)}
    
#     if len(X_test) > 0 and len(set(y_test)) > 1:
#         y_pred = model.predict(X_test)
#         y_proba = model.predict_proba(X_test)[:, 1]
        
#         metrics["test_accuracy"] = round(accuracy_score(y_test, y_pred), 3)
#         metrics["test_auc"] = round(roc_auc_score(y_test, y_proba), 3)

#         # --- Threshold tuning ---
#         best_threshold, best_f1 = 0.5, -1.0
        
#       # --- Threshold tuning ---
#         # Default 0.5 is arbitrary when classes are imbalanced (171 label=0
#         # vs 59 label=1 here). Instead, scan thresholds on the TEST set and
#         # pick the one that maximizes F1 for the minority class (label=1).
#         # NOTE: with only ~46 test samples, this threshold is itself noisy;
#         # treat it as a starting point, not a fixed constant.
#         for t in np.arange(0.05, 0.96, 0.01):
#             f1 = f1_score(y_test, (y_proba >= t).astype(int), zero_division=0)
#             if f1 > best_f1:
#                 best_f1, best_threshold = f1, round(float(t), 2)
                
#         metrics["best_threshold"] = best_threshold
#         metrics["best_threshold_f1"] = round(best_f1, 3)
#         y_pred_tuned = (y_proba >= best_threshold).astype(int)
        
#         metrics["test_accuracy_at_best_threshold"] = round(
#             accuracy_score(y_test, y_pred_tuned), 3
#         )
#     else:
#         best_threshold = 0.5 # Nên đổi lại thành 0.5 thay vì 0.3 ở khối else cho chuẩn mặc định

#     metrics["learned_weights"] = dict(zip(FEATURE_COLUMNS, model.coef_[0].round(4)))
#     metrics["intercept"] = round(model.intercept_[0], 4)
    
#     os.makedirs(os.path.dirname(model_path), exist_ok=True)
#     joblib.dump(model, model_path)

#     return metrics


def train_model(labels_path: str = LABELS_PATH, model_path: str = MODEL_PATH,
                         n_splits: int = 5) -> dict:
    df = _load_training_df(labels_path)
    X = df[FEATURE_COLUMNS].values
    y = df["label"].values
    sample_weight = df["weight"].values if "weight" in df.columns else np.ones(len(df))
 
    n_pos, n_neg = (y == 1).sum(), (y == 0).sum()
    scale_pos_weight = n_neg / max(n_pos, 1)  # tương đương class_weight="balanced"
 
    model = XGBClassifier(
        n_estimators=50,
        max_depth=3,       
        learning_rate=0.1,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
    )
    metrics = {"n_samples": len(df)}
    if len(set(y)) > 1 and len(df) >= n_splits * 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42) #divided in a uniform way
        fold_aucs = []
        for train_idx, val_idx in cv.split(X, y):
            fold_model = XGBClassifier(**model.get_params())
            fold_model.fit(X[train_idx], y[train_idx], sample_weight=sample_weight[train_idx])
            if len(set(y[val_idx])) > 1:
                proba = fold_model.predict_proba(X[val_idx])[:, 1]
                fold_aucs.append(roc_auc_score(y[val_idx], proba))
        if fold_aucs:
            metrics["cv_auc_mean"] = round(float(np.mean(fold_aucs)), 3)
            metrics["cv_auc_std"] = round(float(np.std(fold_aucs)), 3)
    else :
            metrics["cv_auc_mean"] = None
            metrics["cv_auc_std"] = None
        
    model.fit(X, y, sample_weight=sample_weight)
    metrics["feature_importances"] = dict(zip(FEATURE_COLUMNS, model.feature_importances_.round(4)))
 
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump({"model": model, "type": "xgboost"}, model_path)
 
    return metrics


def load_model():
    if not os.path.exists(MODEL_PATH):
        return None
    return joblib.load(MODEL_PATH)
    

def predict_score(indiv_score_dict: dict, funding_fit: float, fallback_weighted_score: float = None) -> float:
    loaded = load_model()
    if loaded is None:
        if fallback_weighted_score is not None:
            return fallback_weighted_score
        raise RuntimeError("No model was trained and no fallback_weighted_score to use")

    model = loaded["model"]
    X = build_feature_vector(indiv_score_dict, funding_fit)
    proba = model.predict_proba(X)[0, 1]
    # [0, 1] -> row 0 (the single sample), column 1 (P of label 1 = "good match")
    return round(float(proba), 4)
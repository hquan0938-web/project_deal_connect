import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

from core.scoring_model import FEATURE_COLUMNS, add_engineered_features, LABELS_PATH


def eval_holdout_once(df: pd.DataFrame, test_size: float, random_state: int) -> float:
    bootstrap = df[df["source"] == "bootstrap_llm"]
    construction = df[df["source"] != "bootstrap_llm"]

    bs_train, bs_test = train_test_split(
        bootstrap, test_size=test_size, stratify=bootstrap["label"], random_state=random_state
    )
    train_df = pd.concat([bs_train, construction], ignore_index=True)

    X_train = train_df[FEATURE_COLUMNS].values
    y_train = train_df["label"].values
    w_train = train_df["weight"].values if "weight" in train_df.columns else np.ones(len(train_df))

    X_test = bs_test[FEATURE_COLUMNS].values
    y_test = bs_test["label"].values

    n_pos, n_neg = (y_train == 1).sum(), (y_train == 0).sum()
    model = XGBClassifier(
        n_estimators=50, max_depth=3, learning_rate=0.1,
        scale_pos_weight=n_neg / max(n_pos, 1), eval_metric="logloss",
    )
    model.fit(X_train, y_train, sample_weight=w_train)
    proba = model.predict_proba(X_test)[:, 1]
    return roc_auc_score(y_test, proba)


def eval_holdout(labels_path: str = LABELS_PATH, test_size: float = 0.2,
                  seeds: list = (0, 1, 42, 123, 2024)):
    df = pd.read_csv(labels_path)
    df = add_engineered_features(df)

    print(f"Data: {len(df)} dòng ({df['source'].value_counts().to_dict()})")

    aucs = []
    for seed in seeds:
        auc = eval_holdout_once(df, test_size, seed)
        aucs.append(auc)
        print(f"  seed={seed}: AUC = {round(auc, 4)}")

    print(f"AUC trung bình trên {len(seeds)} lần chia: {round(np.mean(aucs), 4)} "
          f"(std: {round(np.std(aucs), 4)})")
    return aucs


if __name__ == "__main__":
    eval_holdout()
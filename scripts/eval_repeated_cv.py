import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

from core.scoring_model import FEATURE_COLUMNS, add_engineered_features, LABELS_PATH


def eval_repeated_cv(labels_path: str = LABELS_PATH, n_splits: int = 5, n_repeats: int = 10):
    df = pd.read_csv(labels_path)
    df = add_engineered_features(df)

    bootstrap = df[df["source"] == "bootstrap_llm"].reset_index(drop=True)
    construction = df[df["source"] != "bootstrap_llm"]

    X_bs = bootstrap[FEATURE_COLUMNS].values
    y_bs = bootstrap["label"].values

    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=42)

    aucs = []
    for train_idx, test_idx in rskf.split(X_bs, y_bs):
        bs_train = bootstrap.iloc[train_idx]
        train_df = pd.concat([bs_train, construction], ignore_index=True)

        X_train = train_df[FEATURE_COLUMNS].values
        y_train = train_df["label"].values
        w_train = train_df["weight"].values if "weight" in train_df.columns else np.ones(len(train_df))

        n_pos, n_neg = (y_train == 1).sum(), (y_train == 0).sum()
        model = XGBClassifier(
            n_estimators=50, max_depth=3, learning_rate=0.1,
            scale_pos_weight=n_neg / max(n_pos, 1), eval_metric="logloss",
        )
        model.fit(X_train, y_train, sample_weight=w_train)

        X_test = X_bs[test_idx]
        y_test = y_bs[test_idx]
        proba = model.predict_proba(X_test)[:, 1]
        aucs.append(roc_auc_score(y_test, proba))

    aucs = np.array(aucs)
    print(f"Chạy {n_splits}-fold x {n_repeats} lần lặp = {len(aucs)} lần đo")
    print(f"AUC trung bình: {round(aucs.mean(), 4)} (std: {round(aucs.std(), 4)})")
    print(f"Khoảng 95%: [{round(np.percentile(aucs, 2.5), 4)}, {round(np.percentile(aucs, 97.5), 4)}]")
    return aucs


if __name__ == "__main__":
    eval_repeated_cv()
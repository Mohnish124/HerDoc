"""
HerDoc ML Training Pipeline
Dataset: UCI Maternal Health Risk Dataset
Task: 3-class classification (green / yellow / red)
Priority Metric: High-Risk (Red) Recall
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from data_loader import load_maternal_dataset

MODELS_DIR = ML_DIR / "exported"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_CLASSES = ["green", "yellow", "red"]
CLASS_LABELS = {"green": 0, "yellow": 1, "red": 2}
REVERSE_CLASS_LABELS = {0: "green", 1: "yellow", 2: "red"}


def prepare_data() -> Tuple[pd.DataFrame, pd.Series, np.ndarray, np.ndarray]:
    """Load and prepare features and target."""
    df = load_maternal_dataset()
    feature_cols = ["Age", "SystolicBP", "DiastolicBP", "BS", "BodyTemp", "HeartRate"]
    X = df[feature_cols]
    y_str = df["RiskLevel"]
    y = y_str.map(CLASS_LABELS).astype(int)
    return X, y, df[feature_cols].values, y.values


def build_models() -> Dict[str, Pipeline]:
    """
    Build candidate models with balanced class weighting
    to prioritize recall on the high-risk class.
    """
    models = {
        "Logistic Regression (Balanced)": Pipeline([
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                    solver="lbfgs",
                ),
            ),
        ]),
        "Random Forest (Balanced)": Pipeline([
            ("scaler", StandardScaler()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=150,
                    max_depth=8,
                    min_samples_split=4,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]),
    }
    return models


def evaluate_model(
    name: str,
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
) -> Dict[str, Any]:
    """Fit model on train set and evaluate on test set + 5-fold cross validation."""
    # 5-fold Stratified Cross-Validation on training set
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_results = cross_validate(
        pipeline,
        X_train,
        y_train,
        cv=skf,
        scoring=["accuracy", "f1_macro", "recall_macro"],
    )

    # Train on full train set
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    prec_macro = precision_score(y_test, y_pred, average="macro", zero_division=0)
    rec_macro = recall_score(y_test, y_pred, average="macro", zero_division=0)
    f1_macro = f1_score(y_test, y_pred, average="macro", zero_division=0)

    # Per-class metrics
    per_class_rec = recall_score(y_test, y_pred, average=None, labels=[0, 1, 2], zero_division=0)
    per_class_prec = precision_score(y_test, y_pred, average=None, labels=[0, 1, 2], zero_division=0)
    per_class_f1 = f1_score(y_test, y_pred, average=None, labels=[0, 1, 2], zero_division=0)

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2])
    high_risk_recall = per_class_rec[2]  # Index 2 is 'red' (high risk)
    high_risk_precision = per_class_prec[2]

    report = classification_report(
        y_test,
        y_pred,
        target_names=TARGET_CLASSES,
        digits=4,
        zero_division=0,
    )

    return {
        "name": name,
        "pipeline": pipeline,
        "cv_accuracy_mean": float(np.mean(cv_results["test_accuracy"])),
        "cv_f1_macro_mean": float(np.mean(cv_results["test_f1_macro"])),
        "test_accuracy": float(acc),
        "test_precision_macro": float(prec_macro),
        "test_recall_macro": float(rec_macro),
        "test_f1_macro": float(f1_macro),
        "high_risk_recall": float(high_risk_recall),
        "high_risk_precision": float(high_risk_precision),
        "per_class_recall": {cls: float(per_class_rec[i]) for i, cls in enumerate(TARGET_CLASSES)},
        "per_class_precision": {cls: float(per_class_prec[i]) for i, cls in enumerate(TARGET_CLASSES)},
        "per_class_f1": {cls: float(per_class_f1[i]) for i, cls in enumerate(TARGET_CLASSES)},
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }


def export_selected_model(
    best_eval: Dict[str, Any],
    feature_cols: list,
    X_train: pd.DataFrame,
) -> Tuple[Path, Path]:
    """Export the trained pipeline to joblib and portable JSON metadata."""
    model_path = MODELS_DIR / "maternal_risk_model.joblib"
    metadata_path = MODELS_DIR / "model_metadata.json"

    # Save joblib artifact
    joblib.dump(best_eval["pipeline"], model_path)

    # Extract scaler parameters for client portability
    scaler = best_eval["pipeline"].named_steps["scaler"]
    clf = best_eval["pipeline"].named_steps["clf"]

    scaler_params = {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "var": scaler.var_.tolist(),
    }

    metadata = {
        "selected_model": best_eval["name"],
        "dataset": "UCI Maternal Health Risk Dataset",
        "features": feature_cols,
        "classes": TARGET_CLASSES,
        "class_mapping": CLASS_LABELS,
        "priority_metric": "high_risk_recall",
        "metrics": {
            "test_accuracy": best_eval["test_accuracy"],
            "test_f1_macro": best_eval["test_f1_macro"],
            "high_risk_recall": best_eval["high_risk_recall"],
            "high_risk_precision": best_eval["high_risk_precision"],
            "per_class_recall": best_eval["per_class_recall"],
            "per_class_precision": best_eval["per_class_precision"],
            "confusion_matrix": best_eval["confusion_matrix"],
            "cv_accuracy_mean": best_eval["cv_accuracy_mean"],
            "cv_f1_macro_mean": best_eval["cv_f1_macro_mean"],
        },
        "scaler_params": scaler_params,
        "model_type": clf.__class__.__name__,
    }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return model_path, metadata_path


def main():
    print("==================================================")
    print("   HerDoc Maternal Risk ML Training Pipeline      ")
    print("==================================================")

    X, y, _, _ = prepare_data()
    feature_cols = list(X.columns)

    print(f"\nLoaded dataset shape: {X.shape}")
    print(f"Features: {feature_cols}")
    class_counts = y.value_counts().sort_index()
    for idx, count in class_counts.items():
        print(f"  Class {idx} ({REVERSE_CLASS_LABELS[idx]}): {count} samples ({count/len(y)*100:.1f}%)")

    # Stratified Train/Test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"\nTrain set: {len(X_train)} samples | Test set: {len(X_test)} samples")

    models = build_models()
    evaluations = {}

    for name, pipeline in models.items():
        print(f"\n--- Evaluating {name} ---")
        ev = evaluate_model(name, pipeline, X_train, X_test, y_train, y_test)
        evaluations[name] = ev

        print(f"CV 5-fold Mean Accuracy: {ev['cv_accuracy_mean']:.4f}")
        print(f"Test Accuracy:           {ev['test_accuracy']:.4f}")
        print(f"Test Macro F1:           {ev['test_f1_macro']:.4f}")
        print(f"* High-Risk (Red) Recall: {ev['high_risk_recall']:.4f} *")
        print(f"High-Risk (Red) Precision:{ev['high_risk_precision']:.4f}")
        print("\nClassification Report:\n", ev["classification_report"])
        print("Confusion Matrix [Green, Yellow, Red]:")
        cm = np.array(ev["confusion_matrix"])
        print(cm)

    # Model Comparison Summary
    print("\n==================================================")
    print("              MODEL COMPARISON SUMMARY            ")
    print("==================================================")
    print(f"{'Model':<32} | {'Accuracy':<8} | {'Macro F1':<8} | {'High-Risk Recall':<16} | {'High-Risk Prec':<14}")
    print("-" * 90)
    for name, ev in evaluations.items():
        print(
            f"{name:<32} | {ev['test_accuracy']:<8.4f} | {ev['test_f1_macro']:<8.4f} | {ev['high_risk_recall']:<16.4f} | {ev['high_risk_precision']:<14.4f}"
        )

    # Selection according to priority: Recall on High-Risk class
    best_model_name = max(
        evaluations.keys(),
        key=lambda k: (evaluations[k]["high_risk_recall"], evaluations[k]["test_f1_macro"]),
    )
    best_eval = evaluations[best_model_name]

    print("\n==================================================")
    print(f"  SELECTED MODEL: {best_model_name}")
    print(f"  Selection Rationale: Highest recall ({best_eval['high_risk_recall']:.2%}) on high-risk (red) cases,")
    print(f"  ensuring critical maternal complications are not missed.")
    print("==================================================")

    model_path, meta_path = export_selected_model(best_eval, feature_cols, X_train)
    print(f"\nSaved model artifact to:   {model_path}")
    print(f"Saved metadata to:         {meta_path}")
    print("\nML Training Pipeline completed successfully.")


if __name__ == "__main__":
    main()

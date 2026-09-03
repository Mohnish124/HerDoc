"""
Export trained Scikit-Learn Random Forest Pipeline to portable JSON for on-device React Native inference.
Extracts:
1. Scaler means & scales
2. Decision trees (nodes, thresholds, features, leaf values)
3. Class mapping
4. Verification test suite comparing Python sklearn predictions vs tree traversal logic
"""

import json
from pathlib import Path
import shutil
import joblib
import numpy as np
import pandas as pd

ML_DIR = Path(__file__).resolve().parent
EXPORTED_DIR = ML_DIR / "exported"
MOBILE_ML_DIR = Path(__file__).resolve().parents[2] / "mobile" / "app" / "ml"
MOBILE_ML_DIR.mkdir(parents=True, exist_ok=True)

MODEL_JOB_PATH = EXPORTED_DIR / "maternal_risk_model.joblib"


def tree_to_dict(tree):
    """Recursively convert a sklearn DecisionTreeClassifier tree_ to a compact dict."""
    def recurse(node_id):
        left_child = tree.children_left[node_id]
        right_child = tree.children_right[node_id]

        # Leaf node
        if left_child == -1 and right_child == -1:
            # Normalize class distribution
            val = tree.value[node_id][0]
            total = float(np.sum(val))
            prob = (val / total).tolist() if total > 0 else [0.33, 0.33, 0.34]
            return {"l": 1, "v": prob}

        # Split node: f = feature index, t = threshold, lc = left child, rc = right child
        return {
            "f": int(tree.feature[node_id]),
            "t": float(tree.threshold[node_id]),
            "l": 0,
            "lc": recurse(left_child),
            "rc": recurse(right_child),
        }

    return recurse(0)


def export_bundle():
    if not MODEL_JOB_PATH.exists():
        raise FileNotFoundError(f"Model file {MODEL_JOB_PATH} not found. Run train.py first.")

    pipeline = joblib.load(MODEL_JOB_PATH)
    scaler = pipeline.named_steps["scaler"]
    rf = pipeline.named_steps["clf"]

    trees_json = []
    for estimator in rf.estimators_:
        trees_json.append(tree_to_dict(estimator.tree_))

    bundle = {
        "model_name": "Random Forest (Balanced)",
        "features": ["Age", "SystolicBP", "DiastolicBP", "BS", "BodyTemp", "HeartRate"],
        "classes": ["green", "yellow", "red"],
        "class_indices": [0, 1, 2],
        "scaler": {
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
        },
        "trees": trees_json,
    }

    # Save to backend/ml/exported/
    backend_out = EXPORTED_DIR / "maternal_risk_model_bundle.json"
    backend_out.write_text(json.dumps(bundle), encoding="utf-8")
    print(f"Exported bundle to {backend_out} ({backend_out.stat().st_size / 1024:.1f} KB)")

    # Copy to mobile/app/ml/
    mobile_out = MOBILE_ML_DIR / "maternal_risk_model_bundle.json"
    mobile_out.write_text(json.dumps(bundle), encoding="utf-8")
    print(f"Copied bundle to mobile app at {mobile_out}")

    # Verify accuracy against sklearn on test inputs
    verify_bundle(pipeline, bundle)


def predict_pure_python(bundle, raw_features):
    """Simulate the exact JavaScript tree evaluation logic in Python."""
    # 1. Scale features
    means = bundle["scaler"]["mean"]
    scales = bundle["scaler"]["scale"]
    scaled = [(val - m) / s for val, m, s in zip(raw_features, means, scales)]

    # 2. Accumulate probabilities across all trees
    total_probs = [0.0, 0.0, 0.0]
    for tree in bundle["trees"]:
        curr = tree
        while curr["l"] == 0:
            feat_idx = curr["f"]
            threshold = curr["t"]
            if scaled[feat_idx] <= threshold:
                curr = curr["lc"]
            else:
                curr = curr["rc"]
        for i in range(3):
            total_probs[i] += curr["v"][i]

    n_trees = len(bundle["trees"])
    avg_probs = [p / n_trees for p in total_probs]
    pred_class_idx = int(np.argmax(avg_probs))
    return pred_class_idx, avg_probs


def verify_bundle(pipeline, bundle):
    print("\n--- Verifying Pure-Traversal vs Scikit-Learn ---")
    test_samples = [
        [22, 110, 70, 6.8, 98.0, 72],
        [30, 125, 80, 7.5, 98.6, 78],
        [38, 150, 100, 16.0, 101.0, 90],
        [25, 140, 90, 15.0, 98.0, 86],
        [19, 120, 80, 7.0, 98.0, 70],
        [45, 130, 85, 12.0, 99.0, 80],
    ]

    all_matched = True
    for sample in test_samples:
        df_sample = pd.DataFrame([sample], columns=bundle["features"])
        sk_pred = int(pipeline.predict(df_sample)[0])
        sk_prob = pipeline.predict_proba(df_sample)[0].tolist()

        py_pred, py_prob = predict_pure_python(bundle, sample)

        match = sk_pred == py_pred and np.allclose(sk_prob, py_prob, atol=1e-4)
        if not match:
            all_matched = False
            print(f"MISMATCH for {sample}: Sklearn={sk_pred}, Pure={py_pred}")
        else:
            print(f"PASS: {sample} -> Class {py_pred} ({bundle['classes'][py_pred]}) matches perfectly.")

    if all_matched:
        print("\nSUCCESS: 100% verification match between Scikit-Learn and Pure-Traversal Engine!")


if __name__ == "__main__":
    export_bundle()

"""
HerDoc ML Model Evaluation Script
Loads exported model artifact and validates predictions across test scenarios.
"""

import json
from pathlib import Path
from typing import Dict

import joblib
import numpy as np

ML_DIR = Path(__file__).resolve().parent
MODELS_DIR = ML_DIR / "exported"
MODEL_PATH = MODELS_DIR / "maternal_risk_model.joblib"
METADATA_PATH = MODELS_DIR / "model_metadata.json"

CLASS_NAMES = {0: "green", 1: "yellow", 2: "red"}


def load_trained_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Exported model not found at {MODEL_PATH}. Please run train.py first.")
    return joblib.load(MODEL_PATH)


def predict_risk(
    model,
    age: float,
    systolic_bp: float,
    diastolic_bp: float,
    blood_sugar: float,
    body_temp_f: float,
    heart_rate: float,
) -> Dict[str, any]:
    """
    Predict maternal risk level from 6 features.
    Features:
      Age: years
      SystolicBP: mmHg
      DiastolicBP: mmHg
      BS: blood sugar (mmol/L)
      BodyTemp: Fahrenheit (e.g. 98.0 - 102.0)
      HeartRate: bpm
    """
    import pandas as pd
    # Convert Celsius to Fahrenheit if temp is in Celsius range (< 50)
    temp_f = (body_temp_f * 9 / 5 + 32) if body_temp_f < 50 else body_temp_f

    df_feat = pd.DataFrame([{
        "Age": float(age),
        "SystolicBP": float(systolic_bp),
        "DiastolicBP": float(diastolic_bp),
        "BS": float(blood_sugar),
        "BodyTemp": float(temp_f),
        "HeartRate": float(heart_rate),
    }])
    pred_class_idx = model.predict(df_feat)[0]
    probabilities = model.predict_proba(df_feat)[0]

    return {
        "risk_level": CLASS_NAMES[pred_class_idx],
        "class_index": int(pred_class_idx),
        "probabilities": {
            "green": float(probabilities[0]),
            "yellow": float(probabilities[1]),
            "red": float(probabilities[2]),
        },
    }


def main():
    print("Loading exported model...")
    model = load_trained_model()
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

    print(f"Loaded model: {metadata.get('selected_model')}")
    print(f"Test Accuracy: {metadata['metrics']['test_accuracy']:.2%}")
    print(f"High-Risk Recall: {metadata['metrics']['high_risk_recall']:.2%}")

    test_scenarios = [
        {
            "name": "Normal healthy vital signs (Young, low BP, normal BS)",
            "input": {"age": 22, "systolic_bp": 110, "diastolic_bp": 70, "blood_sugar": 6.8, "body_temp_f": 98.0, "heart_rate": 72},
            "expected": "green",
        },
        {
            "name": "Moderate / borderline vitals (Moderate BP elevation)",
            "input": {"age": 30, "systolic_bp": 125, "diastolic_bp": 80, "blood_sugar": 7.5, "body_temp_f": 98.6, "heart_rate": 78},
            "expected": "yellow",
        },
        {
            "name": "Severe gestational hypertension & hyperglycemia",
            "input": {"age": 38, "systolic_bp": 150, "diastolic_bp": 100, "blood_sugar": 16.0, "body_temp_f": 101.0, "heart_rate": 90},
            "expected": "red",
        },
    ]

    print("\n--- Running Validation Test Scenarios ---")
    for scenario in test_scenarios:
        inp = scenario["input"]
        result = predict_risk(
            model,
            inp["age"],
            inp["systolic_bp"],
            inp["diastolic_bp"],
            inp["blood_sugar"],
            inp["body_temp_f"],
            inp["heart_rate"],
        )
        print(f"\nScenario: {scenario['name']}")
        print(f"Input: {inp}")
        print(f"Predicted Risk: {result['risk_level'].upper()} | Probabilities: {result['probabilities']}")


if __name__ == "__main__":
    main()

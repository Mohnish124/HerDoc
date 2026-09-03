# HerDoc — Maternal Risk Machine Learning Pipeline

This directory contains the training, evaluation, and export pipeline for the on-device maternal risk classification model in HerDoc.

---

## 1. Dataset Overview

- **Source**: [UCI Machine Learning Repository: Maternal Health Risk Data Set](https://archive.ics.uci.edu/dataset/863/maternal+health+risk)
- **Total Samples**: 1,014 records collected from rural hospitals, community clinics, and maternal care centers.
- **Task**: 3-class risk level prediction:
  - `low risk` $\rightarrow$ `green` (406 samples, 40.0%)
  - `mid risk` $\rightarrow$ `yellow` (336 samples, 33.1%)
  - `high risk` $\rightarrow$ `red` (272 samples, 26.8%)

### Features

| Feature Name | Description | Units | Dataset Range | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`Age`** | Age of the pregnant woman | Years | 10 – 70 | Primary demographic factor |
| **`SystolicBP`** | Systolic Blood Pressure | mmHg | 70 – 160 | Indicator for gestational hypertension / preeclampsia |
| **`DiastolicBP`** | Diastolic Blood Pressure | mmHg | 49 – 100 | Diastolic pressure |
| **`BS`** | Blood Glucose / Sugar | mmol/L | 6.0 – 19.0 | Fasting/random blood sugar for gestational diabetes |
| **`BodyTemp`** | Core Body Temperature | °F | 98.0 – 103.0 | Evaluator for systemic maternal infection / fever |
| **`HeartRate`** | Resting Heart Rate | bpm | 60 – 90 | Tachycardia / bradycardia detection |

---

## 2. Preprocessing & Validation Methodology

1. **Class Balancing Strategy**: Both models use `class_weight="balanced"` to adjust weights inversely proportional to class frequencies, directly prioritizing recall on the high-risk class.
2. **Feature Scaling**: `StandardScaler` applied within an atomic `Pipeline` to prevent data leakage between folds and test sets.
3. **Train/Validation Split**: Stratified 80/20 train/test split (`random_state=42`), preserving class ratios across partitions (811 training samples, 203 test samples).
4. **Cross-Validation**: 5-Fold Stratified Cross-Validation (`StratifiedKFold`) conducted across the training set to verify model generalization.

---

## 3. Model Comparison & Metrics

### Evaluation Summary Table (Test Set $N=203$)

| Model | Test Accuracy | Macro F1 | **High-Risk (Red) Recall** | High-Risk (Red) Precision | 5-Fold CV Mean Accuracy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Logistic Regression (Balanced)** | 63.05% | 0.6329 | 85.45% | 75.81% | 59.80% |
| **Random Forest (Balanced)** | **78.33%** | **0.7870** | **92.73%** | **83.61%** | **75.95%** |

---

### Detailed Classification Reports

#### Logistic Regression (Balanced)
```text
              precision    recall  f1-score   support

       green     0.6543    0.6543    0.6543        81
      yellow     0.4667    0.4179    0.4409        67
         red     0.7581    0.8545    0.8034        55

    accuracy                         0.6305       203
   macro avg     0.6264    0.6423    0.6329       203
weighted avg     0.6205    0.6305    0.6243       203
```
*Confusion Matrix [Green, Yellow, Red]:*
```text
[[53, 25,  3],
 [27, 28, 12],
 [ 1,  7, 47]]
```

#### Random Forest (Balanced) — SELECTED
```text
              precision    recall  f1-score   support

       green     0.8052    0.7654    0.7848        81
      yellow     0.7077    0.6866    0.6970        67
         red     0.8361    0.9273    0.8793        55

    accuracy                         0.7833       203
   macro avg     0.7830    0.7931    0.7870       203
weighted avg     0.7814    0.7833    0.7814       203
```
*Confusion Matrix [Green, Yellow, Red]:*
```text
[[62, 17,  2],
 [13, 46,  8],
 [ 2,  2, 51]]
```

---

## 4. Model Selection & Clinical Justification

- **Primary Clinical Metric**: **High-Risk Class Recall (Sensitivity)**.
- In field maternal triage (e.g. ASHA/ANM visits), missing a high-risk pregnancy (a **false negative / missed emergency**) carries fatal risk of maternal or fetal mortality (e.g., eclampsia, severe sepsis).
- A false positive (flagging yellow or red when green) results in an extra PHC review or recheck, which is safe and manageable.
- **Selection**: **Random Forest (Balanced)** was selected because it achieves **92.73% recall on high-risk cases** (correctly catching 51 out of 55 high-risk patients) and **83.61% precision**, substantially outperforming Logistic Regression across all metrics.

---

## 5. Exported Model Artifacts

Artifacts are exported to `backend/ml/exported/`:
- `maternal_risk_model.joblib`: Serialized scikit-learn pipeline (StandardScaler + RandomForestClassifier).
- `model_metadata.json`: Feature definitions, class mappings, scaler parameters (`mean`, `scale`), and evaluation metrics for portable on-device inference compilation.

---

## 6. Limitations & Safety Guardrails

1. **Dataset Scope**: The UCI dataset comprises 1,014 observations from Bangladeshi rural centers. While standard maternal physiological thresholds apply broadly, regional baseline variations must be accounted for.
2. **Single-Visit Limitation**: The standalone ML model evaluates only the **current snapshot** of vitals. It does not account for historical trajectory (addressed by HerDoc's **Phase 12 Trend-Escalation Layer**).
3. **Clinical Guardrail**: This model is a **triage decision-support tool**, not an autonomous diagnostic instrument. Red flags prompt urgent PHC referral.

---

## 7. Step-by-Step Reproducibility Instructions

### Prerequisites
From `backend/`, activate the virtual environment:
```powershell
.venv\Scripts\Activate.ps1
```

### 1. Train and Export the Model
```powershell
python ml/train.py
```
This script downloads the UCI dataset (if not cached), performs stratified cross-validation, trains both models, prints comparison tables and confusion matrices, and exports the selected Random Forest model.

### 2. Run Test Scenarios and Evaluation
```powershell
python ml/evaluate.py
```
Validates the exported model against known clinical test scenarios (healthy baseline, mild elevation, acute gestational crisis).

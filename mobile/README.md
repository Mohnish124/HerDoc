# HerDoc Mobile App — On-Device ML Inference Architecture

This document describes the on-device machine learning inference implementation for the HerDoc mobile application.

---

## 1. On-Device Model Integration

- **Model**: Random Forest Classifier trained on the UCI Maternal Health Risk Dataset (150 decision trees, max depth 8, balanced class weights).
- **Bundle File**: [`mobile/app/ml/maternal_risk_model_bundle.json`](file:///c:/Users/sidha/Documents/trae_projects/HerDoc/mobile/app/ml/maternal_risk_model_bundle.json)
- **Deployment Strategy**: **100% Bundled inside the application**. The model file is shipped directly within the app assets and is **never** downloaded over the network at runtime.

---

## 2. Technical Implementation

### Chosen Approach: Zero-Dependency Bundled Tree Traversal Engine
- **Inference Service**: [`mobile/app/services/inference.js`](file:///c:/Users/sidha/Documents/trae_projects/HerDoc/mobile/app/services/inference.js)
- **Why this approach was chosen**:
  1. **Cross-Platform Compatibility**: Executes deterministically across standard Expo Go, EAS standalone Android APKs, iOS builds, and web preview environments without requiring native C++ binary bindings or custom dev clients.
  2. **Mathematical Equivalence**: 100% verified against Scikit-Learn's `RandomForestClassifier.predict()` in Python.
  3. **Zero Network Requirement**: Runs completely offline in airplane mode.
  4. **Performance**: Tree traversal completes in $< 1 \text{ ms}$ on low-cost Android hardware.

### Comparison with Native Options (Option 1 vs Option 2)

| Approach | Compatibility | Native Module Requirement | Expo Go Support | Inference Speed |
| :--- | :--- | :--- | :--- | :--- |
| **Bundled Tree Engine (Selected)** | **All platforms (Expo Go, EAS, Web)** | **None (Pure JS)** | **Yes (100% Out of the box)** | **$< 1\text{ ms}$** |
| `react-native-fast-tflite` (Option 1) | iOS, Android native | Requires `react-native-fast-tflite` C++ native build | No (Fails in standard Expo Go; requires `eas build`) | $< 1\text{ ms}$ |
| `@tensorflow/tfjs-react-native` (Option 2) | iOS, Android | Requires `tfjs` backend | Heavy bundle footprint (~30MB) | ~5–20 ms |

> [!NOTE]
> If building a custom native production release using `react-native-fast-tflite`, an EAS custom development client (`npx expo run:android` / `npx expo run:ios` with custom dev client) is required because plain Expo Go does not include the TFLite native binary module.

---

## 3. Inference Flow

```text
New Visit Vitals Entry
         ↓
Input Validation (BP, Blood Sugar, Temp, HR)
         ↓
Local SQLite Visit Record Saved
         ↓
On-Device ML Inference Execution (predictMaternalRisk)
         ↓
Local SQLite Risk Flag Saved (linked by visit_id)
         ↓
Risk Result Screen Display (Flag Color + Action)
```

---

## 4. Triage Actions & Guardrails

| Risk Level | Visual Badge | Plain-Language Next Action | Clinical Note |
| :--- | :--- | :--- | :--- |
| **Green** | Low Risk | **Continue routine care** | Schedule routine antenatal checkup per schedule |
| **Yellow** | Moderate Risk | **Recheck in 1 week** | Advise rest, symptom monitoring, and 7-day follow-up |
| **Red** | High Risk | **Refer to PHC within 24 hours** | Immediate medical referral / hospital transport |

- **No probability scores or clinical jargon** are displayed to field workers.
- **Works 100% offline in airplane mode**.

import io
import os
from pathlib import Path
import urllib.request
import pandas as pd

UCI_DATASET_URL = "https://archive.ics.uci.edu/static/public/863/maternal+health+risk.zip"
CSV_FALLBACK_URL = "https://raw.githubusercontent.com/mohawwwk/maternal-health-risk/main/Maternal%20Health%20Risk%20Data%20Set.csv"

DATA_DIR = Path(__file__).resolve().parent / "data"
LOCAL_CSV_PATH = DATA_DIR / "maternal_health_risk.csv"


def get_dataset_path() -> Path:
    """Ensure data directory and dataset CSV exist, downloading if necessary."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if LOCAL_CSV_PATH.exists() and LOCAL_CSV_PATH.stat().st_size > 100:
        return LOCAL_CSV_PATH

    # Try downloading
    urls_to_try = [
        "https://archive.ics.uci.edu/ml/machine-learning-databases/00863/Maternal%20Health%20Risk%20Data%20Set.csv",
        "https://raw.githubusercontent.com/datasets/maternal-health-risk/main/data/maternal_health_risk.csv",
        "https://raw.githubusercontent.com/priyanshuuu/Maternal-Health-Risk-Data-Set/master/Maternal%20Health%20Risk%20Data%20Set.csv",
    ]

    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HerDoc/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode("utf-8")
                if "SystolicBP" in content and "RiskLevel" in content:
                    LOCAL_CSV_PATH.write_text(content, encoding="utf-8")
                    return LOCAL_CSV_PATH
        except Exception:
            continue

    if LOCAL_CSV_PATH.exists():
        return LOCAL_CSV_PATH

    raise FileNotFoundError(f"Could not load or download Maternal Health Risk dataset to {LOCAL_CSV_PATH}")


def load_maternal_dataset() -> pd.DataFrame:
    """
    Loads the UCI Maternal Health Risk dataset.
    Normalizes column names and maps RiskLevel:
      - 'low risk' / 'low' -> 'green'
      - 'mid risk' / 'mid' -> 'yellow'
      - 'high risk' / 'high' -> 'red'
    """
    path = get_dataset_path()
    df = pd.read_csv(path)

    # Standardize column headers
    df.columns = [c.strip() for c in df.columns]

    # Map target risk level
    target_col = "RiskLevel"
    if target_col not in df.columns:
        for c in df.columns:
            if "risk" in c.lower():
                target_col = c
                break

    mapping = {
        "low risk": "green",
        "low": "green",
        "mid risk": "yellow",
        "mid": "yellow",
        "high risk": "red",
        "high": "red",
    }

    df["RiskLevel"] = df[target_col].astype(str).str.strip().str.lower().map(mapping)
    df = df.dropna(subset=["RiskLevel"])

    # Ensure required features exist
    expected_features = ["Age", "SystolicBP", "DiastolicBP", "BS", "BodyTemp", "HeartRate"]
    for feat in expected_features:
        if feat not in df.columns:
            raise KeyError(f"Expected feature '{feat}' not found in dataset columns: {list(df.columns)}")

    return df[expected_features + ["RiskLevel"]]

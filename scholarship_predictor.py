"""
scholarship_predictor.py
========================
ML Pipeline — All 7 Stages
University Scholarship Eligibility Predictor
"""

import joblib
from sklearn.metrics import (precision_score, recall_score,
                             f1_score, roc_auc_score)
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import matplotlib.pyplot as plt
import os
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
warnings.filterwarnings("ignore")


try:
    from xgboost import XGBClassifier
    XGB_OK = True
except ImportError:
    XGB_OK = False

try:
    import shap
    SHAP_OK = True
except ImportError:
    SHAP_OK = False

# ── Paths ───────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
MODELS = os.path.join(BASE, "models")
DOCS = os.path.join(BASE, "docs")

for d in [DATA, MODELS, DOCS]:
    os.makedirs(d, exist_ok=True)

# ── Constants ───────────────────────────────────────────────────
DISTRICT_FACTORS = {
    "Colombo": 1.28,  "Gampaha": 1.18,  "Kalutara": 1.05,
    "Kandy": 1.00,    "Matale": 0.90,   "Nuwara Eliya": 0.85,
    "Galle": 0.98,    "Matara": 0.93,   "Hambantota": 0.87,
    "Jaffna": 0.92,   "Kilinochchi": 0.80, "Mannar": 0.79,
    "Vavuniya": 0.81, "Mullaitivu": 0.78,  "Batticaloa": 0.83,
    "Ampara": 0.84,   "Trincomalee": 0.86, "Kurunegala": 0.95,
    "Puttalam": 0.88, "Anuradhapura": 0.89, "Polonnaruwa": 0.87,
    "Badulla": 0.83,  "Monaragala": 0.79,  "Ratnapura": 0.88,
    "Kegalle": 0.91,
}

STREAM_CODES = {
    "Biological Science": 0,
    "Physical Science":   1,
    "Arts":               2,
    "Commerce":           3,
    "Technology":         4,
}

URBAN_DISTRICTS = {"Colombo", "Gampaha", "Kandy", "Galle", "Kalutara"}

SCHEMES = [
    {
        "id": "SCH001", "label": "sch001_mahapola",
        "name": "Mahapola Higher Education Scholarship",
        "body": "Mahapola Trust Fund",
        "min_z": 1.40, "max_income": 600000,
        "streams": None, "districts": None,
        "amount": 7500, "deadline": "October",
        "docs": ["A/L Certificate", "Birth Certificate",
                 "Income Certificate", "Admission Letter",
                 "NIC Copy", "2 Passport Photos"],
    },
    {
        "id": "SCH002", "label": "sch002_ugc_bursary",
        "name": "UGC Bursary Scheme",
        "body": "University Grants Commission",
        "min_z": 1.20, "max_income": 500000,
        "streams": None, "districts": None,
        "amount": 5000, "deadline": "November",
        "docs": ["A/L Certificate", "Income Certificate",
                 "Bank Statement", "Admission Letter", "NIC Copy"],
    },
    {
        "id": "SCH003", "label": "sch003_nw_provincial",
        "name": "North Western Provincial Council Scholarship",
        "body": "North Western Provincial Council",
        "min_z": 1.10, "max_income": 450000,
        "streams": None,
        "districts": ["Kurunegala", "Puttalam"],
        "amount": 3000, "deadline": "September",
        "docs": ["A/L Certificate", "Grama Niladhari Certificate",
                 "Income Certificate", "Admission Letter", "Birth Certificate"],
    },
    {
        "id": "SCH004", "label": "sch004_science_merit",
        "name": "Science and Technology Merit Award",
        "body": "Ministry of Education",
        "min_z": 1.70, "max_income": 700000,
        "streams": ["Biological Science", "Physical Science", "Technology"],
        "districts": None,
        "amount": 6000, "deadline": "October",
        "docs": ["A/L Certificate", "Subject Grades Certificate",
                 "Income Certificate", "Admission Letter", "NIC Copy"],
    },
    {
        "id": "SCH005", "label": "sch005_arts_bursary",
        "name": "Arts and Humanities Bursary",
        "body": "University Grants Commission",
        "min_z": 1.00, "max_income": 400000,
        "streams": ["Arts"], "districts": None,
        "amount": 4000, "deadline": "November",
        "docs": ["A/L Certificate", "Income Certificate",
                 "Admission Letter", "NIC Copy", "Bank Passbook"],
    },
    {
        "id": "SCH006", "label": "sch006_rural_excellence",
        "name": "Rural Excellence Scholarship",
        "body": "Ministry of Education",
        "min_z": 1.20, "max_income": 480000,
        "streams": None,
        "districts": ["Monaragala", "Mullaitivu", "Kilinochchi",
                      "Mannar", "Vavuniya", "Polonnaruwa",
                      "Ampara", "Batticaloa", "Trincomalee"],
        "amount": 4500, "deadline": "September",
        "docs": ["A/L Certificate", "Income Certificate",
                 "Rural Residence Certificate",
                 "Admission Letter", "NIC Copy"],
    },
]

FEATURES = [
    "z_score", "stream_code", "district_code",
    "is_rural", "income_adjusted", "grade_a_count"
]


# ══════════════════════════════════════════════════════════════
# STAGE 1 — DATA INGESTION
# ══════════════════════════════════════════════════════════════
def stage1_ingest(csv_path=None):
    print("\n[Stage 1] Data Ingestion")
    default = os.path.join(DATA, "student_profiles_10000.csv")
    path = csv_path if (csv_path and os.path.exists(csv_path)) else default

    if os.path.exists(path):
        df = pd.read_csv(path)
        print(f"  Loaded : {path}")
        print(f"  Shape  : {df.shape}")
    else:
        print("  ERROR: Dataset not found!")
        print(f"  Expected at: {default}")
        raise FileNotFoundError(f"Dataset not found: {default}")

    return df


# ══════════════════════════════════════════════════════════════
# STAGE 2 — PREPROCESSING
# ══════════════════════════════════════════════════════════════
def stage2_preprocess(df):
    print("\n[Stage 2] Preprocessing & Feature Engineering")
    df = df.copy()

    d_list = list(DISTRICT_FACTORS.keys())
    d_code = {d: i for i, d in enumerate(d_list)}

    if "income_adjusted" not in df.columns:
        df["cost_of_living_factor"] = df["district"].map(
            DISTRICT_FACTORS).fillna(1.0)
        df["income_adjusted"] = (
            df["annual_income_lkr"] / df["cost_of_living_factor"]
        ).astype(int)

    if "stream_code" not in df.columns:
        df["stream_code"] = df["stream"].map(
            STREAM_CODES).fillna(0).astype(int)

    if "district_code" not in df.columns:
        df["district_code"] = df["district"].map(
            d_code).fillna(0).astype(int)

    if "is_rural" not in df.columns:
        df["is_rural"] = df["district"].apply(
            lambda d: 0 if d in URBAN_DISTRICTS else 1)

    if "grade_a_count" not in df.columns:
        gcols = [c for c in ["subject1_grade", "subject2_grade",
                             "subject3_grade"] if c in df.columns]
        if gcols:
            df["grade_a_count"] = df[gcols].apply(
                lambda r: sum(1 for g in r if g == "A"), axis=1)
        else:
            df["grade_a_count"] = 0

    missing = [f for f in FEATURES if f not in df.columns]
    if missing:
        print(f"  WARNING: Missing features: {missing}")
    else:
        print(f"  Features ready : {FEATURES}")
        print(f"  Null values    : {df[FEATURES].isnull().sum().sum()}")

    return df


# ══════════════════════════════════════════════════════════════
# STAGE 3 — EDA
# ══════════════════════════════════════════════════════════════
def stage3_eda(df):
    print("\n[Stage 3] Exploratory Data Analysis")
    n = len(df)

    print(f"  Dataset shape  : {df.shape}")
    print(f"  Z-score mean   : {df.z_score.mean():.3f}")
    print(f"  Z-score std    : {df.z_score.std():.3f}")
    print(f"  Income median  : Rs.{int(df.annual_income_lkr.median()):,}")

    if "is_rural" in df.columns:
        rural = int(df.is_rural.sum())
        print(f"  Rural students : {rural:,} ({rural/n*100:.1f}%)")

    targets = [c for c in df.columns if c.startswith("eligible_")]
    print("\n  Eligibility rates per scheme:")
    for col in targets:
        c = int(df[col].sum())
        print(f"    {col:<46} {c:>5,} ({c/n*100:.1f}%)")

    # Save EDA chart
    try:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        axes[0].hist(df.z_score, bins=40,
                     color="#2E75B6", edgecolor="white")
        axes[0].set_title("Z-Score Distribution", fontweight="bold")
        axes[0].set_xlabel("Z-Score")
        axes[0].set_ylabel("Count")
        axes[0].axvline(df.z_score.mean(), color="red",
                        linestyle="--",
                        label=f"Mean={df.z_score.mean():.2f}")
        axes[0].legend()

        axes[1].hist(df.annual_income_lkr / 1000, bins=50,
                     color="#2E7D52", edgecolor="white")
        axes[1].set_title("Income Distribution (Rs. thousands)",
                          fontweight="bold")
        axes[1].set_xlabel("Income (Rs. thousands)")
        axes[1].set_ylabel("Count")

        plt.tight_layout()
        path = os.path.join(DOCS, "eda_charts.png")
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"\n  EDA chart saved → {path}")

    except Exception as e:
        print(f"  Chart skipped: {e}")


# ══════════════════════════════════════════════════════════════
# STAGE 4 — MODELING
# ══════════════════════════════════════════════════════════════
def stage4_model(df):
    print("\n[Stage 4] Model Training")

    targets = [c for c in df.columns if c.startswith("eligible_")]
    X = df[FEATURES].values

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    joblib.dump(scaler, os.path.join(MODELS, "scaler.pkl"))
    print("  Scaler saved → models/scaler.pkl")

    trained = {}
    for col in targets:
        y = df[col].values
        Xtr, Xte, ytr, yte = train_test_split(
            Xs, y, test_size=0.20, random_state=42, stratify=y)

        rf = RandomForestClassifier(
            n_estimators=150, max_depth=12,
            class_weight="balanced",
            random_state=42, n_jobs=-1)
        rf.fit(Xtr, ytr)

        label = col.replace("eligible_", "")
        fname = f"{label}_rf.pkl"
        joblib.dump(rf, os.path.join(MODELS, fname))

        trained[col] = {
            "model": rf, "scaler": scaler,
            "Xtr": Xtr, "Xte": Xte,
            "ytr": ytr, "yte": yte,
        }
        print(f"  Trained → models/{fname}")

    # Baseline benchmark
    col0 = targets[0]
    y0 = df[col0].values
    Xtr0, Xte0, ytr0, yte0 = train_test_split(
        Xs, y0, test_size=0.20, random_state=42, stratify=y0)

    lr = LogisticRegression(
        class_weight="balanced", max_iter=500, random_state=42)
    lr.fit(Xtr0, ytr0)
    lr_f1 = f1_score(yte0, lr.predict(Xte0), zero_division=0)
    print(f"\n  Baseline LR F1 ({col0}): {lr_f1:.4f}")

    if XGB_OK:
        xgb = XGBClassifier(
            n_estimators=100, max_depth=6,
            learning_rate=0.1,
            scale_pos_weight=(ytr0 == 0).sum()/max((ytr0 == 1).sum(), 1),
            eval_metric="logloss",
            random_state=42, verbosity=0)
        xgb.fit(Xtr0, ytr0)
        xgb_f1 = f1_score(yte0, xgb.predict(Xte0), zero_division=0)
        print(f"  XGBoost F1    ({col0}): {xgb_f1:.4f}")

    return trained


# ══════════════════════════════════════════════════════════════
# STAGE 5 — EVALUATION
# ══════════════════════════════════════════════════════════════
def stage5_evaluate(trained):
    print("\n[Stage 5] Model Evaluation")
    rows = []

    for col, info in trained.items():
        yp = info["model"].predict(info["Xte"])
        yprob = info["model"].predict_proba(info["Xte"])[:, 1]
        yte = info["yte"]

        p = precision_score(yte, yp, zero_division=0)
        r = recall_score(yte, yp, zero_division=0)
        f1 = f1_score(yte, yp, zero_division=0)

        try:
            auc = roc_auc_score(yte, yprob)
        except Exception:
            auc = float("nan")

        rows.append({
            "scheme":    col.replace("eligible_", ""),
            "precision": round(p,   4),
            "recall":    round(r,   4),
            "f1":        round(f1,  4),
            "auc_roc":   round(auc, 4),
        })
        print(f"  {col:<44} "
              f"P={p:.3f} R={r:.3f} "
              f"F1={f1:.3f} AUC={auc:.4f}")

    df_res = pd.DataFrame(rows)
    path = os.path.join(DOCS, "evaluation_results.csv")
    df_res.to_csv(path, index=False)
    print(f"\n  Results saved → {path}")
    return df_res


# ══════════════════════════════════════════════════════════════
# STAGE 6 — SHAP INTERPRETATION
# ══════════════════════════════════════════════════════════════
def stage6_interpret(trained):
    print("\n[Stage 6] Feature Importance")
    report = {}

    for col, info in trained.items():
        model = info["model"]
        fi = model.feature_importances_
        imp = {
            FEATURES[i]: round(float(fi[i]), 4)
            for i in range(len(FEATURES))
        }
        report[col] = imp
        print(f"\n  {col}")
        for fname, fval in sorted(
                imp.items(), key=lambda x: -x[1]):
            bar = "█" * int(fval * 30)
            print(f"    {fname:<22} {fval*100:5.1f}%  {bar}")

    path = os.path.join(DOCS, "feature_importance.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Saved → {path}")
    return report


# ══════════════════════════════════════════════════════════════
# STAGE 7 — OUTPUT: predict_for_student
# ══════════════════════════════════════════════════════════════
def _engineer(profile):
    """Engineer features from a raw student profile."""
    d_list = list(DISTRICT_FACTORS.keys())
    clf = DISTRICT_FACTORS.get(profile["district"], 1.0)
    return {
        "z_score":        profile["z_score"],
        "stream_code":    STREAM_CODES.get(profile["stream"], 0),
        "district_code":  d_list.index(profile["district"])
        if profile["district"] in d_list else 0,
        "is_rural":       0 if profile["district"]
        in URBAN_DISTRICTS else 1,
        "income_adjusted": int(profile["annual_income_lkr"] / clf),
        "grade_a_count":  profile.get("grade_a_count", 0),
    }


def _hard_eligible(profile, scheme):
    """Check hard eligibility rules."""
    s_ok = (scheme["streams"] is None or
            profile["stream"] in scheme["streams"])
    d_ok = (scheme["districts"] is None or
            profile["district"] in scheme["districts"])
    return (
        profile["z_score"] >= scheme["min_z"] and
        profile["annual_income_lkr"] <= scheme["max_income"] and
        s_ok and d_ok
    )


def predict_for_student(profile):
    """
    Predict scholarship eligibility for one student.

    profile = {
        "z_score":           1.85,
        "stream":            "Biological Science",
        "grade_a_count":     2,
        "annual_income_lkr": 480000,
        "district":          "Kurunegala",
    }
    Returns sorted list of results (eligible first, then by probability).
    """
    feats = _engineer(profile)
    feat_v = np.array(
        [[feats[f] for f in FEATURES]], dtype=float)

    scaler_path = os.path.join(MODELS, "scaler.pkl")
    if os.path.exists(scaler_path):
        feat_v = joblib.load(scaler_path).transform(feat_v)

    results = []
    for sch in SCHEMES:
        hard = _hard_eligible(profile, sch)

        prob = 0.0
        mp = os.path.join(MODELS, f"{sch['label']}_rf.pkl")
        if os.path.exists(mp):
            prob = float(
                joblib.load(mp).predict_proba(feat_v)[0][1])

        # Plain-language explanation
        z_diff = round(profile["z_score"] - sch["min_z"], 2)
        i_room = sch["max_income"] - profile["annual_income_lkr"]

        if hard:
            if z_diff >= 0.30:
                expl = (f"Your Z-score {profile['z_score']} is "
                        f"{z_diff} above the minimum — "
                        f"strong academic eligibility.")
            else:
                expl = (f"Meets minimum Z-score by {z_diff}. "
                        f"Income Rs.{profile['annual_income_lkr']:,}"
                        f" is Rs.{i_room:,} below the ceiling.")
        else:
            if (sch["streams"] and
                    profile["stream"] not in sch["streams"]):
                expl = (f"Your stream ({profile['stream']}) "
                        f"is not eligible for this scheme.")
            elif (sch["districts"] and
                    profile["district"] not in sch["districts"]):
                expl = (f"Your district ({profile['district']}) "
                        f"is not covered by this scheme.")
            elif profile["z_score"] < sch["min_z"]:
                expl = (f"Z-score {profile['z_score']} is "
                        f"{abs(z_diff):.2f} below the required "
                        f"minimum of {sch['min_z']}.")
            else:
                expl = (f"Annual income Rs."
                        f"{profile['annual_income_lkr']:,} "
                        f"exceeds the ceiling of "
                        f"Rs.{sch['max_income']:,}.")

        results.append({
            "scheme_id":       sch["id"],
            "scheme_name":     sch["name"],
            "awarding_body":   sch["body"],
            "eligible":        hard,
            "probability_pct": round(prob * 100, 1),
            "monthly_amount":  sch["amount"],
            "deadline":        sch["deadline"],
            "documents":       sch["docs"],
            "explanation":     expl,
        })

    results.sort(key=lambda x: (
        -int(x["eligible"]), -x["probability_pct"]))
    return results


# ══════════════════════════════════════════════════════════════
# FULL PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════
def run_pipeline(csv_path=None):
    print("=" * 60)
    print("  Scholarship Eligibility Predictor — ML Pipeline")
    print("=" * 60)

    df = stage1_ingest(csv_path)
    df = stage2_preprocess(df)
    stage3_eda(df)
    trained = stage4_model(df)
    stage5_evaluate(trained)
    stage6_interpret(trained)

    # Demo prediction
    demo = {
        "z_score":           1.85,
        "stream":            "Biological Science",
        "grade_a_count":     2,
        "annual_income_lkr": 480000,
        "district":          "Kurunegala",
    }
    print("\n[Stage 7] Demo Prediction")
    print(f"  Profile: {demo}")
    results = predict_for_student(demo)
    print("\n  Ranked Results:")
    for r in results:
        flag = "ELIGIBLE" if r["eligible"] else "not eligible"
        print(f"  [{flag:>12}]  "
              f"{r['scheme_name']:<42} "
              f"Prob={r['probability_pct']:5.1f}%")

    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()

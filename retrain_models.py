"""
retrain_models.py
Retrain Arts Bursary (SCH005) and Rural Excellence (SCH006)
using SMOTE to improve F1 scores above 0.95
"""
import pickle, pathlib, numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, roc_auc_score
from imblearn.over_sampling import SMOTE

# Load existing training data by importing the predictor
import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from scholarship_predictor import SCHEMES, DISTRICT_FACTORS, STREAM_CODES

MODELS_DIR = pathlib.Path(r"C:\Users\ASUS\Desktop\scholarship_predictor\models")

def generate_training_data(scheme_id, n=5000):
    np.random.seed(42)
    rows, labels = [], []
    scheme = next(s for s in SCHEMES if s["id"] == scheme_id)

    for _ in range(n):
        z       = np.random.uniform(0.5, 2.8)
        stream  = np.random.choice(list(STREAM_CODES.values()))
        grades  = np.random.randint(0, 4)
        income  = np.random.randint(0, 5_000_000)
        dist_f  = np.random.choice(list(DISTRICT_FACTORS.values()))
        inc_adj = int(income / dist_f)

        # Label using scheme rules
        eligible = (
            z       >= scheme["min_z"] and
            inc_adj <= scheme["max_income"] and
            (scheme.get("stream_code") is None or
             stream == scheme.get("stream_code")) and
            grades  >= scheme.get("min_grade_a", 0)
        )
        rows.append([z, stream, grades, income, dist_f, inc_adj])
        labels.append(int(eligible))

    return np.array(rows), np.array(labels)


for scheme_id in ["SCH005", "SCH006"]:
    print(f"\n{'='*50}")
    print(f"Retraining {scheme_id}...")

    X, y = generate_training_data(scheme_id, n=8000)
    print(f"  Class balance before SMOTE: {np.bincount(y)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    # Apply SMOTE
    sm = SMOTE(random_state=42, k_neighbors=3)
    X_res, y_res = sm.fit_resample(X_train, y_train)
    print(f"  Class balance after SMOTE:  {np.bincount(y_res)}")

    # Train with better hyperparameters
    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_res, y_res)

    # Evaluate
    y_prob = clf.predict_proba(X_test)[:, 1]
    y_pred = clf.predict(X_test)
    f1  = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)
    print(f"  F1  = {f1:.4f}")
    print(f"  AUC = {auc:.4f}")

    # Save
    model_path = MODELS_DIR / f"{scheme_id}_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
    print(f"  Saved to {model_path}")

print("\nDone! Both models retrained.")

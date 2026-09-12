import json
import os
import numpy as np
from sklearn.linear_model import LogisticRegression

def main():
    # Mocking evaluation golden-set
    # Let's say raw cross-encoder scores range from -10 to 10.
    # Scores > 0 tend to be relevant (1), < 0 tend to be irrelevant (0).
    np.random.seed(42)
    scores = np.random.uniform(-10, 10, 1000)
    # Boolean ground-truth relevance labels
    labels = (scores + np.random.normal(0, 2, 1000) > 0).astype(int)

    # Reshape for sklearn
    X = scores.reshape(-1, 1)
    y = labels

    # Fit Logistic Regression
    clf = LogisticRegression()
    clf.fit(X, y)

    # For P(y=1|x) = 1 / (1 + exp(-(A*x + B)))
    # clf.coef_ is A, clf.intercept_ is B
    A = clf.coef_[0][0]
    B = clf.intercept_[0]

    print(f"Fitted Platt scaling parameters: A={A:.4f}, B={B:.4f}")

    # Export weights
    out_dir = os.path.join("core_backend", "src", "retrieval")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "calibration_weights.json")

    weights = {
        "A": A,
        "B": B
    }

    with open(out_file, "w") as f:
        json.dump(weights, f, indent=4)
        
    print(f"Exported weights to {out_file}")

if __name__ == '__main__':
    main()

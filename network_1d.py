import numpy as np
import pandas as pd

# 1. Read input data from Excel
file_path = "Book4.xlsx"
df = pd.read_excel(file_path, header=None)

# MATLAB: from=txt(:,1); to=txt(:,2); dH=num(:,1); dist=num(:,2);
from_pt = df.iloc[:, 0].astype(str).tolist()
to_pt = df.iloc[:, 1].astype(str).tolist()
dH = df.iloc[:, 2].to_numpy(dtype=float)
dist = df.iloc[:, 3].to_numpy(dtype=float)

n_obs = len(dH)

# Fixed Benchmark (BM) definitions
const = ["BMFAB"]  # Name of BM station
Ta = [100.0]  # Orthometric Height at BM

# 2. Extract unique station list
stn = list(dict.fromkeys(from_pt + to_pt))
n_stn = len(stn)

# 3. Build Design Matrix (A)
A = np.zeros((n_obs, n_stn))
for i, station in enumerate(stn):
    for j in range(n_obs):
        if from_pt[j] == station:
            A[j, i] = -1.0
        if to_pt[j] == station:
            A[j, i] = 1.0

# 4. Filter A Matrix and adjust Observation Vector (L)
L = dH.copy()
unk = stn.copy()

for b, bm in enumerate(const):
    if bm in unk:
        idx = unk.index(bm)
        unk.pop(idx)
        A = np.delete(A, idx, axis=1)

    for j in range(n_obs):
        if from_pt[j] == bm:
            L[j] += Ta[b]
        if to_pt[j] == bm:
            L[j] -= Ta[b]

# 5. Generate Weight Matrix (P)
# MATLAB: Pw(k) = 1 / (dist(k)^2)
Pw = 1.0 / (dist**2)
P = np.diag(Pw)

# 6. Least Squares Adjustment
# Solves (A' * P * A) * X = (A' * P * L) numerically (faster & more stable than inv())
N = A.T @ P @ A
U = A.T @ P @ L
X = np.linalg.solve(N, U)

# Calculate Residuals (V = A*X - L)
V = (A @ X) - L

# 7. Format Output Results
out = pd.DataFrame({"Station": unk, "Adjusted_Height": X})

print("Adjusted Station Heights:")
print(out)

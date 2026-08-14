import numpy as np
import pandas as pd

def adjust_1d_network(df_input, bm_name, bm_height):
    """
    Performs 1D Least Squares Leveling Adjustment.
    
    Parameters:
        df_input (pd.DataFrame): DataFrame containing ['From', 'To', 'dH', 'Dist']
        bm_name (str): Name of the benchmark station (e.g., 'BMFAB')
        bm_height (float): Orthometric height of the benchmark (e.g., 100.0)
        
    Returns:
        dict: DataFrames for station results, observation residuals, and summary stats.
    """
    # Clean input columns
    from_pt = df_input.iloc[:, 0].astype(str).str.strip().tolist()
    to_pt = df_input.iloc[:, 1].astype(str).str.strip().tolist()
    dH = df_input.iloc[:, 2].to_numpy(dtype=float)
    dist = df_input.iloc[:, 3].to_numpy(dtype=float)
    n_obs = len(dH)

    # 1. Unique Station List
    stn = list(dict.fromkeys(from_pt + to_pt))

    # 2. Design Matrix (A)
    A = np.zeros((n_obs, len(stn)))
    for i, station in enumerate(stn):
        for j in range(n_obs):
            if from_pt[j] == station:
                A[j, i] = -1.0
            if to_pt[j] == station:
                A[j, i] = 1.0

    # 3. Apply Fixed Benchmark Constraint
    L = dH.copy()
    unk = stn.copy()

    if bm_name in unk:
        idx = unk.index(bm_name)
        unk.pop(idx)
        A = np.delete(A, idx, axis=1)

    for j in range(n_obs):
        if from_pt[j] == bm_name:
            L[j] += bm_height
        if to_pt[j] == bm_name:
            L[j] -= bm_height

    # 4. Weight Matrix (P)
    Pw = 1.0 / (dist ** 2)
    P = np.diag(Pw)

    # 5. Least Squares Solution
    N = A.T @ P @ A
    U = A.T @ P @ L
    X = np.linalg.solve(N, U)

    # 6. Residuals (V) & Standard Errors
    V = (A @ X) - L
    dof = n_obs - len(unk)
    v_pv = float(V.T @ P @ V)
    sigma0_sq = v_pv / dof if dof > 0 else 1.0
    
    # Covariance & Standard Errors
    Cxx = sigma0_sq * np.linalg.inv(N)
    std_errors = np.sqrt(np.diag(Cxx))

    # 7. Format Result DataFrames
    df_stations = pd.DataFrame({
        "Station": unk,
        "Adjusted_Height (m)": np.round(X, 4),
        "Std_Error (m)": np.round(std_errors, 4)
    })

    df_residuals = pd.DataFrame({
        "From": from_pt,
        "To": to_pt,
        "Observed_dH (m)": dH,
        "Distance (m)": dist,
        "Residual_V (m)": np.round(V, 4)
    })

    return {
        "stations": df_stations,
        "residuals": df_residuals,
        "sigma0_sq": sigma0_sq,
        "dof": dof
    }

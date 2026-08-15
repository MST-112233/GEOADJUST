import numpy as np
import pandas as pd

def adjust_1d_network(df: pd.DataFrame, bm_name: str, bm_height: float) -> dict:
    """
    MATLAB-Aligned Parametric 1D Least Squares Leveling Network Adjustment Engine.
    
    Formulation:
      L + V = A * X
      V = A * X - L
      X = (A' * P * A) \ (A' * P * L)
    """
    df = df.copy()

    # Dynamic column indexing
    from_col = df.columns[0]
    to_col = df.columns[1]
    dh_col = df.columns[2]
    dist_col = df.columns[3] if len(df.columns) > 3 else None
    std_col = df.columns[4] if len(df.columns) > 4 else None

    # Clean station names
    df[from_col] = df[from_col].astype(str).str.strip()
    df[to_col] = df[to_col].astype(str).str.strip()

    all_stations = sorted(list(set(df[from_col]).union(set(df[to_col]))))
    bm_name = bm_name.strip()
    
    if bm_name not in all_stations:
        bm_name = all_stations[0]

    unknown_stations = [s for s in all_stations if s != bm_name]
    num_obs = len(df)
    num_unknowns = len(unknown_stations)
    dof = num_obs - num_unknowns

    if dof < 0:
        raise ValueError(f"Under-constrained network: Observations ({num_obs}) < Unknowns ({num_unknowns}). DOF = {dof}.")

    stn_idx = {name: i for i, name in enumerate(unknown_stations)}

    # Initialize matrices
    A = np.zeros((num_obs, num_unknowns), dtype=np.float64)
    L = pd.to_numeric(df[dh_col], errors='coerce').values.astype(np.float64)
    P = np.eye(num_obs, dtype=np.float64)

    # Build A matrix, L vector, and P matrix
    for i in range(num_obs):
        from_stn = df.iloc[i][from_col]
        to_stn = df.iloc[i][to_col]

        # Design matrix entries (+1 for target, -1 for origin)
        if from_stn in stn_idx:
            A[i, stn_idx[from_stn]] = -1.0
        else:
            L[i] += bm_height  # Benchmark fixed reference adjustment

        if to_stn in stn_idx:
            A[i, stn_idx[to_stn]] = 1.0
        else:
            L[i] -= bm_height

        # Weighting scheme (Matching MATLAB conventions: P = 1 / sigma^2 or P = 1 / Distance)
        if std_col and pd.notnull(df.iloc[i][std_col]):
            val = float(df.iloc[i][std_col])
            if val > 0:
                std_m = val / 1000.0  # Convert mm to m
                P[i, i] = 1.0 / (std_m ** 2)
        elif dist_col and pd.notnull(df.iloc[i][dist_col]):
            val = float(df.iloc[i][dist_col])
            if val > 0:
                P[i, i] = 1.0 / val  # Weight inversely proportional to distance (km)

    # Normal Equations: N = A' * P * A, U = A' * P * L
    N = A.T @ P @ A
    U = A.T @ P @ L

    # Matrix Rank & Singularity Check
    cond_num = np.linalg.cond(N)
    if cond_num > 1e12:
        raise ValueError(f"Ill-conditioned Normal Matrix (Condition No: {cond_num:.2e}). Check for unlinked stations or missing benchmark constraints.")

    # MATLAB-equivalent solver: np.linalg.lstsq (SVD-based QR decomposition equivalent)
    X, _, _, _ = np.linalg.lstsq(N, U, rcond=None)
    
    # Precise Covariance Matrix Inverse
    Qxx = np.linalg.pinv(N)

    # Residuals vector: V = A*X - L
    V = (A @ X) - L

    # Reference Variance: s0^2 = (V' * P * V) / dof
    vTpv = float(V.T @ P @ V)
    sigma0_sq = vTpv / dof if dof > 0 else 0.0
    sigma0 = np.sqrt(sigma0_sq)

    # Standard errors of parameters: sigma_x = sigma0 * sqrt(diag(Qxx))
    std_errors = np.sqrt(np.diag(Qxx) * (sigma0_sq if dof > 0 else 1.0))

    # Construct Station Output DataFrame
    stations_list = []
    # Benchmark entry
    stations_list.append({
        "Station": bm_name,
        "Adjusted Height (m)": float(np.round(bm_height, 5)),
        "Std Dev (mm)": 0.0,
        "Status": "Fixed Datum"
    })
    # Unknown stations entries
    for s_name, idx in stn_idx.items():
        stations_list.append({
            "Station": s_name,
            "Adjusted Height (m)": float(np.round(X[idx], 5)),
            "Std Dev (mm)": float(np.round(std_errors[idx] * 1000.0, 3)),
            "Status": "Adjusted"
        })
    df_stations = pd.DataFrame(stations_list)

    # Construct Residuals Output DataFrame
    residuals_list = []
    for i in range(num_obs):
        residuals_list.append({
            "From": df.iloc[i][from_col],
            "To": df.iloc[i][to_col],
            "Observed dH (m)": float(df.iloc[i][dh_col]),
            "Adjusted dH (m)": float(np.round(df.iloc[i][dh_col] + V[i], 5)),
            "Residual V (mm)": float(np.round(V[i] * 1000.0, 3)),
            "Weight (P)": float(np.round(P[i, i], 4))
        })
    df_residuals = pd.DataFrame(residuals_list)

    return {
        "stations": df_stations,
        "residuals": df_residuals,
        "sigma0_sq": sigma0_sq,
        "sigma0": sigma0,
        "vTpv": vTpv,
        "dof": dof,
        "cond_num": cond_num
    }

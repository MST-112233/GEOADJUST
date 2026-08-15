import numpy as np
import pandas as pd

def adjust_1d_network(df: pd.DataFrame, bm_name: str, bm_height: float) -> dict:
    """
    Computes parametric 1D Least Squares Adjustment for vertical levelling networks.
    """
    df = df.copy()
    
    # Extract columns by position index to avoid header name issues
    from_col = df.columns[0]
    to_col = df.columns[1]
    dh_col = df.columns[2]
    dist_col = df.columns[3] if len(df.columns) > 3 else None
    std_col = df.columns[4] if len(df.columns) > 4 else None

    # Get unique stations
    all_stations = sorted(list(set(df[from_col].astype(str).str.strip()).union(set(df[to_col].astype(str).str.strip()))))
    
    bm_name = bm_name.strip()
    if bm_name not in all_stations:
        # Fallback to first station if user-specified benchmark is missing
        bm_name = all_stations[0]

    unknown_stations = [s for s in all_stations if s != bm_name]
    num_obs = len(df)
    num_unknowns = len(unknown_stations)
    dof = num_obs - num_unknowns

    if dof < 0:
        raise ValueError(f"Insufficient observations ({num_obs}) for unknown stations ({num_unknowns}). DOF = {dof}.")

    stn_idx = {name: i for i, name in enumerate(unknown_stations)}

    # Build Design Matrix (A), Observation Vector (L), Weight Matrix (P)
    A = np.zeros((num_obs, num_unknowns))
    L = pd.to_numeric(df[dh_col], errors='coerce').values.astype(float)
    P = np.eye(num_obs)

    for i in range(num_obs):
        from_stn = str(df.iloc[i][from_col]).strip()
        to_stn = str(df.iloc[i][to_col]).strip()

        if from_stn in stn_idx:
            A[i, stn_idx[from_stn]] = -1.0
        else:
            L[i] += bm_height

        if to_stn in stn_idx:
            A[i, stn_idx[to_stn]] = 1.0
        else:
            L[i] -= bm_height

        # Weighting
        if std_col and pd.notnull(df.iloc[i][std_col]):
            val = float(df.iloc[i][std_col])
            if val > 0:
                std_m = val / 1000.0
                P[i, i] = 1.0 / (std_m ** 2)
        elif dist_col and pd.notnull(df.iloc[i][dist_col]):
            val = float(df.iloc[i][dist_col])
            if val > 0:
                P[i, i] = 1.0 / val

    # Normal Equations Matrix
    N = A.T @ P @ A
    U = A.T @ P @ L

    # Check rank/singularity
    rank = np.linalg.matrix_rank(N)
    if rank < num_unknowns:
        raise ValueError(f"Singular matrix: Network is unconstrained or unlinked. Rank ({rank}) < Unknowns ({num_unknowns}). Check station IDs or Benchmark selection.")

    # Least squares solution
    X = np.linalg.solve(N, U)
    Qxx = np.linalg.inv(N)

    # Residuals & Variances
    V = (A @ X) - L
    sigma0_sq = float((V.T @ P @ V) / max(dof, 1))
    std_errors = np.sqrt(np.diag(Qxx) * sigma0_sq)

    # Station heights output table
    stations_list = []
    for s_name, idx in stn_idx.items():
        stations_list.append({
            "Station": s_name,
            "Adjusted Height (m)": round(float(X[idx]), 4),
            "Std Dev (mm)": round(float(std_errors[idx] * 1000.0), 2),
            "Status": "Adjusted"
        })
    stations_list.insert(0, {
        "Station": bm_name,
        "Adjusted Height (m)": round(float(bm_height), 4),
        "Std Dev (mm)": 0.0,
        "Status": "Fixed Datum"
    })
    df_stations = pd.DataFrame(stations_list)

    # Residuals output table
    residuals_list = []
    for i in range(num_obs):
        residuals_list.append({
            "From": str(df.iloc[i][from_col]).strip(),
            "To": str(df.iloc[i][to_col]).strip(),
            "Observed dH (m)": float(df.iloc[i][dh_col]),
            "Residual (mm)": round(float(V[i] * 1000.0), 2)
        })
    df_residuals = pd.DataFrame(residuals_list)

    return {
        "stations": df_stations,
        "residuals": df_residuals,
        "sigma0_sq": sigma0_sq,
        "dof": dof
    }

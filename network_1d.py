import numpy as np
import pandas as pd

def adjust_1d_network(df: pd.DataFrame, bm_name: str, bm_height: float) -> dict:
    """
    Computes parametric 1D Least Squares Adjustment for vertical levelling networks.
    
    Parameters:
        df: DataFrame with columns [From_Point, To_Point, dH_m, (Dist_km), (StdDev_mm)]
        bm_name: Station ID of fixed benchmark
        bm_height: Elevation of fixed benchmark (m)
        
    Returns:
        dict containing 'stations' DataFrame, 'residuals' DataFrame, 'sigma0_sq', and 'dof'.
    """
    df = df.copy()
    
    # Rename columns flexibly based on position if string names vary
    cols = list(df.columns)
    from_col = cols[0]
    to_col = cols[1]
    dh_col = cols[2]
    dist_col = cols[3] if len(cols) > 3 else None
    std_col = cols[4] if len(cols) > 4 else None

    # Extract unique station names
    all_stations = sorted(list(set(df[from_col].astype(str)).union(set(df[to_col].astype(str)))))
    
    if bm_name not in all_stations:
        # Fallback if benchmark name is not exact match
        bm_name = all_stations[0]

    unknown_stations = [s for s in all_stations if s != bm_name]
    num_obs = len(df)
    num_unknowns = len(unknown_stations)
    dof = num_obs - num_unknowns

    if dof <= 0:
        raise ValueError(f"Insufficient degrees of freedom (DOF = {dof}). Add more observations.")

    # Index map for unknown stations
    stn_idx = {name: i for i, name in enumerate(unknown_stations)}

    # Build Design Matrix (A) and Observation Vector (L)
    A = np.zeros((num_obs, num_unknowns))
    L = df[dh_col].values.astype(float)
    P = np.eye(num_obs)

    # Weights formulation
    for i in range(num_obs):
        from_stn = str(df.iloc[i][from_col])
        to_stn = str(df.iloc[i][to_col])

        if from_stn in stn_idx:
            A[i, stn_idx[from_stn]] = -1.0
        else:
            L[i] += bm_height  # Add fixed benchmark height

        if to_stn in stn_idx:
            A[i, stn_idx[to_stn]] = 1.0
        else:
            L[i] -= bm_height  # Subtract fixed benchmark height

        # Compute weights based on distance or std dev if available
        if std_col and pd.notnull(df.iloc[i][std_col]) and float(df.iloc[i][std_col]) > 0:
            std_m = float(df.iloc[i][std_col]) / 1000.0
            P[i, i] = 1.0 / (std_m ** 2)
        elif dist_col and pd.notnull(df.iloc[i][dist_col]) and float(df.iloc[i][dist_col]) > 0:
            dist = float(df.iloc[i][dist_col])
            P[i, i] = 1.0 / dist
        else:
            P[i, i] = 1.0

    # Normal equations: (A^T * P * A) * X = A^T * P * L
    N = A.T @ P @ A
    U = A.T @ P @ L

    # Solve for station heights (X)
    X = np.linalg.solve(N, U)
    Qxx = np.linalg.inv(N)

    # Residuals & A-posteriori reference variance
    V = (A @ X) - L
    sigma0_sq = float((V.T @ P @ V) / dof)
    std_errors = np.sqrt(np.diag(Qxx) * sigma0_sq)

    # Prepare Station Results
    stations_list = []
    for s_name, idx in stn_idx.items():
        stations_list.append({
            "Station": s_name,
            "Adjusted Height (m)": round(float(X[idx]), 4),
            "Std Dev (mm)": round(float(std_errors[idx] * 1000.0), 2),
            "Status": "Adjusted"
        })
    # Add Fixed Benchmark
    stations_list.insert(0, {
        "Station": bm_name,
        "Adjusted Height (m)": round(float(bm_height), 4),
        "Std Dev (mm)": 0.0,
        "Status": "Fixed Datum"
    })
    df_stations = pd.DataFrame(stations_list)

    # Prepare Residual Results
    residuals_list = []
    for i in range(num_obs):
        residuals_list.append({
            "From": str(df.iloc[i][from_col]),
            "To": str(df.iloc[i][to_col]),
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

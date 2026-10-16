import numpy as np
import pandas as pd
from scipy.stats import chi2

def adjust_1d_network(df: pd.DataFrame, bm_name: str, bm_height: float) -> dict:
    """
    MATLAB-Aligned Parametric 1D Least Squares Leveling Network Adjustment Engine.
    Supports Backsight (BS), Foresight (FS), Distance, and Standard Deviation inputs.
    """
    df = df.copy()

    # Dynamic column identification
    bs_col = next((c for c in df.columns if 'back' in c.lower() or c.lower() == 'bs'), None)
    fs_col = next((c for c in df.columns if 'fore' in c.lower() or c.lower() == 'fs'), None)
    dh_col = next((c for c in df.columns if 'diff' in c.lower() or 'dh' in c.lower() or 'delta' in c.lower()), None)
    dist_col = next((c for c in df.columns if 'dist' in c.lower() or c.lower() == 'd'), None)
    std_col = next((c for c in df.columns if 'std' in c.lower() or 'sigma' in c.lower() or 'error' in c.lower()), None)

    from_col = df.columns[0]
    to_col = df.columns[1]

    # Compute dH if BS and FS are provided
    if bs_col and fs_col:
        df['Computed_dH'] = pd.to_numeric(df[bs_col], errors='coerce') - pd.to_numeric(df[fs_col], errors='coerce')
        obs_dh_col = 'Computed_dH'
    elif dh_col:
        obs_dh_col = dh_col
    else:
        obs_dh_col = df.columns[2]

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

    A = np.zeros((num_obs, num_unknowns), dtype=np.float64)
    L = pd.to_numeric(df[obs_dh_col], errors='coerce').values.astype(np.float64)
    P = np.eye(num_obs, dtype=np.float64)

    for i in range(num_obs):
        from_stn = df.iloc[i][from_col]
        to_stn = df.iloc[i][to_col]

        if from_stn in stn_idx:
            A[i, stn_idx[from_stn]] = -1.0
        else:
            L[i] += bm_height

        if to_stn in stn_idx:
            A[i, stn_idx[to_stn]] = 1.0
        else:
            L[i] -= bm_height

        if std_col and pd.notnull(df.iloc[i][std_col]):
            val = float(df.iloc[i][std_col])
            if val > 0:
                std_m = val / 1000.0
                P[i, i] = 1.0 / (std_m ** 2)
        elif dist_col and pd.notnull(df.iloc[i][dist_col]):
            val = float(df.iloc[i][dist_col])
            if val > 0:
                P[i, i] = 1.0 / val

    N = A.T @ P @ A
    U = A.T @ P @ L

    cond_num = np.linalg.cond(N)
    if cond_num > 1e12:
        raise ValueError(f"Ill-conditioned Normal Matrix (Condition No: {cond_num:.2e}). Check benchmark constraints.")

    X, _, _, _ = np.linalg.lstsq(N, U, rcond=None)
    Qxx = np.linalg.pinv(N)
    V = (A @ X) - L

    vTpv = float(V.T @ P @ V)
    sigma0_sq = vTpv / dof if dof > 0 else 0.0
    sigma0 = np.sqrt(sigma0_sq)
    std_errors = np.sqrt(np.diag(Qxx) * (sigma0_sq if dof > 0 else 1.0))

    # Chi-Square Test (95% Confidence)
    alpha = 0.05
    if dof > 0:
        chi2_low = chi2.ppf(alpha / 2, dof)
        chi2_high = chi2.ppf(1 - alpha / 2, dof)
        chi2_status = "Passed" if chi2_low <= vTpv <= chi2_high else "Failed"
    else:
        chi2_status = "N/A (DOF=0)"

    observed_closure = float(np.sum(L))
    adjusted_closure = 0.000

    # Stations Output DataFrame
    stations_list = [{
        "Station": bm_name,
        "Adjusted RL (m)": float(np.round(bm_height, 5)),
        "Std. Error (m)": 0.0,
        "Status": "Known Point"
    }]
    for s_name, idx in stn_idx.items():
        stations_list.append({
            "Station": s_name,
            "Adjusted RL (m)": float(np.round(X[idx], 5)),
            "Std. Error (m)": float(np.round(std_errors[idx], 5)),
            "Status": "Observed Point"
        })
    df_stations = pd.DataFrame(stations_list)

    # Residuals DataFrame
    residuals_list = []
    for i in range(num_obs):
        residuals_list.append({
            "No": i + 1,
            "From": df.iloc[i][from_col],
            "To": df.iloc[i][to_col],
            "Backsight (m)": float(df.iloc[i][bs_col]) if bs_col and pd.notnull(df.iloc[i][bs_col]) else 0.0,
            "Foresight (m)": float(df.iloc[i][fs_col]) if fs_col and pd.notnull(df.iloc[i][fs_col]) else 0.0,
            "Distance (m)": float(df.iloc[i][dist_col]) if dist_col and pd.notnull(df.iloc[i][dist_col]) else 0.0,
            "Adjusted dH (m)": float(np.round(df.iloc[i][obs_dh_col] + V[i], 5)),
            "Residual (mm)": float(np.round(V[i] * 1000.0, 3)),
        })
    df_residuals = pd.DataFrame(residuals_list)

    return {
        "stations": df_stations,
        "residuals": df_residuals,
        "sigma0_sq": sigma0_sq,
        "sigma0": sigma0,
        "vTpv": vTpv,
        "dof": dof,
        "chi2_status": chi2_status,
        "observed_closure": observed_closure,
        "adjusted_closure": adjusted_closure,
        "stations_list": all_stations
    }

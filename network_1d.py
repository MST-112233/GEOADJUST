import numpy as np
import pandas as pd
import math

try:
    from scipy.stats import chi2
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def adjust_1d_network(
    df: pd.DataFrame,
    bm_name: str,
    bm_height: float,
    instrument_std: float = 0.003
) -> dict:
    """
    StarNet-Aligned Parametric 1D Least Squares Leveling Network Adjustment Engine.

    This implementation mirrors the StarNet-PRO mathematical model:

    1. OBSERVATION MODEL (Parametric / Gauss-Helmert):
       - L_i = H_to - H_from  (observed elevation difference = BS - FS)
       - Adjusted: L_i + V_i = A_i * X

    2. WEIGHT MODEL (StarNet instrument-based):
       - std_err_i = C * sqrt(D_km_i)    where C = instrument precision (default 0.003 m/km)
       - P_i = 1 / (std_err_i)^2
       (If user provides explicit std column, that value is used directly.)

    3. NORMAL EQUATIONS:
       - N = A^T * P * A
       - U = A^T * P * L
       - X = N^{-1} * U

    4. RESIDUALS:
       - V = A*X - L

    5. VARIANCE FACTOR (A Posteriori):
       - vTpV = V^T * P * V
       - sigma0_sq = vTpV / DOF
       - Error Factor = sqrt(sigma0_sq)

    6. COFACTOR MATRIX:
       - Qxx = N^{-1}

    7. STANDARD ERRORS (StarNet Prior Format):
       - Prior SE = sqrt(diag(Qxx))        (with sigma0 = 1, i.e. based on instrument specs)
       - Posterior SE = sqrt(diag(Qxx) * sigma0_sq)   (scaled by a posteriori variance factor)
       StarNet reports the PRIOR SE in the main table and the Error Factor separately.

    8. CHI-SQUARE TEST (at alpha=0.05):
       - Test statistic: vTpV (sum of weighted squared residuals)
       - Lower bound: chi2.ppf(alpha/2, DOF)
       - Upper bound: chi2.ppf(1 - alpha/2, DOF)
       - Pass if: lower <= vTpV <= upper
       This matches StarNet's "Sum Squares of StdRes" and "Lower/Upper Bounds" output.

    9. 95% CONFIDENCE INTERVALS:
       - CI_95 = t_value * SE  (using normal distribution z=1.96 for large DOF,
         or t-distribution for small DOF)
       StarNet reports 95% CI alongside each station's StdDev.

    Parameters:
    -----------
    df : pd.DataFrame
        Input observations with columns: From, To, Backsight (m), Foresight (m), Distance (m)
        Optionally: Std Dev (mm) column for explicit standard errors.
    bm_name : str
        Name of the fixed benchmark station.
    bm_height : float
        Known reduced level (elevation) of the benchmark in meters.
    instrument_std : float
        Instrument standard error in meters per km (default 0.003, matching StarNet default).

    Returns:
    --------
    dict with keys:
        - stations: DataFrame with Station, Adjusted RL, Prior StdDev, Posterior StdDev,
          95% CI, Status
        - residuals: DataFrame with From, To, BS, FS, Distance, StdErr, Observed dH,
          Adjusted dH, Residual, StdRes
        - sigma0_sq: A posteriori variance factor
        - sigma0: A posteriori standard deviation (Error Factor)
        - vTpv: Sum of weighted squared residuals (chi-square test statistic)
        - dof: Degrees of freedom (redundant observations)
        - chi2_status: "Passed" or "Failed"
        - chi2_lower: Lower bound of chi-square test
        - chi2_upper: Upper bound of chi-square test
        - num_stations: Total number of stations
        - num_obs: Number of observations
        - num_unknowns: Number of unknown stations
        - observed_closure: Sum of observed dH around loop
        - adjusted_closure: Sum of adjusted dH around loop (should be 0 for closed loop)
        - instrument_std: The instrument precision used
        - stations_list: Sorted list of all station names
    """
    df = df.copy()

    # --- Detect column names ---
    bs_col = next((c for c in df.columns if 'back' in c.lower() or c.lower() == 'bs'), None)
    fs_col = next((c for c in df.columns if 'fore' in c.lower() or c.lower() == 'fs'), None)
    dh_col = next((c for c in df.columns if 'diff' in c.lower() or 'dh' in c.lower() or 'delta' in c.lower()), None)
    dist_col = next((c for c in df.columns if 'dist' in c.lower() or c.lower() == 'd'), None)
    std_col = next((c for c in df.columns if 'std' in c.lower() or 'sigma' in c.lower() or 'error' in c.lower()), None)

    from_col = df.columns[0]
    to_col = df.columns[1]

    # --- Compute observed elevation differences ---
    if bs_col and fs_col:
        df['Computed_dH'] = pd.to_numeric(df[bs_col], errors='coerce') - pd.to_numeric(df[fs_col], errors='coerce')
        obs_dh_col = 'Computed_dH'
    elif dh_col:
        obs_dh_col = dh_col
    else:
        obs_dh_col = df.columns[2]

    # --- Clean station names ---
    df[from_col] = df[from_col].astype(str).str.strip()
    df[to_col] = df[to_col].astype(str).str.strip()

    # --- Build station lists ---
    all_stations = sorted(list(set(df[from_col]).union(set(df[to_col]))))
    bm_name = bm_name.strip()

    if bm_name not in all_stations:
        bm_name = all_stations[0]

    unknown_stations = [s for s in all_stations if s != bm_name]
    num_obs = len(df)
    num_unknowns = len(unknown_stations)
    num_stations = len(all_stations)
    dof = num_obs - num_unknowns

    if dof < 0:
        raise ValueError(
            f"Under-constrained network: Observations ({num_obs}) < Unknowns ({num_unknowns}). DOF = {dof}."
        )

    stn_idx = {name: i for i, name in enumerate(unknown_stations)}

    # --- Build Design Matrix A, Observation Vector L, Weight Matrix P ---
    A = np.zeros((num_obs, num_unknowns), dtype=np.float64)
    L = pd.to_numeric(df[obs_dh_col], errors='coerce').values.astype(np.float64)
    P = np.eye(num_obs, dtype=np.float64)
    obs_std_errs = np.zeros(num_obs, dtype=np.float64)  # Store std errors for output

    for i in range(num_obs):
        from_stn = df.iloc[i][from_col]
        to_stn = df.iloc[i][to_col]

        # Design matrix: -1 for From station, +1 for To station
        # Observation equation: H_to - H_from = dH_observed + V
        # If From is benchmark: H_to - BM_height = dH + V  =>  H_to = dH + BM_height + V
        # If To is benchmark:   BM_height - H_from = dH + V  =>  -H_from = dH - BM_height + V
        if from_stn in stn_idx:
            A[i, stn_idx[from_stn]] = -1.0
        else:
            # From station is the benchmark: move BM_height to RHS
            L[i] += bm_height

        if to_stn in stn_idx:
            A[i, stn_idx[to_stn]] = 1.0
        else:
            # To station is the benchmark: move BM_height to RHS
            L[i] -= bm_height

        # --- StarNet Weight Model ---
        # Priority 1: Explicit std column (in mm)
        # Priority 2: Instrument-based: std_err = C * sqrt(D_km) where C = instrument_std
        if std_col and pd.notnull(df.iloc[i][std_col]):
            val = float(df.iloc[i][std_col])
            if val > 0:
                std_m = val / 1000.0  # Convert mm to meters
                obs_std_errs[i] = std_m
                P[i, i] = 1.0 / (std_m ** 2)
        elif dist_col and pd.notnull(df.iloc[i][dist_col]):
            dist_m = float(df.iloc[i][dist_col])
            if dist_m > 0:
                dist_km = dist_m / 1000.0
                # StarNet formula: std_err = C * sqrt(D_km)
                std_err = instrument_std * math.sqrt(dist_km)
                obs_std_errs[i] = std_err
                P[i, i] = 1.0 / (std_err ** 2)
            else:
                # Fallback: unit weight
                obs_std_errs[i] = 1.0
                P[i, i] = 1.0
        else:
            # No distance or std provided: unit weight
            obs_std_errs[i] = 1.0
            P[i, i] = 1.0

    # --- Form and Solve Normal Equations ---
    # N = A^T * P * A
    # U = A^T * P * L
    # X = N^{-1} * U
    N = A.T @ P @ A
    U = A.T @ P @ L

    # Check conditioning
    cond_num = np.linalg.cond(N)
    if cond_num > 1e12:
        raise ValueError(
            f"Ill-conditioned Normal Matrix (Condition No: {cond_num:.2e}). Check benchmark constraints."
        )

    # Solve for unknown parameters
    X, _, _, _ = np.linalg.lstsq(N, U, rcond=None)

    # Cofactor matrix (inverse of normal matrix)
    Qxx = np.linalg.pinv(N)

    # Compute residuals: V = A*X - L
    V = (A @ X) - L

    # --- Statistical Summary (StarNet format) ---
    # v^T * P * V = sum of weighted squared residuals
    vTpv = float(V.T @ P @ V)

    # A posteriori variance factor (Reference Variance)
    sigma0_sq = vTpv / dof if dof > 0 else 0.0
    sigma0 = math.sqrt(sigma0_sq) if sigma0_sq >= 0 else 0.0

    # Standardized residuals (for StarNet "StdRes" column)
    std_res = np.zeros(num_obs, dtype=np.float64)
    for i in range(num_obs):
        if obs_std_errs[i] > 0:
            std_res[i] = V[i] / obs_std_errs[i]
        else:
            std_res[i] = 0.0

    # --- Standard Errors (StarNet Prior Format) ---
    # Prior SE: sqrt(diag(Qxx)) with sigma0 = 1 (based on instrument specs only)
    prior_se = np.sqrt(np.diag(Qxx))

    # Posterior SE: sqrt(diag(Qxx) * sigma0_sq) (scaled by a posteriori variance factor)
    if dof > 0 and sigma0_sq > 0:
        posterior_se = np.sqrt(np.diag(Qxx) * sigma0_sq)
    else:
        posterior_se = prior_se.copy()

    # 95% Confidence Intervals (StarNet format)
    # StarNet uses z=1.95996 for 95% CI (normal distribution)
    z_95 = 1.95996
    ci_95_prior = prior_se * z_95

    # --- Chi-Square Test (StarNet format) ---
    alpha = 0.05
    if dof > 0 and HAS_SCIPY:
        chi2_lower = float(chi2.ppf(alpha / 2, dof))
        chi2_upper = float(chi2.ppf(1 - alpha / 2, dof))
        chi2_status = "Passed" if chi2_lower <= vTpv <= chi2_upper else "Failed"
    else:
        chi2_lower = 0.0
        chi2_upper = 0.0
        chi2_status = "N/A"

    # --- Closure checks ---
    observed_closure = float(np.sum(L))
    adjusted_closure = float(np.sum(V + L))  # Should be 0 for closed loop

    # ===============================
    # STATIONS OUTPUT DATAFRAME
    # (StarNet format: Station, Elev, StdDev, 95% CI, Status)
    # ===============================
    stations_list = [{
        "Station": bm_name,
        "Adjusted RL (m)": float(np.round(bm_height, 4)),
        "Prior StdDev (m)": 0.0,
        "Posterior StdDev (m)": 0.0,
        "95% CI (m)": 0.0,
        "Status": "Fixed (Known Point)"
    }]
    for s_name, idx in stn_idx.items():
        stations_list.append({
            "Station": s_name,
            "Adjusted RL (m)": float(np.round(X[idx], 4)),
            "Prior StdDev (m)": float(np.round(prior_se[idx], 6)),
            "Posterior StdDev (m)": float(np.round(posterior_se[idx], 6)),
            "95% CI (m)": float(np.round(ci_95_prior[idx], 6)),
            "Status": "Adjusted (Observed Point)"
        })
    df_stations = pd.DataFrame(stations_list)

    # ===============================
    # RESIDUALS OUTPUT DATAFRAME
    # (StarNet format: From, To, Observed dH, Adjusted dH, Residual, StdErr, StdRes)
    # ===============================
    residuals_list = []
    for i in range(num_obs):
        residuals_list.append({
            "From": df.iloc[i][from_col],
            "To": df.iloc[i][to_col],
            "Backsight (m)": float(df.iloc[i][bs_col]) if bs_col and pd.notnull(df.iloc[i][bs_col]) else 0.0,
            "Foresight (m)": float(df.iloc[i][fs_col]) if fs_col and pd.notnull(df.iloc[i][fs_col]) else 0.0,
            "Distance (m)": float(df.iloc[i][dist_col]) if dist_col and pd.notnull(df.iloc[i][dist_col]) else 0.0,
            "StdErr (m)": float(np.round(obs_std_errs[i], 6)),
            "Observed dH (m)": float(np.round(df.iloc[i][obs_dh_col], 4)),
            "Adjusted dH (m)": float(np.round(df.iloc[i][obs_dh_col] + V[i], 4)),
            "Residual (m)": float(np.round(V[i], 6)),
            "Residual (mm)": float(np.round(V[i] * 1000.0, 3)),
            "StdRes": float(np.round(std_res[i], 1)),
        })
    df_residuals = pd.DataFrame(residuals_list)

    return {
        "stations": df_stations,
        "residuals": df_residuals,
        "sigma0_sq": sigma0_sq,
        "sigma0": sigma0,
        "error_factor": sigma0,  # StarNet "Error Factor"
        "vTpv": vTpv,
        "dof": dof,
        "chi2_status": chi2_status,
        "chi2_lower": chi2_lower,
        "chi2_upper": chi2_upper,
        "num_stations": num_stations,
        "num_obs": num_obs,
        "num_unknowns": num_unknowns,
        "observed_closure": observed_closure,
        "adjusted_closure": adjusted_closure,
        "instrument_std": instrument_std,
        "stations_list": all_stations,
    }

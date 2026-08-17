import numpy as np
import pandas as pd


def adjust_3d_network(
    df_input, const_name="SPGR", Ta=None, jns=1, conf_level=0.95
):
    """3D Geodetic Vector Network Least Squares Adjustment (Corrected Math)."""
    if Ta is None:
        Ta = np.array([[-1468840.404], [6203485.795], [200173.714]])
    else:
        Ta = np.array(Ta, dtype=float).reshape(3, 1)

    const = [str(const_name).strip()]

    # Read station names and baseline observations
    to_list = df_input.iloc[:, 0].astype(str).str.strip().tolist()
    from_list = df_input.iloc[:, 1].astype(str).str.strip().tolist()

    num = df_input.iloc[:, 2:11].to_numpy(dtype=float)
    dx = num[:, 0]
    dy = num[:, 1]
    dz = num[:, 2]
    cv = num[:, 3:9]

    num_obs = len(dx)

    # Standardize Station List Order
    stn = []
    for station in from_list + to_list:
        if station not in stn:
            stn.append(station)

    num_stn = len(stn)

    # 1. Build Full Design Matrix (A)
    A_full = np.zeros((num_obs * 3, num_stn * 3))

    for i in range(num_obs):
        from_idx = stn.index(from_list[i])
        to_idx = stn.index(to_list[i])

        # Standard 3D Geodetic Design Matrix derivative setup
        # dX_obs = X_to - X_from
        for v in range(3):
            row_idx = i * 3 + v
            A_full[row_idx, from_idx * 3 + v] = -1.0
            A_full[row_idx, to_idx * 3 + v] = 1.0

    # 2. Build Block Diagonal Covariance Matrix (C_l) & Weight Matrix (W)
    cov_matrix = np.zeros((num_obs * 3, num_obs * 3))

    for i in range(num_obs):
        idx = i * 3
        # CORRECTED 3x3 Covariance Matrix Mapping:
        # [ Var(dX)    Cov(dX,dY) Cov(dX,dZ) ]
        # [ Cov(dX,dY) Var(dY)    Cov(dY,dZ) ]
        # [ Cov(dX,dZ) Cov(dY,dZ) Var(dZ)    ]
        cov_block = np.array([
            [cv[i, 0], cv[i, 1], cv[i, 2]],
            [cv[i, 1], cv[i, 3], cv[i, 4]],
            [cv[i, 2], cv[i, 4], cv[i, 5]],  # <--- Fixed [i,2] mapping
        ])
        cov_matrix[idx : idx + 3, idx : idx + 3] = cov_block

    W = np.linalg.inv(cov_matrix)

    # 3. Build Observation Vector (L)
    L_obs = np.zeros((num_obs * 3, 1))
    for i in range(num_obs):
        L_obs[i * 3 : i * 3 + 3, 0] = [dx[i], dy[i], dz[i]]

    # 4. Partition Fixed vs Unknown Stations
    unk_stn = list(stn)
    fixed_indices = [
        stn.index(c) for c in const if c in stn
    ]  # 0-based station indices

    # Remove fixed station columns from Design Matrix
    cols_to_delete = []
    for f_idx in sorted(fixed_indices, reverse=True):
        cols_to_delete.extend([f_idx * 3, f_idx * 3 + 1, f_idx * 3 + 2])
        unk_stn.pop(f_idx)

    A = np.delete(A_full, cols_to_delete, axis=1)

    # Adjust Observation Vector L with fixed coordinates
    L = L_obs.copy()
    for i in range(num_obs):
        if from_list[i] in const:
            L[i * 3 : i * 3 + 3] += Ta
        if to_list[i] in const:
            L[i * 3 : i * 3 + 3] -= Ta

    # 5. Least-Squares Solution: X = (A^T * W * A)^(-1) * (A^T * W * L)
    N = A.T @ W @ A
    N_inv = np.linalg.inv(N)
    U = A.T @ W @ L
    X = N_inv @ U

    # 6. Residuals & Precision Statistics
    V = A @ X - L
    vTpv = float((V.T @ W @ V)[0, 0])
    dof = int(A.shape[0] - A.shape[1])
    dof_calc = max(dof, 1)

    sigma0_sq = vTpv / dof_calc
    sigma0 = np.sqrt(sigma0_sq)

    Cx = sigma0_sq * N_inv
    std_x = np.sqrt(np.diag(Cx))

    num_unk = len(unk_stn)
    g = X.reshape((num_unk, 3), order="C")
    std_g = std_x.reshape((num_unk, 3), order="C")

    # Build Output DataFrames
    stations_list = [
        {
            "Station": const_name,
            "X (m)": float(Ta[0, 0]),
            "Y (m)": float(Ta[1, 0]),
            "Z (m)": float(Ta[2, 0]),
            "σX (mm)": 0.00,
            "σY (mm)": 0.00,
            "σZ (mm)": 0.00,
            "Status": "Fixed Constraint",
        }
    ]

    for st in range(num_unk):
        stations_list.append(
            {
                "Station": unk_stn[st],
                "X (m)": float(g[st, 0]),
                "Y (m)": float(g[st, 1]),
                "Z (m)": float(g[st, 2]),
                "σX (mm)": float(std_g[st, 0] * 1000.0),
                "σY (mm)": float(std_g[st, 1] * 1000.0),
                "σZ (mm)": float(std_g[st, 2] * 1000.0),
                "Status": "Adjusted",
            }
        )

    df_stations = pd.DataFrame(stations_list)

    residuals_list = []
    for i in range(num_obs):
        residuals_list.append(
            {
                "From": from_list[i],
                "To": to_list[i],
                "V_dX (m)": float(V[i * 3, 0]),
                "V_dY (m)": float(V[i * 3 + 1, 0]),
                "V_dZ (m)": float(V[i * 3 + 2, 0]),
            }
        )

    df_residuals = pd.DataFrame(residuals_list)

    return {
        "stations": df_stations,
        "residuals": df_residuals,
        "sigma0_sq": sigma0_sq,
        "sigma0": sigma0,
        "dof": dof,
        "vTpv": vTpv,
        "X": X,
        "A": A,
        "W": W,
    }

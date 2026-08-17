import numpy as np
import pandas as pd


def adjust_3d_network(
    df_input, const_name="SPGR", Ta=None, jns=1, conf_level=0.95
):
    """3D Geodetic Vector Network Least Squares Adjustment.

    Calculates 3D station coordinates and statistics strictly preserving original
    MATLAB mathematical formulation.

    Parameters:
    -----------
    df_input : pd.DataFrame
        Data containing baseline vectors and covariance elements.
    const_name : str
        Name of the fixed constraint station.
    Ta : list or np.ndarray
        Coordinates [X, Y, Z] in meters for the constrained station.
    jns : int
        Baseline vector direction indicator flag (default: 1).
    conf_level : float
        Confidence level for standard error scaling.

    Returns:
    --------
    dict containing stations DataFrame, residuals DataFrame, and adjustment statistics.
    """
    if Ta is None:
        Ta = np.array([[-1468840.404], [6203485.795], [200173.714]])
    else:
        Ta = np.array(Ta, dtype=float).reshape(3, 1)

    const = [str(const_name).strip()]
    coll = len(const)

    # Standardize input structure
    to_list = df_input.iloc[:, 0].astype(str).str.strip().tolist()
    from_list = df_input.iloc[:, 1].astype(str).str.strip().tolist()

    num = df_input.iloc[:, 2:11].to_numpy(dtype=float)
    dx = num[:, 0]
    dy = num[:, 1]
    dz = num[:, 2]
    cv = num[:, 3:9]

    row = len(dx)

    # Assemble ordered list of unique stations
    pt = from_list + to_list
    stn = []
    for station in pt:
        if station not in stn:
            stn.append(station)

    rw = len(stn)

    # Design Matrix (A)
    A = np.zeros((row * 3, rw * 3))
    count = 0

    for i in range(row):
        for v in range(3):
            dari = stn.index(from_list[i])
            dr = dari * 3
            d2 = v + dr
            A[count, d2] = 1.0

            ke = stn.index(to_list[i])
            kee = ke * 3
            k2 = v + kee
            A[count, k2] = -1.0

            count += 1

    # Covariance and Weight Matrix (W) construction
    wgt = np.zeros((row * 3, row * 3))
    r = 0
    for i in range(row):
        min_idx = r
        wgt[min_idx : min_idx + 3, min_idx : min_idx + 3] = np.array(
            [
                [cv[i, 0], cv[i, 1], cv[i, 2]],
                [cv[i, 1], cv[i, 3], cv[i, 4]],
                [cv[i, 3], cv[i, 4], cv[i, 5]],
            ]
        )
        r += 3

    W = np.linalg.inv(wgt)

    # Observation vector construction
    vec = np.array([dx, dy, dz], dtype=float)
    bs = A.shape[0]

    unk = list(stn)

    # Apply datum constraints
    for b in range(coll):
        if const[b] in unk:
            emp = unk.index(const[b])
            empt = emp * 3
            unk.pop(emp)
            A = np.delete(A, np.s_[empt : empt + 3], axis=1)

        f_indices = [
            idx for idx, val in enumerate(from_list) if val == const[b]
        ]
        if f_indices:
            for idx in f_indices:
                if jns == 0:
                    vec[:, idx : idx + 1] += Ta
                else:
                    vec[:, idx : idx + 1] -= Ta

        h_indices = [idx for idx, val in enumerate(to_list) if val == const[b]]
        if h_indices:
            for idx in h_indices:
                if jns == 0:
                    vec[:, idx : idx + 1] -= Ta
                else:
                    vec[:, idx : idx + 1] += Ta

    L = vec.reshape((bs, 1), order="F")

    # Least Squares Estimation: X = (A^T * W * A)^(-1) * (A^T * W * L)
    N = A.T @ W @ A
    N_inv = np.linalg.inv(N)
    U = A.T @ W @ L
    X = N_inv @ U

    # Residuals & Variance Factor Computation
    V = A @ X - L
    vTpv = float((V.T @ W @ V)[0, 0])
    dof = int(A.shape[0] - A.shape[1])
    dof_calc = max(dof, 1)

    sigma0_sq = vTpv / dof_calc
    sigma0 = np.sqrt(sigma0_sq)

    # Parameter Covariance Matrix
    Cx = sigma0_sq * N_inv
    std_x = np.sqrt(np.diag(Cx))

    num_unk = len(unk)
    g = X.reshape((num_unk, 3), order="C")
    std_g = std_x.reshape((num_unk, 3), order="C")

    # Format Station Data
    stations_list = []
    # Add Fixed Constrained Station
    stations_list.append(
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
    )

    # Add Adjusted Unknown Stations
    for st in range(num_unk):
        stations_list.append(
            {
                "Station": unk[st],
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

    # Format Residuals Data
    residuals_list = []
    v_reshaped = V.reshape((row, 3), order="F")
    for i in range(row):
        residuals_list.append(
            {
                "From": from_list[i],
                "To": to_list[i],
                "V_dX (m)": float(v_reshaped[i, 0]),
                "V_dY (m)": float(v_reshaped[i, 1]),
                "V_dZ (m)": float(v_reshaped[i, 2]),
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

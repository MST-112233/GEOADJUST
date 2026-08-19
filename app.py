import io
import os
import pandas as pd
import streamlit as st
from network_1d import adjust_1d_network
from network_3d import adjust_3d_network

# --- 1. Page Configuration ---
st.set_page_config(page_title="GEOADJUST", page_icon="🌐", layout="wide")

# Custom Styling
st.markdown(
    """
    <style>
    .main-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 800;
        color: #1E88E5;
        margin-bottom: 0px;
    }
    .sub-title {
        text-align: center;
        font-size: 1.1rem;
        color: #555555;
        margin-bottom: 1.5rem;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Title Header
st.markdown("<h1 class='main-title'>GEOADJUST</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>",
    unsafe_allow_html=True,
)

# --- 2. Main Navigation Tabs ---
tab1, tab2, tab3 = st.tabs([
    "📏 1D Levelling",
    "🛰️ 3D GNSS",
    "📍 Real-Time Tracking",
])

# =========================================================
# TAB 1: 1D NETWORK ADJUSTMENT (LEVELLING)
# =========================================================
with tab1:
    st.header("📏 1D Leveling Network Adjustment")
    st.caption("MATLAB-Aligned Parametric Least Squares Leveling Engine")

    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        bm_name = st.text_input(
            "Fixed Benchmark Station Name", value="BMFGHT", key="1d_bm_name"
        )
        has_header = st.checkbox(
            "File contains a header row", value=False, key="1d_header"
        )
    with col_cfg2:
        bm_height = st.number_input(
            "Benchmark Height (m)",
            value=100.0000,
            step=0.0001,
            format="%.4f",
            key="1d_bm_height",
        )
        custom_filename = st.text_input(
            "Output Filename Base", value="1D_Adjustment_Results", key="1d_out_name"
        )

    with st.expander("ℹ️ Required File Format Guide"):
        st.markdown("""
        Upload **`.csv`** or **`.xlsx`** structured as follows:
        * **Column 1**: From Station ID (e.g., `CP001`)
        * **Column 2**: To Station ID (e.g., `TBM2`)
        * **Column 3**: Height Difference $dH$ in meters ($m$)
        * **Column 4** *(Optional)*: Line Distance ($km$)
        * **Column 5** *(Optional)*: Standard Deviation ($mm$)
        """)

    uploaded_file = st.file_uploader(
        "Upload Leveling File (.csv or .xlsx)",
        type=["csv", "xlsx"],
        key="1d_file_uploader",
    )

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_input = pd.read_csv(
                    uploaded_file, header=0 if has_header else None
                )
            else:
                df_input = pd.read_excel(
                    uploaded_file, header=0 if has_header else None
                )

            expected_cols = [
                "From_Point",
                "To_Point",
                "dH_m",
                "Dist_km",
                "StdDev_mm",
            ]
            if not has_header or len(df_input.columns) < 3:
                rename_map = {
                    i: expected_cols[i]
                    for i in range(min(len(df_input.columns), 5))
                }
                df_input = df_input.rename(columns=rename_map)

            st.subheader("📋 Input Data Preview")
            st.dataframe(df_input.head(10), use_container_width=True)

            if st.button(
                "🚀 Run 1D Adjustment",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Computing Least Squares..."):
                    st.session_state["results_1d"] = adjust_1d_network(
                        df_input, bm_name, bm_height
                    )
                    st.success("Adjustment Complete!")

        except Exception as e:
            st.error(f"Data loading error: {e}")

    if "results_1d" in st.session_state:
        res = st.session_state["results_1d"]

        st.markdown("---")
        st.subheader("📊 Adjustment Summary Statistics")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ref Variance (σ₀²)", f"{res['sigma0_sq']:.6f}")
        m2.metric("Ref Std Dev (σ₀)", f"{res['sigma0']:.5f}")
        m3.metric("Degrees of Freedom", res["dof"])
        m4.metric("Sum VᵀPV", f"{res['vTpv']:.5f}")

        col_tbl1, col_tbl2 = st.columns(2)
        with col_tbl1:
            st.subheader("📍 Adjusted Station Heights")
            st.dataframe(
                res["stations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Station": st.column_config.TextColumn("Station ID"),
                    "Adjusted Height (m)": st.column_config.NumberColumn(
                        "Adjusted Height (m)", format="%.4f"
                    ),
                    "Std Dev (mm)": st.column_config.NumberColumn(
                        "Std Error (mm)", format="%.2f"
                    ),
                    "Status": st.column_config.TextColumn("Status"),
                },
            )

        with col_tbl2:
            st.subheader("📏 Observation Residuals")
            st.dataframe(
                res["residuals"], use_container_width=True, hide_index=True
            )

        st.markdown("---")
        st.subheader("💾 Export & Save Output")

        btn_col1, btn_col2 = st.columns(2)

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            res["stations"].to_excel(
                writer, sheet_name="Adjusted Heights", index=False
            )
            res["residuals"].to_excel(
                writer, sheet_name="Residuals", index=False
            )

        with btn_col1:
            st.download_button(
                label="📥 Save & Download Excel Output (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name=f"{custom_filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        csv_data = res["stations"].to_csv(index=False).encode("utf-8")
        with btn_col2:
            st.download_button(
                label="📥 Save & Download Stations CSV (.csv)",
                data=csv_data,
                file_name=f"{custom_filename}_stations.csv",
                mime="text/csv",
                use_container_width=True,
            )

# =========================================================
# TAB 3: 3D GNSS NETWORK ADJUSTMENT
# =========================================================
with tab3:
    st.header("🛰️ 3D GNSS Vector Network Adjustment")
    st.caption(
        "MATLAB-Aligned Parametric 3D Geodetic Vector Least Squares Adjustment"
    )

    col_3d_1, col_3d_2 = st.columns(2)
    with col_3d_1:
        stn_const_name = st.text_input(
            "Fixed Station Name", value="SPGR", key="3d_const_name"
        )
        has_header_3d = st.checkbox(
            "File contains a header row", value=True, key="3d_header"
        )
        custom_filename_3d = st.text_input(
            "Output Filename Base",
            value="3D_GNSS_Adjustment_Results",
            key="3d_out_name",
        )

    with col_3d_2:
        st.markdown("**Constrained Station Coordinates (ECEF)**")
        col_x, col_y, col_z = st.columns(3)
        with col_x:
            const_x = st.number_input(
                "X (m)",
                value=-1468840.4040,
                format="%.4f",
                step=0.0001,
                key="3d_x",
            )
        with col_y:
            const_y = st.number_input(
                "Y (m)",
                value=6203485.7950,
                format="%.4f",
                step=0.0001,
                key="3d_y",
            )
        with col_z:
            const_z = st.number_input(
                "Z (m)", value=200173.7140, format="%.4f", step=0.0001, key="3d_z"
            )

    with st.expander("ℹ️ Required File Format Guide"):
        st.markdown("""
        Upload **`.xlsx`** or **`.csv`** containing 11 baseline observation and covariance columns:
        * **Column 1**: `TO` Station ID
        * **Column 2**: `FROM` Station ID
        * **Column 3-5**: Baseline Components `dX`, `dY`, `dZ` (meters)
        * **Column 6-11**: Covariance Matrix upper triangular terms `Var(dX)`, `Cov(dX,dY)`, `Cov(dX,dZ)`, `Var(dY)`, `Cov(dY,dZ)`, `Var(dZ)`
        """)

    uploaded_file_3d = st.file_uploader(
        "Upload Baseline Vector File (.xlsx or .csv)",
        type=["xlsx", "csv"],
        key="3d_file_uploader",
    )

    if uploaded_file_3d is not None:
        try:
            if uploaded_file_3d.name.endswith(".csv"):
                df_input_3d = pd.read_csv(
                    uploaded_file_3d, header=0 if has_header_3d else None
                )
            else:
                df_input_3d = pd.read_excel(
                    uploaded_file_3d, header=0 if has_header_3d else None
                )

            st.subheader("📋 Input Vector Preview")
            st.dataframe(df_input_3d.head(10), use_container_width=True)

            if st.button(
                "🚀 Run 3D Adjustment",
                type="primary",
                use_container_width=True,
                key="btn_run_3d",
            ):
                with st.spinner("Computing 3D Least Squares..."):
                    Ta_coords = [const_x, const_y, const_z]
                    st.session_state["results_3d"] = adjust_3d_network(
                        df_input_3d,
                        const_name=stn_const_name,
                        Ta=Ta_coords,
                        jns=1,
                    )
                    st.success("3D Network Adjustment Complete!")

        except Exception as e:
            st.error(f"Data loading error: {e}")

    if "results_3d" in st.session_state:
        res3d = st.session_state["results_3d"]

        st.markdown("---")
        st.subheader("📊 3D Adjustment Summary Statistics")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ref Variance (σ₀²)", f"{res3d['sigma0_sq']:.6f}")
        m2.metric("Ref Std Dev (σ₀)", f"{res3d['sigma0']:.5f}")
        m3.metric("Degrees of Freedom", res3d["dof"])
        m4.metric("Sum VᵀPV", f"{res3d['vTpv']:.5f}")

        col_tbl1_3d, col_tbl2_3d = st.columns(2)
        with col_tbl1_3d:
            st.subheader("📍 Adjusted 3D Coordinates (ECEF)")
            st.dataframe(
                res3d["stations"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Station": st.column_config.TextColumn("Station ID"),
                    "X (m)": st.column_config.NumberColumn(
                        "X (m)", format="%.4f"
                    ),
                    "Y (m)": st.column_config.NumberColumn(
                        "Y (m)", format="%.4f"
                    ),
                    "Z (m)": st.column_config.NumberColumn(
                        "Z (m)", format="%.4f"
                    ),
                    "σX (mm)": st.column_config.NumberColumn(
                        "σX (mm)", format="%.2f"
                    ),
                    "σY (mm)": st.column_config.NumberColumn(
                        "σY (mm)", format="%.2f"
                    ),
                    "σZ (mm)": st.column_config.NumberColumn(
                        "σZ (mm)", format="%.2f"
                    ),
                    "Status": st.column_config.TextColumn("Status"),
                },
            )

        with col_tbl2_3d:
            st.subheader("📏 Baseline Residuals")
            st.dataframe(
                res3d["residuals"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "From": st.column_config.TextColumn("From"),
                    "To": st.column_config.TextColumn("To"),
                    "V_dX (m)": st.column_config.NumberColumn(
                        "V_dX (m)", format="%.5f"
                    ),
                    "V_dY (m)": st.column_config.NumberColumn(
                        "V_dY (m)", format="%.5f"
                    ),
                    "V_dZ (m)": st.column_config.NumberColumn(
                        "V_dZ (m)", format="%.5f"
                    ),
                },
            )

        st.markdown("---")
        st.subheader("💾 Export & Save 3D Output")

        btn_col1_3d, btn_col2_3d = st.columns(2)

        excel_buffer_3d = io.BytesIO()
        with pd.ExcelWriter(excel_buffer_3d, engine="openpyxl") as writer:
            res3d["stations"].to_excel(
                writer, sheet_name="Adjusted Coordinates", index=False
            )
            res3d["residuals"].to_excel(
                writer, sheet_name="Residuals", index=False
            )

        with btn_col1_3d:
            st.download_button(
                label="📥 Save & Download 3D Excel Output (.xlsx)",
                data=excel_buffer_3d.getvalue(),
                file_name=f"{custom_filename_3d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        csv_data_3d = res3d["stations"].to_csv(index=False).encode("utf-8")
        with btn_col2_3d:
            st.download_button(
                label="📥 Save & Download 3D Stations CSV (.csv)",
                data=csv_data_3d,
                file_name=f"{custom_filename_3d}_stations.csv",
                mime="text/csv",
                use_container_width=True,
            )



# =========================================================
# TAB 5: REAL-TIME TRACKING
# =========================================================
with tab5:
    st.header("📍 Real-Time Tracking & Visualization")
    st.caption("Stream spatial positions live and plot trajectory data.")

    TRACKING_URL = "https://geoadjust-tracking.onrender.com"

    st.markdown("""
    ### 🔗 Access Real-Time Tracking Interface

    Click the button below to open the real-time tracking interface in a new tab:
    """)

    st.markdown(
        f'<a href="{TRACKING_URL}/tracking" target="_blank" style="text-decoration: none;">',
        unsafe_allow_html=True,
    )
    st.button(
        "🚀 Open Tracking Interface", use_container_width=True, type="primary"
    )
    st.markdown("</a>", unsafe_allow_html=True)

    st.divider()

    st.markdown("### 📡 Server Status")
    try:
        import requests

        response = requests.get(f"{TRACKING_URL}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            st.success(
                "✅ Tracking server is online!"
                f" ({data['rooms_count']} active room(s))"
            )
        else:
            st.warning(
                "⚠️ Server is reachable but returned unexpected response"
            )
    except Exception as e:
        st.error(
            "❌ Cannot connect to tracking server. Please ensure it's running."
        )
        st.info(f"Server URL: {TRACKING_URL}")

    st.divider()

    st.markdown("""
    ### 📋 How to Use the Tracking System

    #### 🏢 Control Center (Office):
    1. Click "Open Tracking Interface"
    2. Enter a Room Name (e.g., "Project Alpha")
    3. Set a password (remember it!)
    4. Select "Control Center" as role
    5. Click "Enter Room"
    6. Share Room ID and Password with field teams

    #### 🔧 Site Surveyors (Field):
    1. Open the tracking interface
    2. Enter the Room ID provided by Control Center
    3. Enter the room password
    4. Select "Site Surveyor" as role
    5. Click "Enter Room"
    6. Grant location permissions when prompted
    7. Your location will automatically update every 10 seconds

    #### ✨ Features:
    - 📍 Real-time GPS tracking on interactive map
    - 💬 Live chat between office and field teams
    - 📊 Export location logs (CSV)
    - 📝 Export chat history (TXT)
    - 👥 Multiple users supported
    - 🌐 Works across WiFi and mobile data
    - 🔒 Room-based security with passwords
    """)

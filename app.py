import io
import os
import streamlit as st
import pandas as pd
from network_1d import adjust_1d_network

# --- 1. Page Configuration ---
st.set_page_config(
    page_title="GEOADJUST",
    page_icon="🌐",
    layout="wide"
)

# Custom Styling
st.markdown("""
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
""", unsafe_allow_html=True)

# Title Header
st.markdown("<h1 class='main-title'>GEOADJUST</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>", unsafe_allow_html=True)

# --- 2. Main Navigation Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📏 1D Levelling", 
    "📐 2D Traversing", 
    "🛰️ 3D GNSS", 
    "🗺️ Map Projection", 
    "📍 Real-Time Tracking"
])

# =========================================================
# TAB 1: 1D NETWORK ADJUSTMENT (LEVELLING)
# =========================================================
with tab1:
    st.header("📏 1D Leveling Network Adjustment")
    st.caption("MATLAB-Aligned Parametric Least Squares Leveling Engine")

    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        bm_name = st.text_input("Fixed Benchmark Station Name", value="BMFGHT", key="1d_bm_name")
        has_header = st.checkbox("File contains a header row", value=False, key="1d_header")
    with col_cfg2:
        bm_height = st.number_input("Benchmark Height (m)", value=100.0000, step=0.0001, format="%.4f", key="1d_bm_height")
        custom_filename = st.text_input("Output Filename Base", value="1D_Adjustment_Results", key="1d_out_name")

    with st.expander("ℹ️ Required File Format Guide"):
        st.markdown("""
        Upload **`.csv`** or **`.xlsx`** structured as follows:
        * **Column 1**: From Station ID (e.g., `CP001`)
        * **Column 2**: To Station ID (e.g., `TBM2`)
        * **Column 3**: Height Difference $dH$ in meters ($m$)
        * **Column 4** *(Optional)*: Line Distance ($km$)
        * **Column 5** *(Optional)*: Standard Deviation ($mm$)
        """)

    uploaded_file = st.file_uploader("Upload Leveling File (.csv or .xlsx)", type=["csv", "xlsx"], key="1d_file_uploader")

    if uploaded_file is not None:
        try:
            # Read file based on type
            if uploaded_file.name.endswith('.csv'):
                df_input = pd.read_csv(uploaded_file, header=0 if has_header else None)
            else:
                df_input = pd.read_excel(uploaded_file, header=0 if has_header else None)

            # Assign columns standard layout if unheadered
            expected_cols = ["From_Point", "To_Point", "dH_m", "Dist_km", "StdDev_mm"]
            if not has_header or len(df_input.columns) < 3:
                rename_map = {i: expected_cols[i] for i in range(min(len(df_input.columns), 5))}
                df_input = df_input.rename(columns=rename_map)

            st.subheader("📋 Input Data Preview")
            st.dataframe(df_input.head(10), use_container_width=True)

            # Run Adjustment Button
            if st.button("🚀 Run 1D Adjustment", type="primary", use_container_width=True):
                with st.spinner("Computing Least Squares..."):
                    st.session_state['results_1d'] = adjust_1d_network(df_input, bm_name, bm_height)
                    st.success("Adjustment Complete!")

        except Exception as e:
            st.error(f"Data loading error: {e}")

    # Render Results Persistently
    if 'results_1d' in st.session_state:
        res = st.session_state['results_1d']
        
        st.markdown("---")
        st.subheader("📊 Adjustment Summary Statistics")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ref Variance (σ₀²)", f"{res['sigma0_sq']:.6f}")
        m2.metric("Ref Std Dev (σ₀)", f"{res['sigma0']:.5f}")
        m3.metric("Degrees of Freedom", res['dof'])
        m4.metric("Sum VᵀPV", f"{res['vTpv']:.5f}")

        col_tbl1, col_tbl2 = st.columns(2)
        with col_tbl1:
            st.subheader("📍 Adjusted Station Heights")
            st.dataframe(
                res['stations'], 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Station": st.column_config.TextColumn("Station ID"),
                    "Adjusted Height (m)": st.column_config.NumberColumn("Adjusted Height (m)", format="%.4f"),
                    "Std Dev (mm)": st.column_config.NumberColumn("Std Error (mm)", format="%.2f"),
                    "Status": st.column_config.TextColumn("Status")
                }
            )

        with col_tbl2:
            st.subheader("📏 Observation Residuals")
            st.dataframe(res['residuals'], use_container_width=True, hide_index=True)

        # Output Download Options
        st.markdown("---")
        st.subheader("💾 Export & Save Output")
        
        btn_col1, btn_col2 = st.columns(2)
        
        # Excel Download Buffer
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            res['stations'].to_excel(writer, sheet_name='Adjusted Heights', index=False)
            res['residuals'].to_excel(writer, sheet_name='Residuals', index=False)

        with btn_col1:
            st.download_button(
                label="📥 Save & Download Excel Output (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name=f"{custom_filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        # CSV Download Buffer
        csv_data = res['stations'].to_csv(index=False).encode('utf-8')
        with btn_col2:
            st.download_button(
                label="📥 Save & Download Stations CSV (.csv)",
                data=csv_data,
                file_name=f"{custom_filename}_stations.csv",
                mime="text/csv",
                use_container_width=True
            )

# =========================================================
# TAB 2: 2D TRAVERSING MODULE (PLACEHOLDER)
# =========================================================
with tab2:
    st.header("📐 2D Network Adjustment (Traversing)")
    st.caption("2D least-squares adjustment for distance, horizontal angle, and azimuth observations.")
    st.file_uploader("Upload Control Points (.csv)", type=["csv"], key="2d_pts")
    st.file_uploader("Upload Distance/Angle Obs (.csv)", type=["csv"], key="2d_obs")
    st.info("📌 Module logic ready for 2D computation code.")

# =========================================================
# TAB 3: 3D GNSS MODULE (PLACEHOLDER)
# =========================================================
with tab3:
    st.header("🛰️ 3D Network Adjustment (GNSS)")
    st.caption("3D adjustment incorporating baseline vectors (dX, dY, dZ) and covariance matrices.")
    st.file_uploader("Upload RINEX / Baseline File", key="3d_gnss")
    st.selectbox("Reference Frame", ["WGS84", "ITRF2020", "Local Localized Datum"])
    st.info("📌 Module logic ready for 3D GNSS computation code.")

# =========================================================
# TAB 4: MAP PROJECTION (PLACEHOLDER)
# =========================================================
with tab4:
    st.header("🗺️ Map Projection & Transformations")
    st.caption("Convert between Geographic (Lat/Lon) and Projected Coordinates (UTM/Local).")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Transformation Type", ["Geographic to UTM", "UTM to Geographic"])
        st.number_input("Latitude / Northing", value=1.4927)
    with c2:
        st.number_input("Longitude / Easting", value=103.7414)
        st.selectbox("Ellipsoid", ["WGS84", "GRS80", "Kertau 1948"])
    st.info("📌 Module logic ready for projection math.")

# =========================================================
# TAB 5: REAL-TIME TRACKING (PLACEHOLDER)
# =========================================================
with tab5:
    st.header("📍 Real-Time Tracking & Visualization")
    st.caption("Stream spatial positions live and plot trajectory data.")
    st.text_input("NMEA / RTCM Stream URL", "tcp://127.0.0.1:9000")
    st.map(data={"lat": [1.4927], "lon": [103.7414]}, zoom=12)

import os
import io
import streamlit as st
import pandas as pd
from network_1d import adjust_1d_network

# 1. Page Configuration
st.set_page_config(
    page_title="GEOADJUST",
    page_icon="🌐",
    layout="wide"
)

# Custom CSS for UI styling
st.markdown("""
    <style>
    .main-title {
        text-align: center;
        font-size: 3rem;
        font-weight: 800;
        color: #1E88E5;
        margin-bottom: 0px;
    }
    .sub-title {
        text-align: center;
        font-size: 1.2rem;
        color: #555555;
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Title Header
st.markdown("<h1 class='main-title'>GEOADJUST</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>", unsafe_allow_html=True)

st.write("---")
st.subheader("Select a Module")

# ---------------------------------------------------------
# DIALOG DEFINITIONS (Pop-up Modals for Each Module)
# ---------------------------------------------------------

@st.dialog("📏 1D Network Adjustment (Levelling)", width="large")
def show_1d_module():
    st.caption("Perform 1D least-squares adjustment for differential levelling networks.")
    
    # --- Benchmark Inputs ---
    col_bm1, col_bm2 = st.columns(2)
    with col_bm1:
        bm_name = st.text_input("Benchmark Station Name (Fixed)", value="BMFAB")
    with col_bm2:
        bm_height = st.number_input("Benchmark Height (m)", value=100.0, step=0.001, format="%.4f")
    
    # --- Format Guide ---
    with st.expander("ℹ️ Click to view required column format"):
        st.markdown("""
        Your uploaded file (**`.csv`** or **`.xlsx`**) should follow this column structure:
        
        | Column | Recommended Header | Type | Description | Required? |
        |---|---|---|---|---|
        | Col 1 | `From_Point` | String | Origin Station ID | **Yes** |
        | Col 2 | `To_Point` | String | Target Station ID | **Yes** |
        | Col 3 | `dH_m` | Float | Observed height difference ($m$) | **Yes** |
        | Col 4 | `Dist_km` | Float | Line length ($km$) | Optional (default = 1.0) |
        | Col 5 | `StdDev_mm` | Float | A-priori std dev ($mm$) | Optional (default = 1.0) |
        """)

    # --- File Upload ---
    uploaded_file = st.file_uploader("Upload Levelling Observation File (.csv or .xlsx)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            has_header = st.checkbox("File contains a header row", value=True)
            
            # Read file based on extension
            if uploaded_file.name.endswith('.csv'):
                df_input = pd.read_csv(uploaded_file, header=0 if has_header else None)
            else:
                df_input = pd.read_excel(uploaded_file, header=0 if has_header else None)

            # Assign standard headers if missing or positional
            expected_cols = ["From_Point", "To_Point", "dH_m", "Dist_km", "StdDev_mm"]
            if not has_header or len(df_input.columns) < 3:
                rename_map = {i: expected_cols[i] for i in range(min(len(df_input.columns), 5))}
                df_input = df_input.rename(columns=rename_map)

            st.write("📋 **Input Data Preview:**")
            st.dataframe(df_input.head(5), use_container_width=True)

            if len(df_input.columns) < 3:
                st.error("❌ Invalid file format: At least 3 columns (From_Point, To_Point, dH_m) are required.")
            else:
                st.success("✅ File format verified!")

                # --- Output Directory Selector ---
                st.markdown("---")
                st.subheader("💾 Output Destination")
                default_dir = os.path.join(os.path.expanduser("~"), "GEOADJUST_Outputs")
                output_dir = st.text_input("Local Save Directory Path:", value=default_dir)

                # --- Execution ---
                if st.button("Run 1D Adjustment", type="primary", use_container_width=True):
                    with st.spinner("Computing Least Squares Adjustment..."):
                        results = adjust_1d_network(df_input, bm_name, bm_height)
                        st.session_state['1d_results'] = results
                        st.session_state['output_dir'] = output_dir
                        st.success("Adjustment Completed Successfully!")

                # --- Display Results & Downloads ---
                if '1d_results' in st.session_state:
                    res = st.session_state['1d_results']
                    target_dir = st.session_state.get('output_dir', default_dir)

                    st.markdown("---")
                    st.subheader("📊 Adjustment Metrics")
                    m1, m2 = st.columns(2)
                    m1.metric("Reference Variance (σ₀²)", f"{res['sigma0_sq']:.6f}")
                    m2.metric("Degrees of Freedom (DoF)", res['dof'])

                    res_col1, res_col2 = st.columns(2)
                    with res_col1:
                        st.write("📍 **Adjusted Station Heights**")
                        st.dataframe(res['stations'], use_container_width=True)
                    with res_col2:
                        st.write("📏 **Observation Residuals**")
                        st.dataframe(res['residuals'], use_container_width=True)

                    # Export Logic
                    st.markdown("---")
                    st.subheader("📥 Export Results")

                    # Option 1: Direct Save to Local Path
                    if st.button("📁 Save Files Directly to Local Directory"):
                        os.makedirs(target_dir, exist_ok=True)
                        excel_path = os.path.join(target_dir, "1D_Adjustment_Results.xlsx")
                        csv_path = os.path.join(target_dir, "1D_Adjustment_Results.csv")

                        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                            res['stations'].to_excel(writer, sheet_name='Adjusted Heights', index=False)
                            res['residuals'].to_excel(writer, sheet_name='Residuals', index=False)

                        combined_df = pd.concat([res['stations'], res['residuals']], axis=1)
                        combined_df.to_csv(csv_path, index=False)
                        st.success(f"Files saved to `{target_dir}`")

                    # Option 2: Web Browser Download
                    export_format = st.radio("Download via Browser:", ["Excel (.xlsx)", "CSV (.csv)"], horizontal=True)
                    if export_format == "Excel (.xlsx)":
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            res['stations'].to_excel(writer, sheet_name='Adjusted Heights', index=False)
                            res['residuals'].to_excel(writer, sheet_name='Residuals', index=False)
                        st.download_button(
                            label="📥 Download Excel File",
                            data=buffer.getvalue(),
                            file_name="1D_Adjustment_Results.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        combined_df = pd.concat([res['stations'], res['residuals']], axis=1)
                        csv_bytes = combined_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download CSV File",
                            data=csv_bytes,
                            file_name="1D_Adjustment_Results.csv",
                            mime="text/csv"
                        )

        except Exception as e:
            st.error(f"Error processing 1D levelling data: {e}")

@st.dialog("📐 2D Network Adjustment (Traversing)", width="large")
def show_2d_module():
    st.caption("2D least-squares adjustment for angles, azimuths, and horizontal distances.")
    st.file_uploader("Upload Control Points (.csv)", type=["csv"], key="2d_pts")
    st.file_uploader("Upload Distance/Angle Obs (.csv)", type=["csv"], key="2d_obs")
    
    st.info("📌 **Module Code Placeholder:** Paste your 2D Traversing algorithm logic here.")
    
    if st.button("Compute 2D Adjustment", type="primary"):
        st.success("2D Computation completed!")

@st.dialog("🛰️ 3D Network Adjustment (GNSS)", width="large")
def show_3d_module():
    st.caption("3D adjustment incorporating baseline vectors (dX, dY, dZ) and covariance matrices.")
    st.file_uploader("Upload RINEX / Baseline File", key="3d_gnss")
    st.selectbox("Reference Frame / Datum", ["WGS84", "ITRF2020", "Local Localized Datum"])
    
    st.info("📌 **Module Code Placeholder:** Paste your 3D GNSS algorithm logic here.")
    
    if st.button("Execute 3D Adjustment", type="primary"):
        st.success("3D Processing completed!")

@st.dialog("🗺️ Map Projection", width="large")
def show_map_module():
    st.caption("Convert between Geographic (Lat/Lon) and Projected Coordinates (UTM/Local).")
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("Transformation Type", ["Geographic to UTM", "UTM to Geographic"])
        st.number_input("Latitude / Northing", value=1.4927)
    with col2:
        st.number_input("Longitude / Easting", value=103.7414)
        st.selectbox("Ellipsoid", ["WGS84", "GRS80", "Kertau 1948"])
        
    st.info("📌 **Module Code Placeholder:** Paste your Map Projection math here.")
    
    if st.button("Convert Coordinates", type="primary"):
        st.success("Conversion executed!")

@st.dialog("📍 Real-Time Tracking", width="large")
def show_tracking_module():
    st.caption("Live streaming of spatial positions and trajectory visualization.")
    st.text_input("NMEA / RTCM Stream URL", "tcp://127.0.0.1:9000")
    st.map(data={"lat": [1.4927], "lon": [103.7414]}, zoom=12)
    
    st.info("📌 **Module Code Placeholder:** Paste your Live Tracking receiver code here.")

# ---------------------------------------------------------
# DASHBOARD GRID (5 Module Cards on 1 Page)
# ---------------------------------------------------------

# Row 1: First 3 Modules
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📏 1D Levelling")
    st.write("1D least-squares adjustment for vertical levelling networks.")
    if st.button("Open 1D Module", key="btn_1d", use_container_width=True):
        show_1d_module()

with col2:
    st.markdown("### 📐 2D Traversing")
    st.write("2D adjustment for distance, horizontal angle, and azimuth observations.")
    if st.button("Open 2D Module", key="btn_2d", use_container_width=True):
        show_2d_module()

with col3:
    st.markdown("### 🛰️ 3D GNSS")
    st.write("3D network adjustment using spatial baseline vectors and covariance.")
    if st.button("Open 3D Module", key="btn_3d", use_container_width=True):
        show_3d_module()

st.write("") # Spacing

# Row 2: Remaining 2 Modules
col4, col5, _ = st.columns([1, 1, 1])

with col4:
    st.markdown("### 🗺️ Map Projection")
    st.write("Coordinate conversion between Ellipsoidal and Grid projections.")
    if st.button("Open Projection Module", key="btn_proj", use_container_width=True):
        show_map_module()

with col5:
    st.markdown("### 📍 Real-Time Tracking")
    st.write("Stream spatial positions live and plot trajectory data.")
    if st.button("Open Tracking Module", key="btn_track", use_container_width=True):
        show_tracking_module()

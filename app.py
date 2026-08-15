import io
import streamlit as st
import pandas as pd
from network_1d import adjust_1d_network

# Page Configuration
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

st.markdown("<h1 class='main-title'>GEOADJUST</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>", unsafe_allow_html=True)

st.write("---")
st.subheader("Select a Module")

@st.dialog("📏 1D Network Adjustment (Levelling)", width="large")
def show_1d_module():
    st.caption("MATLAB-Aligned Least Squares 1D Network Adjustment Engine.")
    
    col_bm1, col_bm2 = st.columns(2)
    with col_bm1:
        bm_name = st.text_input("Benchmark Station Name (Fixed Datum)", value="BMFGHT")
    with col_bm2:
        bm_height = st.number_input("Benchmark Height (m)", value=100.0, step=0.0001, format="%.4f")
    
    with st.expander("ℹ️ Click to view required column format"):
        st.markdown("""
        Your uploaded file (**`.csv`** or **`.xlsx`**) should follow this structure:
        
        | Col Index | Name | Description |
        |---|---|---|
        | Col 1 | `From_Point` | Station From |
        | Col 2 | `To_Point` | Station To |
        | Col 3 | `dH_m` | Observed Height Diff (m) |
        | Col 4 | `Dist_km` | Line Length (km) - *Optional* |
        | Col 5 | `StdDev_mm` | Std Deviation (mm) - *Optional* |
        """)

    uploaded_file = st.file_uploader("Upload Levelling File (.csv or .xlsx)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            has_header = st.checkbox("File contains header row", value=False)
            
            if uploaded_file.name.endswith('.csv'):
                df_input = pd.read_csv(uploaded_file, header=0 if has_header else None)
            else:
                df_input = pd.read_excel(uploaded_file, header=0 if has_header else None)

            expected_cols = ["From_Point", "To_Point", "dH_m", "Dist_km", "StdDev_mm"]
            if not has_header or len(df_input.columns) < 3:
                rename_map = {i: expected_cols[i] for i in range(min(len(df_input.columns), 5))}
                df_input = df_input.rename(columns=rename_map)

            st.write("📋 **Input Data Preview:**")
            st.dataframe(df_input.head(5), use_container_width=True)

            # Trigger Calculation and store explicitly in session_state
            if st.button("🚀 Run MATLAB-Aligned 1D Adjustment", type="primary", use_container_width=True):
                with st.spinner("Computing Adjustment Matrix..."):
                    st.session_state['1d_results'] = adjust_1d_network(df_input, bm_name, bm_height)
                    st.success("Adjustment Executed Successfully!")

            # Render Results & Station Outputs
            if '1d_results' in st.session_state:
                res = st.session_state['1d_results']

                st.markdown("---")
                st.subheader("📊 Adjustment Summary Statistics")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Ref Variance (σ₀²)", f"{res['sigma0_sq']:.6f}")
                m2.metric("Ref Std Dev (σ₀)", f"{res['sigma0']:.5f}")
                m3.metric("Degrees of Freedom", res['dof'])
                m4.metric("Sum VᵀPV", f"{res['vTpv']:.5f}")

                # Display Per-Station Results Table Clearly
                st.markdown("---")
                st.subheader("📍 Adjusted Heights & Station Coordinates")
                st.dataframe(
                    res['stations'], 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Station": st.column_config.TextColumn("Station ID"),
                        "Adjusted Height (m)": st.column_config.NumberColumn("Adjusted Height (m)", format="%.4f"),
                        "Std Dev (mm)": st.column_config.NumberColumn("Std Error (mm)", format="%.2f"),
                        "Status": st.column_config.TextColumn("Datum Status")
                    }
                )

                st.subheader("📏 Line Residuals & Weights")
                st.dataframe(res['residuals'], use_container_width=True, hide_index=True)

                # Export & Download Section
                st.markdown("---")
                st.subheader("💾 Export Station Results")
                
                custom_filename = st.text_input("Output Filename:", value="1D_Station_Heights_Results")
                
                col_dl1, col_dl2 = st.columns(2)

                # Excel Download Buffer
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    res['stations'].to_excel(writer, sheet_name='Station Heights', index=False)
                    res['residuals'].to_excel(writer, sheet_name='Line Residuals', index=False)
                
                with col_dl1:
                    st.download_button(
                        label="📥 Download Excel Report (.xlsx)",
                        data=excel_buffer.getvalue(),
                        file_name=f"{custom_filename}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                # CSV Download Buffer
                csv_bytes = res['stations'].to_csv(index=False).encode('utf-8')
                with col_dl2:
                    st.download_button(
                        label="📥 Download Stations CSV (.csv)",
                        data=csv_bytes,
                        file_name=f"{custom_filename}_stations.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

        except Exception as e:
            st.error(f"Error executing 1D adjustment: {e}")

@st.dialog("📐 2D Network Adjustment (Traversing)", width="large")
def show_2d_module():
    st.caption("2D least-squares adjustment for angles, azimuths, and horizontal distances.")
    st.file_uploader("Upload Control Points (.csv)", type=["csv"], key="2d_pts")
    st.file_uploader("Upload Distance/Angle Obs (.csv)", type=["csv"], key="2d_obs")
    if st.button("Compute 2D Adjustment", type="primary"):
        st.success("2D Computation completed!")

@st.dialog("🛰️ 3D Network Adjustment (GNSS)", width="large")
def show_3d_module():
    st.caption("3D adjustment incorporating baseline vectors (dX, dY, dZ) and covariance matrices.")
    st.file_uploader("Upload RINEX / Baseline File", key="3d_gnss")
    st.selectbox("Reference Frame / Datum", ["WGS84", "ITRF2020", "Local Localized Datum"])
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
    if st.button("Convert Coordinates", type="primary"):
        st.success("Conversion executed!")

@st.dialog("📍 Real-Time Tracking", width="large")
def show_tracking_module():
    st.caption("Live streaming of spatial positions and trajectory visualization.")
    st.text_input("NMEA / RTCM Stream URL", "tcp://127.0.0.1:9000")
    st.map(data={"lat": [1.4927], "lon": [103.7414]}, zoom=12)

# Module Selection Dashboard Grid
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

st.write("")

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

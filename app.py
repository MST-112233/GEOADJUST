import streamlit as st

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
    st.file_uploader("Upload Levelling Observation File (.csv)", type=["csv"])
    st.number_input("Benchmark Height (m)", value=100.0, step=0.001)
    
    st.info("📌 **Module Code Placeholder:** Paste your 1D Levelling algorithm logic here.")
    
    if st.button("Run 1D Adjustment", type="primary"):
        st.success("Module executed successfully!")

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
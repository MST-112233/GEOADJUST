import io
import os
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
from streamlit_js_eval import get_geolocation

import folium
from streamlit_folium import st_folium

from network_1d import adjust_1d_network
from network_3d import adjust_3d_network

# --- Import GDTS Datum Transformation Engine ---
import datum_transform as dt

# --- Helper Functions for Coordinate Parsing & Formatting ---
def parse_coordinate_to_deg(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    pattern = r'^\s*([+-]?\d+)[°\s_dD-]+(\d+)[′\'\s_mM-]+(\d+(?:\.\d+)?)[″"\s_sS]*\s*$'
    match = re.match(pattern, val_str)
    if match:
        d = float(match.group(1))
        m = float(match.group(2))
        s = float(match.group(3))
        sign = -1.0 if d < 0 or val_str.startswith('-') else 1.0
        return sign * (abs(d) + m / 60.0 + s / 3600.0)
    try:
        return float(val_str)
    except ValueError:
        raise ValueError(f"Unable to parse coordinate: '{val}'")

def format_deg_to_dms_str(deg):
    if pd.isna(deg) or deg is None:
        return ""
    d, m, s = dt.deg_to_dms(deg)
    return f"{d}° {m}' {s:.4f}\""


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
    .user-banner {
        background-color: #E3F2FD;
        padding: 10px 15px;
        border-radius: 8px;
        color: #0D47A1;
        font-weight: 600;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- GLOBAL SESSION REGISTRY FOR 2-HOUR EXPIRY & INTERCONNECTED ROOMS ---
@st.cache_resource
def get_global_app_registry():
    return {}

APP_REGISTRY = get_global_app_registry()
TIMEZONE = ZoneInfo("Asia/Kuala_Lumpur")
INACTIVITY_TIMEOUT_HOURS = 2
COLOR_PALETTE = ["#1E88E5", "#E53935", "#43A047", "#FB8C00", "#8E24AA", "#FDD835", "#00ACC1"]


# =========================================================
# FRONT LOGIN SCREEN
# =========================================================
if "app_auth" not in st.session_state:
    st.session_state["app_auth"] = {
        "logged_in": False,
        "username": "",
        "room_id": "",
        "password": ""
    }

auth = st.session_state["app_auth"]

if not auth["logged_in"]:
    st.markdown("<h1 class='main-title'>🌐 GEOADJUST</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        st.markdown(
            """
            <div style="background-color: #ffffff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08);">
                <h3 style="color: #1E88E5; text-align: center; margin-bottom: 5px;">🔐 Portal Login</h3>
                <p style="color: #666; font-size: 0.85rem; text-align: center; margin-bottom: 20px;">Enter identical Room ID and Password to collaborate and track positions.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        with st.form("portal_login_form"):
            input_username = st.text_input("👤 Username", value="")
            input_room = st.text_input("🏠 Room ID", value="")
            input_pass = st.text_input("🔑 Password", type="password", value="")
            
            submit_portal = st.form_submit_button("🚀 Enter GEOADJUST", use_container_width=True, type="primary")
            
            if submit_portal:
                if not input_username.strip() or not input_room.strip() or not input_pass.strip():
                    st.error("Please fill in Username, Room ID, and Password.")
                else:
                    room_key = input_room.strip()
                    user_key = input_username.strip()
                    now_ts = datetime.now(TIMEZONE)
                    
                    if room_key in APP_REGISTRY:
                        room_info = APP_REGISTRY[room_key]
                        last_active = room_info.get("last_active", now_ts)
                        if (now_ts - last_active) > timedelta(hours=INACTIVITY_TIMEOUT_HOURS):
                            APP_REGISTRY.pop(room_key, None)
                            st.warning("⚠️ Previous session for this room expired due to 2 hours of inactivity. Starting fresh session.")
                        else:
                            if room_info["password"] != input_pass:
                                st.error("Incorrect password for this active room!")
                                st.stop()
                    
                    if room_key not in APP_REGISTRY:
                        APP_REGISTRY[room_key] = {
                            "password": input_pass,
                            "last_active": now_ts,
                            "data_store": {},
                            "locations": {},
                            "levelling_positions": []
                        }
                    
                    auth["logged_in"] = True
                    auth["username"] = user_key
                    auth["room_id"] = room_key
                    auth["password"] = input_pass
                    
                    st.success("Login Successful!")
                    st.rerun()
    st.stop()


# =========================================================
# MAIN GEOADJUST DASHBOARD (Post-Login)
# =========================================================

room_key = auth["room_id"]
if room_key in APP_REGISTRY:
    APP_REGISTRY[room_key]["last_active"] = datetime.now(TIMEZONE)
else:
    APP_REGISTRY[room_key] = {
        "password": auth["password"],
        "last_active": datetime.now(TIMEZONE),
        "data_store": {},
        "locations": {},
        "levelling_positions": []
    }

room_data = APP_REGISTRY[room_key]

st.markdown("<h1 class='main-title'>🌐 GEOADJUST</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>", unsafe_allow_html=True)

col_greet1, col_greet2 = st.columns([4, 1])
with col_greet1:
    st.markdown(
        f"""<div class="user-banner">
            <span>👋 Welcome, <b>{auth['username']}</b>!</span>
            <span>🏠 Room ID: <b>{auth['room_id']}</b></span>
        </div>""",
        unsafe_allow_html=True
    )
with col_greet2:
    if st.button("🚪 Log Out", use_container_width=True):
        auth["logged_in"] = False
        st.rerun()

# --- 2. Main Navigation Tabs ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📏 1D Levelling",
    "🛰️ 3D GNSS",
    "📍 Real-Time Tracking",
    "🧭 Datum Transformation",
])

# =========================================================
# TAB 1: 1D NETWORK ADJUSTMENT WITH AUTO-POSITIONING
# =========================================================
with tab1:
    st.header("📏 1D Leveling Network Adjustment")

    input_method = st.radio(
        "Select Data Input Method:",
        ["📁 Upload CSV / Excel File", "✍️ Step-by-Step Manual Key-in Wizard"],
        horizontal=True,
        key="1d_input_method"
    )

    st.markdown("---")
    df_input = None

    if input_method == "📁 Upload CSV / Excel File":
        col_cfg1, col_cfg2 = st.columns(2)
        with col_cfg1:
            bm_name = st.text_input("Fixed Benchmark Station Name", value="BM1", key="1d_bm_name_upl")
            has_header = st.checkbox("File contains a header row", value=True, key="1d_header")
        with col_cfg2:
            bm_height = st.number_input("Benchmark Known RL (m)", value=100.0000, step=0.0001, format="%.4f", key="1d_bm_height_upl")
            custom_filename = st.text_input("Output Filename Base", value="1D_Adjustment_Report", key="1d_out_name_upl")

        uploaded_file = st.file_uploader("Upload Leveling File (.csv or .xlsx)", type=["csv", "xlsx"], key="1d_file_uploader")

        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_input = pd.read_csv(uploaded_file, header=0 if has_header else None)
                else:
                    df_input = pd.read_excel(uploaded_file, header=0 if has_header else None)

                expected_cols = ["From", "To", "Backsight (m)", "Foresight (m)", "Distance (m)"]
                if not has_header or len(df_input.columns) < 3:
                    rename_map = {i: expected_cols[i] for i in range(min(len(df_input.columns), 5))}
                    df_input = df_input.rename(columns=rename_map)

                st.subheader("📋 Input Data Preview")
                st.dataframe(df_input.head(10), use_container_width=True)

            except Exception as e:
                st.error(f"Data loading error: {e}")

    else:
        if "wizard_step" not in st.session_state:
            st.session_state["wizard_step"] = 1
        if "manual_records" not in st.session_state:
            st.session_state["manual_records"] = []
        if "proj_meta" not in st.session_state:
            st.session_state["proj_meta"] = {
                "name": "Jalan Contoh 2026",
                "date": datetime.now().date(),
                "instrument": "Leica NA320",
                "observer": auth["username"],
                "bm_name": "BM1",
                "bm_height": 100.0000
            }

        step = st.session_state["wizard_step"]
        st.markdown(f"### 🧙‍♂️ Wizard Step {step} of 3")

        if step == 1:
            st.subheader("Step 1: Project Information & Benchmark Setup")
            meta = st.session_state["proj_meta"]
            
            p_name = st.text_input("Project Name", value=meta["name"], key="w_pname")
            p_date = st.date_input("Date", value=meta["date"], key="w_pdate")
            p_inst = st.text_input("Name of Instrument", value=meta["instrument"], key="w_pinst")
            p_obs = st.text_input("Observer", value=meta["observer"], key="w_pobs")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                p_bm_name = st.text_input("Fixed Benchmark Station Name", value=meta["bm_name"], key="w_bm_name")
            with col_b2:
                p_bm_height = st.number_input("Benchmark Known RL (m)", value=meta["bm_height"], format="%.4f", key="w_bm_height")

            if st.button("Next ➔ Enter Observations", type="primary", use_container_width=True):
                st.session_state["proj_meta"] = {
                    "name": p_name, "date": p_date, "instrument": p_inst,
                    "observer": p_obs, "bm_name": p_bm_name, "bm_height": p_bm_height
                }
                st.session_state["wizard_step"] = 2
                st.rerun()

        elif step == 2:
            st.subheader("Step 2: Enter Backsight (BS) & Foresight (FS) Observations")
            meta = st.session_state["proj_meta"]
            st.info(f"Project: **{meta['name']}** | Benchmark: **{meta['bm_name']} ({meta['bm_height']:.4f} m)**")

            # --- Auto-Take Positioning Option for 1D Levelling ---
            st.markdown("#### 📍 Auto GPS Positioning for Levelling Station")
            auto_gps_enabled = st.checkbox("Enable Auto-Take GPS Positioning for current observation", value=True, key="auto_gps_1d_toggle")
            show_gps_details = st.checkbox("👁️ View Captured GPS Coordinates", value=True, key="show_gps_1d_toggle")

            current_gps_lat, current_gps_lon = None, None
            if auto_gps_enabled:
                loc_1d = get_geolocation(component_key=f"geo_1d_{datetime.now().second}")
                if loc_1d and "coords" in loc_1d:
                    current_gps_lat = loc_1d["coords"].get("latitude")
                    current_gps_lon = loc_1d["coords"].get("longitude")
                    if show_gps_details:
                        st.success(f"🛰️ GPS Position Acquired: Lat: `{current_gps_lat:.6f}`, Lon: `{current_gps_lon:.6f}`")

            with st.form("obs_form", clear_on_submit=True):
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    from_stn = st.text_input("From Station (e.g. BM1 or P1)", value=meta["bm_name"])
                    bs_val = st.number_input("Backsight (BS) value (m)", value=1.523, format="%.4f")
                with col_o2:
                    to_stn = st.text_input("To Station (e.g. P1 or P2)", value="P1")
                    fs_val = st.number_input("Foresight (FS) value (m)", value=0.612, format="%.4f")
                
                dist_val = st.number_input("Distance (m) [Optional]", value=120.5, format="%.2f")

                submitted = st.form_submit_button("➕ Add Observation Record", use_container_width=True)
                if submitted:
                    record_entry = {
                        "From": from_stn.strip(),
                        "To": to_stn.strip(),
                        "Backsight (m)": bs_val,
                        "Foresight (m)": fs_val,
                        "Distance (m)": dist_val,
                        "Observer": auth["username"],
                        "Timestamp": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
                    }
                    if current_gps_lat and current_gps_lon:
                        record_entry["Latitude"] = current_gps_lat
                        record_entry["Longitude"] = current_gps_lon
                        # Push to room levelling positions for tracking monitoring
                        room_data["levelling_positions"].append({
                            "station": to_stn.strip(),
                            "lat": current_gps_lat,
                            "lon": current_gps_lon,
                            "observer": auth["username"],
                            "timestamp": datetime.now(TIMEZONE).strftime("%H:%M:%S")
                        })

                    st.session_state["manual_records"].append(record_entry)
                    st.success(f"Added observation from {from_stn} to {to_stn} successfully!")

            if st.session_state["manual_records"]:
                st.markdown("#### 📑 Collected Field Observations So Far:")
                df_collected = pd.DataFrame(st.session_state["manual_records"])
                st.dataframe(df_collected, use_container_width=True, hide_index=True)

                if st.button("🗑️ Clear All Records", use_container_width=True):
                    st.session_state["manual_records"] = []
                    st.rerun()

            col_nav1, col_nav2 = st.columns(2)
            with col_nav1:
                if st.button("⬅️ Back to Project Info", use_container_width=True):
                    st.session_state["wizard_step"] = 1
                    st.rerun()
            with col_nav2:
                if st.button("Next ➔ Review & Compute", type="primary", use_container_width=True):
                    if not st.session_state["manual_records"]:
                        st.warning("Please add at least one observation record before proceeding.")
                    else:
                        st.session_state["wizard_step"] = 3
                        st.rerun()

        elif step == 3:
            st.subheader("Step 3: Review Collected Data & Compute Adjustment")
            meta = st.session_state["proj_meta"]
            
            st.markdown(f"**Project Name:** {meta['name']} | **Date:** {meta['date']} | **Instrument:** {meta['instrument']} | **Observer:** {meta['observer']}")
            st.markdown(f"**Benchmark:** {meta['bm_name']} ({meta['bm_height']:.4f} m)")

            df_input = pd.DataFrame(st.session_state["manual_records"])
            st.markdown("#### 📊 Final Review of Input Data")
            st.dataframe(df_input, use_container_width=True, hide_index=True)

            col_w_back, col_w_comp = st.columns(2)
            with col_w_back:
                if st.button("⬅️ Back to Add Observations", use_container_width=True):
                    st.session_state["wizard_step"] = 2
                    st.rerun()
            with col_w_comp:
                if st.button("🚀 Run 1D Adjustment", type="primary", use_container_width=True):
                    try:
                        res = adjust_1d_network(df_input, meta["bm_name"], meta["bm_height"])
                        st.session_state["results_1d"] = res
                        st.session_state["custom_filename_1d"] = f"1D_Report_{meta['name'].replace(' ', '_')}"
                        room_data["data_store"]["results_1d"] = res
                        st.success("Adjustment Complete!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Adjustment error: {e}")

    if input_method == "📁 Upload CSV / Excel File" and df_input is not None:
        bm_name = st.session_state.get("1d_bm_name_upl", "BM1")
        bm_height = st.session_state.get("1d_bm_height_upl", 100.0)
        custom_filename = st.session_state.get("1d_out_name_upl", "1D_Adjustment_Report")

        if st.button("🚀 Run 1D Adjustment", type="primary", use_container_width=True):
            with st.spinner("Computing Least Squares Adjustment..."):
                try:
                    res = adjust_1d_network(df_input, bm_name, bm_height)
                    st.session_state["results_1d"] = res
                    st.session_state["custom_filename_1d"] = custom_filename
                    room_data["data_store"]["results_1d"] = res
                    st.success("Adjustment Complete!")
                except Exception as e:
                    st.error(f"Adjustment error: {e}")

    if "results_1d" not in st.session_state and "results_1d" in room_data["data_store"]:
        st.session_state["results_1d"] = room_data["data_store"]["results_1d"]

    if "results_1d" in st.session_state:
        res = st.session_state["results_1d"]
        meta = st.session_state.get("proj_meta", {
            "name": "Jalan Contoh 2026", "date": datetime.now().date(),
            "instrument": "Leica NA320", "observer": auth["username"]
        })

        st.markdown("---")
        st.subheader("📊 Adjustment Summary Statistics")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ref Variance (σ₀²)", f"{res['sigma0_sq']:.6f}")
        m2.metric("Ref Std Dev (σ₀)", f"{res['sigma0']:.5f}")
        m3.metric("Degrees of Freedom", res["dof"])
        m4.metric("Chi-Square Test", res["chi2_status"])

        col_tbl1, col_tbl2 = st.columns(2)
        with col_tbl1:
            st.subheader("📍 Adjusted Reduced Levels (RL)")
            st.dataframe(res["stations"], use_container_width=True, hide_index=True)

        with col_tbl2:
            st.subheader("📏 Observation Residuals")
            st.dataframe(res["residuals"], use_container_width=True, hide_index=True)


# =========================================================
# TAB 2: 3D GNSS NETWORK ADJUSTMENT
# =========================================================
with tab2:
    st.header("🛰️ 3D GNSS Vector Network Adjustment")
    st.caption("MATLAB-Aligned Parametric 3D Geodetic Vector Least Squares Adjustment")

    col_3d_1, col_3d_2 = st.columns(2)
    with col_3d_1:
        stn_const_name = st.text_input("Fixed Station Name", value="SPGR", key="3d_const_name")
        has_header_3d = st.checkbox("File contains a header row", value=True, key="3d_header")
        custom_filename_3d = st.text_input("Output Filename Base", value="3D_GNSS_Adjustment_Results", key="3d_out_name")

    with col_3d_2:
        st.markdown("**Constrained Station Coordinates (ECEF)**")
        col_x, col_y, col_z = st.columns(3)
        with col_x:
            const_x = st.number_input("X (m)", value=-1468840.4040, format="%.4f", step=0.0001, key="3d_x")
        with col_y:
            const_y = st.number_input("Y (m)", value=6203485.7950, format="%.4f", step=0.0001, key="3d_z")
        with col_z:
            const_z = st.number_input("Z (m)", value=200173.7140, format="%.4f", step=0.0001, key="3d_y")

    uploaded_file_3d = st.file_uploader("Upload Baseline Vector File (.xlsx or .csv)", type=["xlsx", "csv"], key="3d_file_uploader")

    if uploaded_file_3d is not None:
        try:
            if uploaded_file_3d.name.endswith(".csv"):
                df_input_3d = pd.read_csv(uploaded_file_3d, header=0 if has_header_3d else None)
            else:
                df_input_3d = pd.read_excel(uploaded_file_3d, header=0 if has_header_3d else None)

            st.subheader("📋 Input Vector Preview")
            st.dataframe(df_input_3d.head(10), use_container_width=True)

            if st.button("🚀 Run 3D Adjustment", type="primary", use_container_width=True, key="btn_run_3d"):
                with st.spinner("Computing 3D Least Squares..."):
                    Ta_coords = [const_x, const_y, const_z]
                    res3d = adjust_3d_network(df_input_3d, const_name=stn_const_name, Ta=Ta_coords, jns=1)
                    st.session_state["results_3d"] = res3d
                    room_data["data_store"]["results_3d"] = res3d
                    st.success("3D Network Adjustment Complete!")

        except Exception as e:
            st.error(f"Data loading error: {e}")

    if "results_3d" not in st.session_state and "results_3d" in room_data["data_store"]:
        st.session_state["results_3d"] = room_data["data_store"]["results_3d"]

    if "results_3d" in st.session_state:
        res3d = st.session_state["results_3d"]
        st.markdown("---")
        st.subheader("📊 3D Adjustment Summary Statistics")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ref Variance (σ₀²)", f"{res3d['sigma0_sq']:.6f}")
        m2.metric("Ref Std Dev (σ₀)", f"{res3d['sigma0']:.5f}")
        m3.metric("Degrees of Freedom", res3d["dof"])
        m4.metric("Sum VᵀPV", f"{res3d['vTpv']:.5f}")


# =========================================================
# TAB 3: REAL-TIME TRACKING & INTERCONNECTED MONITORING
# =========================================================
with tab3:
    st.header("📍 Real-Time Tracking & Room Collaboration")
    st.info(f"Active Room Session: `{auth['room_id']}` | Logged in as: `{auth['username']}`")
    st.caption("All users sharing the same Room ID and Password are interconnected and can monitor each other's live positions and 1D levelling stations here.")

    # Auto-refresh every 10 seconds to fetch live locations
    refresh_count = st_autorefresh(interval=10000, key="tracking_autorefresh_t3")

    # Get current user geolocation
    loc = get_geolocation(component_key=f"geo_t3_{refresh_count}")
    now_ts = datetime.now(TIMEZONE)

    if loc and "coords" in loc:
        coords = loc["coords"]
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        alt = coords.get("altitude") or 0.0
        acc = coords.get("accuracy") or 0.0
        
        # Store user location in global room data
        room_data["locations"][auth["username"]] = {
            "latitude": lat,
            "longitude": lon,
            "altitude_m": alt,
            "accuracy_m": acc,
            "updated_at": now_ts.strftime("%Y-%m-%d %H:%M:%S")
        }

    # Display active members & locations in the room
    col_map, col_info = st.columns([2, 1])

    with col_info:
        st.subheader("👥 Room Members & Stations")
        active_locations = room_data.get("locations", {})
        if active_locations:
            df_locs = pd.DataFrame([
                {"User": u, "Lat": d["latitude"], "Lon": d["longitude"], "Updated": d["updated_at"]}
                for u, d in active_locations.items()
            ])
            st.dataframe(df_locs, use_container_width=True, hide_index=True)
        else:
            st.info("Awaiting GPS location signal from users...")

        st.markdown("#### 📏 Auto-Captured Levelling Stations")
        lev_pos = room_data.get("levelling_positions", [])
        if lev_pos:
            df_lev_pos = pd.DataFrame(lev_pos)
            st.dataframe(df_lev_pos, use_container_width=True, hide_index=True)
        else:
            st.info("No auto-captured 1D levelling stations yet.")

    with col_map:
        st.subheader("🗺️ Live Team Map")
        # Initialize Folium Map centered on Malaysia or user's location
        center_lat = 3.1390
        center_lon = 101.6869
        if active_locations:
            first_user = list(active_locations.values())[0]
            center_lat = first_user["latitude"]
            center_lon = first_user["longitude"]

        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

        # Add user position markers
        for idx, (usr, info) in enumerate(active_locations.items()):
            color = COLOR_PALETTE[idx % len(COLOR_PALETTE)]
            folium.Marker(
                [info["latitude"], info["longitude"]],
                popup=f"<b>User:</b> {usr}<br><b>Updated:</b> {info['updated_at']}",
                tooltip=usr,
                icon=folium.Icon(color="blue" if usr == auth["username"] else "orange", icon="user", prefix="fa")
            ).add_to(m)

        # Add 1D Levelling station auto-positions
        for lev in lev_pos:
            folium.CircleMarker(
                location=[lev["lat"], lev["lon"]],
                radius=8,
                color="#43A047",
                fill=True,
                fill_color="#43A047",
                popup=f"<b>Station:</b> {lev['station']}<br><b>Observer:</b> {lev['observer']}<br><b>Time:</b> {lev['timestamp']}",
                tooltip=f"Station: {lev['station']}"
            ).add_to(m)

        st_folium(m, width=700, height=450, key=f"folium_map_{refresh_count}")


# =========================================================
# TAB 4: DATUM TRANSFORMATION
# =========================================================
with tab4:
    st.header("🧭 Geodetic Datum Transformation & Map Projection")

    mode = st.radio(
        "Select Operation Mode:",
        ["3-Dimensional Transformation", "Map Projection", "Geodetic Tools (Conversion)"],
        horizontal=True,
        key="gdts_mode",
    )
    st.markdown("---")

    if mode == "3-Dimensional Transformation":
        st.subheader("📐 3D Datum Transformation")
        region = st.selectbox("Select Region / Zone:", ["Peninsular Malaysia", "Sabah and Sarawak"], key="trans_region")
        modules = ["1. GDM2000 to PMSGN94", "2. PMSGN94 to GDM2000"] if region == "Peninsular Malaysia" else ["1. GDM2000 to EMSGN97", "2. EMSGN97 to GDM2000"]
        selected_module = st.selectbox("Transformation Module:", modules, key="trans_module_sel")
        module_key = selected_module.split(". ", 1)[1]
        from_name, to_name = [x.strip() for x in module_key.split(" to ")]

        col_in1, col_in2, col_in3 = st.columns(3)
        with col_in1:
            lat_in = st.number_input("Latitude (Decimal Degrees)", value=1.4833333, format="%.5f", key="trans_dd_lat")
        with col_in2:
            lon_in = st.number_input("Longitude (Decimal Degrees)", value=103.7500000, format="%.5f", key="trans_dd_lon")
        with col_in3:
            h_in = st.number_input("Ellipsoidal Height (m)", value=10.000, format="%.3f", key="trans_h_in")
            stn_name = st.text_input("Station Name", value="STN01", key="trans_stn_name")

        if st.button("⚡ Transform Coordinates", type="primary", use_container_width=True, key="btn_transform"):
            lat_out, lon_out, h_out = dt.bursa_wolf_transform(lat_in, lon_in, h_in, module_key)
            st.success("Transformation Successful!")
            df_res = pd.DataFrame([{
                "Station": stn_name,
                f"{from_name} Lat": f"{lat_in:.6f}°", f"{from_name} Lon": f"{lon_in:.6f}°",
                f"{to_name} Lat": f"{lat_out:.6f}°", f"{to_name} Lon": f"{lon_out:.6f}°", f"{to_name} H (m)": f"{h_out:.3f}"
            }])
            st.dataframe(df_res, use_container_width=True, hide_index=True)

    elif mode == "Map Projection":
        st.subheader("🗺️ Map Projection System")
        proj_region = st.selectbox("Select Region:", ["Peninsular Malaysia", "Sabah and Sarawak"], key="proj_region")
        proj_modules = ["1. GDM2000 to RSO Geocentric", "2. RSO Geocentric to GDM2000"]
        sel_p_module = st.selectbox("Transformation Module:", proj_modules, key="proj_module_sel")
        module_title = sel_p_module.split(". ", 1)[1]
        from_name, to_name = [x.strip() for x in module_title.split(" to ")]

        col_i1, col_i2 = st.columns(2)
        with col_i1:
            p_dd_lat = st.number_input("Latitude (Decimal Degrees)", value=1.4833333, format="%.5f", key="p_dd_lat")
        with col_i2:
            p_dd_lon = st.number_input("Longitude (Decimal Degrees)", value=103.7500000, format="%.5f", key="p_dd_lon")

        if st.button("🚀 Calculate Map Projection", type="primary", use_container_width=True, key="btn_calc_proj"):
            E, N = dt.latlon_to_rso(p_dd_lat, p_dd_lon)
            st.success("Projection Complete!")
            df_res = pd.DataFrame([{
                "Station": "STN_PROJ_01",
                f"{from_name} Lat": f"{p_dd_lat:.5f}°", f"{from_name} Lon": f"{p_dd_lon:.5f}°",
                f"{to_name} Easting (m)": f"{E:.3f}", f"{to_name} Northing (m)": f"{N:.3f}"
            }])
            st.dataframe(df_res, use_container_width=True, hide_index=True)

    elif mode == "Geodetic Tools (Conversion)":
        st.subheader("🌐 Geodetic Coordinate Conversion Tools")
        tool_choice = st.radio("Tool Selection:", ["Geographical to Cartesian", "Cartesian to Geographical"], horizontal=True, key="tool_choice")
        ellipsoid_name = st.selectbox("Select Pre-Defined Ellipsoid:", list(dt.ELLIPSOIDS.keys()), key="ell_sel")

        if tool_choice == "Geographical to Cartesian":
            col_g1, col_g2, col_g3 = st.columns(3)
            with col_g1:
                g_dd_lat = st.number_input("Latitude (Decimal Degrees)", value=1.4833333, format="%.5f", key="g_dd_lat")
            with col_g2:
                g_dd_lon = st.number_input("Longitude (Decimal Degrees)", value=103.7500000, format="%.5f", key="g_dd_lon")
            with col_g3:
                g_h = st.number_input("Ellipsoidal Height (m)", value=10.0, format="%.3f", key="g_h")

            if st.button("⚙️ Compute Cartesian (X, Y, Z)", type="primary", use_container_width=True, key="btn_geo_cart"):
                X, Y, Z = dt.geo_to_cartesian(g_dd_lat, g_dd_lon, g_h, ellipsoid_name)
                st.success("Conversion Computed Successfully!")
                df_res = pd.DataFrame([{
                    "Station": "STN_TOOL_01", "X (m)": f"{X:.4f}", "Y (m)": f"{Y:.4f}", "Z (m)": f"{Z:.4f}"
                }])
                st.dataframe(df_res, use_container_width=True, hide_index=True)
        else:
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                in_X = st.number_input("X (meters)", value=-1468840.4040, format="%.4f", key="in_x")
            with col_c2:
                in_Y = st.number_input("Y (meters)", value=6203485.7950, format="%.4f", key="in_y")
            with col_c3:
                in_Z = st.number_input("Z (meters)", value=200173.7140, format="%.4f", key="in_z")

            if st.button("⚙️ Compute Geographical (Lat, Lon, H)", type="primary", use_container_width=True, key="btn_cart_geo"):
                lat_deg, lon_deg, height = dt.cartesian_to_geo(in_X, in_Y, in_Z, ellipsoid_name)
                st.success("Conversion Computed Successfully!")
                df_res = pd.DataFrame([{
                    "Station": "STN_TOOL_01", "Latitude": f"{lat_deg:.6f}°", "Longitude": f"{lon_deg:.6f}°", "Height (m)": f"{height:.4f}"
                }])
                st.dataframe(df_res, use_container_width=True, hide_index=True)

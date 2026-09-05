import io
import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
from streamlit_js_eval import get_geolocation

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

# --- GLOBAL CROSS-DEVICE MEMORY REGISTRY ---
# This dictionary is shared across ALL devices/browsers connected to the app server instance.
@st.cache_resource
def get_global_room_registry():
    return {}

GLOBAL_ROOMS_REGISTRY = get_global_room_registry()

COLOR_PALETTE = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue", "darkpurple", "pink"]

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
# TAB 2: 3D GNSS NETWORK ADJUSTMENT
# =========================================================
with tab2:
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
# TAB 3: REAL-TIME TRACKING (CROSS-DEVICE OPENSTREETMAP MODULE)
# =========================================================
with tab3:
    if "user_room_session" not in st.session_state:
        st.session_state["user_room_session"] = {
            "authenticated": False,
            "room_id": "",
            "room_pass": "",
            "username": "",
            "role": "",
        }

    session = st.session_state["user_room_session"]

    # --- Step 1: Room Access Form ---
    if not session["authenticated"]:
        st.markdown("<br>", unsafe_allow_html=True)
        login_col1, login_col2, login_col3 = st.columns([1, 2, 1])

        with login_col2:
            st.markdown(
                """
                <div style="background-color: #ffffff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); text-align: center;">
                    <h2 style="color: #1E88E5; margin-bottom: 0px;">📍 GEOADJUST Tracking</h2>
                    <p style="color: #666; font-size: 0.95rem; margin-bottom: 20px;">Cross-Device Real-Time Location Sharing & Unified Chat</p>
                </div>
            """,
                unsafe_allow_html=True,
            )

            with st.form("room_login_form"):
                input_user = st.text_input("👤 Username", value="User_1")
                input_room = st.text_input("🏠 Room ID", value="DemoRoom")
                input_pass = st.text_input(
                    "🔑 Password", type="password", value="123456"
                )
                input_role = st.selectbox(
                    "🎯 Role",
                    ["Field Surveyor", "🏢 Control Center (Office)"],
                )

                submit_login = st.form_submit_button(
                    "🚀 Enter Room", use_container_width=True, type="primary"
                )

                if submit_login:
                    if not input_user or not input_room or not input_pass:
                        st.error("Please fill in Username, Room ID, and Password.")
                    else:
                        room_key = input_room.strip()

                        # Check or create room in global server memory
                        if room_key in GLOBAL_ROOMS_REGISTRY:
                            existing_pass = GLOBAL_ROOMS_REGISTRY[room_key]["password"]
                            if existing_pass != input_pass:
                                st.error("Incorrect Password for this active room!")
                                st.stop()
                        else:
                            GLOBAL_ROOMS_REGISTRY[room_key] = {
                                "password": input_pass,
                                "locations": {},        # { user_id: {lat, lon, alt, acc, updated_at, color} }
                                "unified_log": [],      # combined tracking & chat logs
                                "user_colors": {},
                            }

                        # Assign a persistent unique marker color to the user
                        room_data = GLOBAL_ROOMS_REGISTRY[room_key]
                        user_clean = input_user.strip()
                        if user_clean not in room_data["user_colors"]:
                            color_idx = len(room_data["user_colors"]) % len(COLOR_PALETTE)
                            room_data["user_colors"][user_clean] = COLOR_PALETTE[color_idx]

                        session["authenticated"] = True
                        session["username"] = user_clean
                        session["room_id"] = room_key
                        session["room_pass"] = input_pass
                        session["role"] = input_role
                        st.rerun()

            st.warning(
                "⚠️ **Notice**: GEOADJUST does not store data on a database server. All tracking and chat logs exist temporarily in active memory—download your CSV before leaving!"
            )

    # --- Step 2: Active Tracking Room Engine ---
    else:
        current_room = session["room_id"]
        user_id = session["username"]
        is_admin = "Control Center" in session["role"]
        room_data = GLOBAL_ROOMS_REGISTRY.get(current_room)

        if not room_data:
            st.error("Room session expired or room closed.")
            session["authenticated"] = False
            st.rerun()

        # Top Control Bar
        head_col1, head_col2 = st.columns([3, 1])
        with head_col1:
            st.subheader(f"📍 Room: `{current_room}`")
            st.caption(
                f"Logged in as **{user_id}** ({'Control Center Admin' if is_admin else 'Field Surveyor'})"
            )
        with head_col2:
            if st.button("🚪 Leave Room", use_container_width=True):
                if user_id in room_data["locations"]:
                    del room_data["locations"][user_id]
                session["authenticated"] = False
                st.rerun()

        # Auto-refresh UI and poll browser GPS every 10 seconds
        st_autorefresh(interval=10000, key="tracking_autorefresh")

        # Capture Geolocation with Altitude & Accuracy
        loc = get_geolocation()
        current_time_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        if loc and "coords" in loc:
            coords = loc["coords"]
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            alt = coords.get("altitude") if coords.get("altitude") is not None else 0.0
            acc = coords.get("accuracy") if coords.get("accuracy") is not None else 0.0

            user_color = room_data["user_colors"].get(user_id, "blue")

            # Update live marker state
            room_data["locations"][user_id] = {
                "user_id": user_id,
                "latitude": lat,
                "longitude": lon,
                "altitude_m": alt,
                "accuracy_m": acc,
                "updated_at": current_time_str,
                "color": user_color,
            }

            # Record to unified event log
            room_data["unified_log"].append({
                "Timestamp": current_time_str,
                "Room_ID": current_room,
                "User_ID": user_id,
                "Event_Type": "GPS_UPDATE",
                "Latitude": lat,
                "Longitude": lon,
                "Altitude_m": round(alt, 2),
                "Accuracy_m": round(acc, 2),
                "Chat_Message": "",
            })

            st.sidebar.success(
                f"📡 GPS Updated:\n* Lat/Lon: `{lat:.5f}, {lon:.5f}`\n* Alt: `{alt:.2f} m`\n* Acc: `±{acc:.2f} m`"
            )
        else:
            st.sidebar.warning("⏳ Awaiting Browser GPS Permissions...")

        # --- Main Layout Split ---
        col_map, col_chat = st.columns([2, 1])

        # --- Left Column: OpenStreetMap with Custom User Pins ---
        with col_map:
            st.subheader("🗺️ Live OpenStreetMap")

            active_users = list(room_data["locations"].values())
            if active_users:
                # Center map on the first active user's location
                avg_lat = active_users[0]["latitude"]
                avg_lon = active_users[0]["longitude"]

                m = folium.Map(location=[avg_lat, avg_lon], zoom_start=16, tiles="OpenStreetMap")

                for u in active_users:
                    popup_html = f"""
                    <b>User:</b> {u['user_id']}<br>
                    <b>Lat:</b> {u['latitude']:.5f}<br>
                    <b>Lon:</b> {u['longitude']:.5f}<br>
                    <b>Alt:</b> {u['altitude_m']:.2f} m<br>
                    <b>Acc:</b> ±{u['accuracy_m']:.2f} m<br>
                    <b>Time:</b> {u['updated_at']}
                    """
                    folium.Marker(
                        location=[u["latitude"], u["longitude"]],
                        popup=folium.Popup(popup_html, max_width=250),
                        tooltip=f"📍 {u['user_id']}",
                        icon=folium.Icon(color=u["color"], icon="info-sign"),
                    ).add_to(m)

                st_folium(m, width="100%", height=450, returned_objects=[])

                # Table displaying live coordinates and spatial metrics
                st.markdown("**Active Team Members**")
                df_active_display = pd.DataFrame(active_users)
                st.dataframe(
                    df_active_display[
                        ["user_id", "latitude", "longitude", "altitude_m", "accuracy_m", "updated_at"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "user_id": "User ID",
                        "latitude": "Latitude",
                        "longitude": "Longitude",
                        "altitude_m": "Altitude (m)",
                        "accuracy_m": "Accuracy (m)",
                        "updated_at": "Last Fix Time",
                    },
                )
            else:
                st.info("No active team members sharing GPS coordinates in this room.")

        # --- Right Column: Chat System ---
        with col_chat:
            st.subheader("💬 Room Chat")

            with st.form("send_chat_form", clear_on_submit=True):
                chat_msg = st.text_input("Message:")
                btn_send = st.form_submit_button("Send", use_container_width=True)

                if btn_send and chat_msg.strip():
                    room_data["unified_log"].append({
                        "Timestamp": current_time_str,
                        "Room_ID": current_room,
                        "User_ID": user_id,
                        "Event_Type": "CHAT_MESSAGE",
                        "Latitude": None,
                        "Longitude": None,
                        "Altitude_m": None,
                        "Accuracy_m": None,
                        "Chat_Message": chat_msg.strip(),
                    })
                    st.rerun()

            st.markdown("---")
            # Extract chat messages from unified log
            chat_events = [
                log for log in room_data["unified_log"] if log["Event_Type"] == "CHAT_MESSAGE"
            ]

            if chat_events:
                chat_container = st.container(height=300)
                with chat_container:
                    for msg in reversed(chat_events):
                        time_only = msg["Timestamp"].split(" ")[1]
                        st.markdown(f"**{msg['User_ID']}** ({time_only}): {msg['Chat_Message']}")
            else:
                st.caption("No chat messages sent in this room yet.")

        # --- Export Section: Unified Log (GPS Tracks + Chat Log Combined) ---
        st.markdown("---")
        st.subheader("💾 Unified Room History Export")
        st.caption("Download the consolidated spatial tracking log and chat message transcript combined into a single chronological CSV file.")

        if room_data["unified_log"]:
            df_unified = pd.DataFrame(room_data["unified_log"])
            csv_unified = df_unified.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="📥 Download Unified Track & Chat Log (.csv)",
                data=csv_unified,
                file_name=f"Unified_Room_Log_{current_room}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No room events recorded yet to download.")

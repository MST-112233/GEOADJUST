import io
import os
import pandas as pd
import streamlit as st
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
from streamlit_js_eval import get_geolocation

from network_1d import adjust_1d_network
from network_3d import adjust_3d_network

# --- 1. Page Configuration ---
st.set_page_config(page_title="GEOADJUST", page_icon="🌐", layout="wide")

# Supabase Credentials (Replace with your actual copied credentials)
SUPABASE_URL = "https://oqgmnsfxtmpbnqyqnqcg.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xZ21uc2Z4dG1wYm5xeXFucWNnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcwNjQ0MDksImV4cCI6MjEwMjY0MDQwOX0.8rSeA3bzCk2cZp6vPP43XipQTfrRAIRWUfONjEwdKwk"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

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
# TAB 3: REAL-TIME TRACKING (TEMPORARY IN-MEMORY MODULE)
# =========================================================
with tab3:
    # --- 1. Global In-Memory Storage Initialization ---
    # Stores room data temporarily in session memory without any SQL database
    if "global_rooms" not in st.session_state:
        st.session_state["global_rooms"] = {}

    if "user_room_session" not in st.session_state:
        st.session_state["user_room_session"] = {
            "authenticated": False,
            "room_id": "",
            "room_pass": "",
            "username": "",
            "role": "",
        }

    session = st.session_state["user_room_session"]

    # --- 2. Room Login & Access Form ---
    if not session["authenticated"]:
        st.markdown("<br>", unsafe_allow_html=True)
        login_col1, login_col2, login_col3 = st.columns([1, 2, 1])

        with login_col2:
            st.markdown(
                """
                <div style="background-color: #ffffff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); text-align: center;">
                    <h2 style="color: #1E88E5; margin-bottom: 0px;">📍 GEOADJUST Tracking</h2>
                    <p style="color: #666; font-size: 0.95rem; margin-bottom: 20px;">Temporary Session-Based Location Sharing & Chat</p>
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

                        # Validate password if room already exists in temporary memory
                        if room_key in st.session_state["global_rooms"]:
                            existing_pass = st.session_state["global_rooms"][room_key]["password"]
                            if existing_pass != input_pass:
                                st.error("Incorrect Password for this active room!")
                                st.stop()
                        else:
                            # Create new temporary room in memory
                            st.session_state["global_rooms"][room_key] = {
                                "password": input_pass,
                                "locations": {},        # { user_id: {lat, lon, updated_at} }
                                "location_history": [], # list of all recorded points
                                "chat_history": [],     # list of all messages
                            }

                        session["authenticated"] = True
                        session["username"] = input_user.strip()
                        session["room_id"] = room_key
                        session["room_pass"] = input_pass
                        session["role"] = input_role
                        st.rerun()

            st.warning(
                "⚠️ **Notice**: GEOADJUST does not store any data permanently. Download your tracking/chat logs before leaving!"
            )

    # --- 3. Active Room Engine ---
    else:
        current_room = session["room_id"]
        user_id = session["username"]
        is_admin = "Control Center" in session["role"]
        room_data = st.session_state["global_rooms"].get(current_room)

        # Handle edge-case if room memory was cleared
        if not room_data:
            st.error("Room session expired or server restarted.")
            session["authenticated"] = False
            st.rerun()

        # Top Navigation & Status Bar
        head_col1, head_col2 = st.columns([3, 1])
        with head_col1:
            st.subheader(f"📍 Room: `{current_room}`")
            st.caption(
                f"Logged in as **{user_id}** ({'Control Center Admin' if is_admin else 'Field Surveyor'})"
            )
        with head_col2:
            if st.button("🚪 Leave Room", use_container_width=True):
                # Remove active marker on exit
                if user_id in room_data["locations"]:
                    del room_data["locations"][user_id]
                session["authenticated"] = False
                st.rerun()

        # Auto-refresh app and trigger location capture every 10 seconds
        st_autorefresh(interval=10000, key="tracking_autorefresh")

        # --- Location Tracking Logic ---
        loc = get_geolocation()
        current_time_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        if loc and "coords" in loc:
            lat = loc["coords"]["latitude"]
            lon = loc["coords"]["longitude"]

            # 1. Update live active point in memory
            room_data["locations"][user_id] = {
                "user_id": user_id,
                "latitude": lat,
                "longitude": lon,
                "updated_at": current_time_str,
            }

            # 2. Append to temporary track history log
            room_data["location_history"].append({
                "room_id": current_room,
                "user_id": user_id,
                "latitude": lat,
                "longitude": lon,
                "recorded_at": current_time_str,
            })

            st.sidebar.success(f"📡 GPS Updated: {lat:.5f}, {lon:.5f}")
        else:
            st.sidebar.warning("⏳ Awaiting Browser GPS Permissions...")

        # --- Dashboard Layout ---
        col_map, col_chat = st.columns([2, 1])

        # --- Left Column: Map & Active Members ---
        with col_map:
            st.subheader("🗺️ Live Team Map")

            active_locs_list = list(room_data["locations"].values())
            if active_locs_list:
                df_active = pd.DataFrame(active_locs_list)
                st.map(df_active, latitude="latitude", longitude="longitude")

                st.markdown("**Active Team Members**")
                st.dataframe(
                    df_active[["user_id", "latitude", "longitude", "updated_at"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No active team members sharing GPS coordinates in this room.")

        # --- Right Column: Chat Room ---
        with col_chat:
            st.subheader("💬 Temporary Room Chat")

            # Chat Input Form
            with st.form("send_chat_form", clear_on_submit=True):
                chat_msg = st.text_input("Message:")
                btn_send = st.form_submit_button("Send", use_container_width=True)

                if btn_send and chat_msg:
                    room_data["chat_history"].append({
                        "room_id": current_room,
                        "user_id": user_id,
                        "message": chat_msg,
                        "sent_at": current_time_str,
                    })
                    st.rerun()

            # Display Chat Messages
            st.markdown("---")
            if room_data["chat_history"]:
                chat_container = st.container(height=250)
                with chat_container:
                    # Show messages starting from newest
                    for msg in reversed(room_data["chat_history"]):
                        st.markdown(f"**{msg['user_id']}** ({msg['sent_at'].split(' ')[1]}): {msg['message']}")
            else:
                st.caption("No chat messages sent yet.")

        # --- Export & Download Data Section ---
        st.markdown("---")
        st.subheader("💾 Export & Download Session Data")
        st.caption("Download your location track logs and room chats before closing your browser or leaving the room.")

        down_col1, down_col2 = st.columns(2)

        # Download 1: Location Tracking History
        with down_col1:
            if room_data["location_history"]:
                df_loc_export = pd.DataFrame(room_data["location_history"])
                csv_locs = df_loc_export.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label="📥 Download GPS Track Log (.csv)",
                    data=csv_locs,
                    file_name=f"GPS_Track_{current_room}_{user_id}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.info("No GPS tracks recorded yet to download.")

        # Download 2: Room Chat History
        with down_col2:
            if room_data["chat_history"]:
                df_chat_export = pd.DataFrame(room_data["chat_history"])
                csv_chats = df_chat_export.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label="📥 Download Room Chat Log (.csv)",
                    data=csv_chats,
                    file_name=f"Chat_Log_{current_room}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.info("No chat logs recorded yet to download.")

        except Exception as e:
            st.error(f"Failed to communicate with real-time backend: {e}")

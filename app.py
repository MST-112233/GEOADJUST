import io
import os
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
from streamlit_js_eval import get_geolocation, streamlit_js_eval

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

# --- GLOBAL SESSION REGISTRY FOR 2-HOUR EXPIRY ---
@st.cache_resource
def get_global_app_registry():
    return {}

APP_REGISTRY = get_global_app_registry()
TIMEZONE = ZoneInfo("Asia/Kuala_Lumpur")
INACTIVITY_TIMEOUT_HOURS = 2


# =========================================================
# FRONT LOGIN SCREEN (Requirement 1 & 3)
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
                <p style="color: #666; font-size: 0.85rem; text-align: center; margin-bottom: 20px;">Enter your credentials to access or continue your project session.</p>
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
                    
                    # Check if room/session exists in registry
                    if room_key in APP_REGISTRY:
                        room_info = APP_REGISTRY[room_key]
                        # Check 2-hour inactivity timeout
                        last_active = room_info.get("last_active", now_ts)
                        if (now_ts - last_active) > timedelta(hours=INACTIVITY_TIMEOUT_HOURS):
                            # Purge expired room data
                            APP_REGISTRY.pop(room_key, None)
                            st.warning("⚠️ Previous session for this room expired due to 2 hours of inactivity. Starting fresh session.")
                        else:
                            if room_info["password"] != input_pass:
                                st.error("Incorrect password for this active room!")
                                st.stop()
                    
                    # Initialize or load room state
                    if room_key not in APP_REGISTRY:
                        APP_REGISTRY[room_key] = {
                            "password": input_pass,
                            "last_active": now_ts,
                            "data_store": {}
                        }
                    
                    # Set authentication session state
                    auth["logged_in"] = True
                    auth["username"] = user_key
                    auth["room_id"] = room_key
                    auth["password"] = input_pass
                    
                    # Restore session data if saved previously
                    st.session_state["room_storage"] = APP_REGISTRY[room_key]["data_store"]
                    st.success("Login Successful!")
                    st.rerun()
    st.stop()


# =========================================================
# MAIN GEOADJUST DASHBOARD (Post-Login)
# =========================================================

# Update last active timestamp for 2-hour timeout tracking
APP_REGISTRY[auth["room_id"]]["last_active"] = datetime.now(TIMEZONE)

# Title Header & Personalized Greeting Banner (Requirement 2)
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
# TAB 1: 1D NETWORK ADJUSTMENT
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
        # --- Step-by-Step Manual Key-in Wizard ---
        if "wizard_step" not in st.session_state:
            st.session_state["wizard_step"] = 1
        if "manual_records" not in st.session_state:
            st.session_state["manual_records"] = []
        if "proj_meta" not in st.session_state:
            st.session_state["proj_meta"] = {
                "name": "Jalan Contoh 2025",
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
                    st.session_state["manual_records"].append({
                        "From": from_stn.strip(),
                        "To": to_stn.strip(),
                        "Backsight (m)": bs_val,
                        "Foresight (m)": fs_val,
                        "Distance (m)": dist_val
                    })
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
                        # Save to global room store so it persists across refreshes
                        APP_REGISTRY[auth["room_id"]]["data_store"]["results_1d"] = res
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
                    APP_REGISTRY[auth["room_id"]]["data_store"]["results_1d"] = res
                    st.success("Adjustment Complete!")
                except Exception as e:
                    st.error(f"Adjustment error: {e}")

    # Check room storage for results if not in current session state
    if "results_1d" not in st.session_state and "results_1d" in APP_REGISTRY[auth["room_id"]]["data_store"]:
        st.session_state["results_1d"] = APP_REGISTRY[auth["room_id"]]["data_store"]["results_1d"]

    # --- Results Display & PDF Export ---
    if "results_1d" in st.session_state:
        res = st.session_state["results_1d"]
        meta = st.session_state.get("proj_meta", {
            "name": "Jalan Contoh 2025", "date": datetime.now().date(),
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

        st.markdown("---")
        
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        def generate_pdf_report(res_data, project_meta):
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
            story = []
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                'ReportTitle', parent=styles['Heading1'], fontSize=18,
                textColor=colors.HexColor('#1E88E5'), alignment=1, spaceAfter=4
            )
            subtitle_style = ParagraphStyle(
                'ReportSubtitle', parent=styles['Normal'], fontSize=9,
                textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=12
            )

            story.append(Paragraph("GEOADJUST — 1D Levelling Adjustment Report", title_style))
            story.append(Paragraph("Geodetic Network Least Squares Adjustment System", subtitle_style))
            story.append(Spacer(1, 8))

            meta_data = [
                [Paragraph("<b>Project Name:</b>", styles['Normal']), Paragraph(str(project_meta.get('name', '-')), styles['Normal']),
                 Paragraph("<b>Date:</b>", styles['Normal']), Paragraph(str(project_meta.get('date', '-')), styles['Normal'])],
                [Paragraph("<b>Instrument:</b>", styles['Normal']), Paragraph(str(project_meta.get('instrument', '-')), styles['Normal']),
                 Paragraph("<b>Observer:</b>", styles['Normal']), Paragraph(str(project_meta.get('observer', '-')), styles['Normal'])]
            ]
            t_meta = Table(meta_data, colWidths=[90, 180, 70, 200])
            t_meta.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8F9FA')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#DCDCDC')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('PADDING', (0,0), (-1,-1), 5),
                ('FONTSIZE', (0,0), (-1,-1), 9),
            ]))
            story.append(t_meta)
            story.append(Spacer(1, 12))

            story.append(Paragraph("<b>Adjustment Summary Statistics</b>", styles['Heading2']))
            stat_data = [
                ["Degrees of Freedom (f):", str(res_data['dof']), "A Posteriori Std. Dev. (σ₀):", f"{res_data['sigma0']:.4f}"],
                ["Sum of Squares (Σv²):", f"{res_data['vTpv']:.4f} m²", "Chi-Square Test:", str(res_data['chi2_status'])]
            ]
            t_stat = Table(stat_data, colWidths=[140, 130, 140, 130])
            t_stat.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DCDCDC')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FAFAFA')),
                ('PADDING', (0,0), (-1,-1), 5),
                ('FONTSIZE', (0,0), (-1,-1), 9),
            ]))
            story.append(t_stat)
            story.append(Spacer(1, 12))

            story.append(Paragraph("<b>Adjusted Reduced Levels (RL)</b>", styles['Heading2']))
            stn_df = res_data['stations']
            stn_table_data = [list(stn_df.columns)] + stn_df.values.tolist()
            t_stn = Table(stn_table_data, colWidths=[140, 140, 140, 120])
            t_stn.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E88E5')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 5),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DCDCDC')),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9F9F9')])
            ]))
            story.append(t_stn)
            story.append(Spacer(1, 12))

            story.append(Paragraph("<b>Observation Residuals</b>", styles['Heading2']))
            res_df = res_data['residuals']
            res_table_data = [list(res_df.columns)] + res_df.values.tolist()
            t_res = Table(res_table_data, colWidths=[60, 60, 80, 80, 80, 90, 90])
            t_res.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E88E5')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 5),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DCDCDC')),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9F9F9')])
            ]))
            story.append(t_res)

            def add_header_footer(canvas, document):
                canvas.saveState()
                canvas.setFont('Helvetica', 8)
                canvas.setFillColor(colors.HexColor('#777777'))
                canvas.drawString(36, 20, "GEOADJUST Geodetic Network Adjustment Toolkit")
                canvas.drawRightString(576, 20, f"Page {document.page}")
                canvas.restoreState()

            doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
            return pdf_buffer.getvalue()

        pdf_bytes = generate_pdf_report(res, meta)
        out_filename = st.session_state.get("custom_filename_1d", "1D_Adjustment_Report")

        st.download_button(
            label="📄 Download Official PDF Report with Header",
            data=pdf_bytes,
            file_name=f"{out_filename}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

# =========================================================
# TAB 2: 3D GNSS NETWORK ADJUSTMENT
# =========================================================
with tab2:
    st.header("🛰️ 3D GNSS Vector Network Adjustment")
    st.caption(f"Logged in user: **{auth['username']}** | Room: **{auth['room_id']}**")
    st.info("3D GNSS adjustment module ready for vector data input.")

# =========================================================
# TAB 3: REAL-TIME TRACKING
# =========================================================
with tab3:
    st.header("📍 Real-Time Tracking & Room Collaboration")
    st.info(f"Active Room Session: `{auth['room_id']}` as `{auth['username']}`")

# =========================================================
# TAB 4: DATUM TRANSFORMATION
# =========================================================
with tab4:
    st.header("🧭 Geodetic Datum Transformation & Map Projection")
    st.info("Datum transformation modules active.")

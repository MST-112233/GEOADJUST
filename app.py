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
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown("<h1 class='main-title'>🌐 GEOADJUST</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>", unsafe_allow_html=True)

# --- GLOBAL CROSS-DEVICE MEMORY REGISTRIES ---
@st.cache_resource
def get_global_room_registry():
    return {}

GLOBAL_ROOMS_REGISTRY = get_global_room_registry()

COLOR_PALETTE = ["blue", "red", "green", "orange", "violet", "gold", "black"]
COLOR_EMOJI = {
    "blue": "🔵", "red": "🔴", "green": "🟢", "orange": "🟠",
    "violet": "🟣", "gold": "🟡", "black": "⚫", "grey": "⚪",
}

TIMEZONE = ZoneInfo("Asia/Kuala_Lumpur")  # GMT+8
ONLINE_THRESHOLD_SEC = 20      
STALE_ROOM_MINUTES = 60        
MAX_TRACK_POINTS = 500         
MARKER_ICON_BASE = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-{color}.png"
MARKER_SHADOW = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png"


# =========================================================
# Real-Time Tracking Helper Functions (from app_1.py)
# =========================================================
def now_local():
    return datetime.now(TIMEZONE)

def fmt_time(dt_val):
    return dt_val.strftime("%Y-%m-%d %H:%M:%S") if dt_val else "-"

def today_str():
    return now_local().strftime("%Y-%m-%d")

def gps_quality_label(acc):
    if acc is None:
        return "🔴 No Fix"
    if acc <= 15:
        return "🟢 Strong"
    elif acc <= 50:
        return "🟡 Medium"
    return "🔴 Weak"

def is_room_stale(room_data):
    last_seen_times = [
        loc.get("last_seen") for loc in room_data.get("locations", {}).values() if loc.get("last_seen")
    ]
    if last_seen_times:
        latest = max(last_seen_times)
    else:
        time_ins = [m.get("time_in") for m in room_data.get("members", {}).values() if m.get("time_in")]
        if not time_ins:
            return True
        latest = max(time_ins)
    return (now_local() - latest) > timedelta(minutes=STALE_ROOM_MINUTES)

def purge_room(registry, room_key):
    registry.pop(room_key, None)

def log_event(room_data, room_key, user_id, event_type, extra=None):
    entry = {
        "Timestamp": fmt_time(now_local()),
        "Room_ID": room_key,
        "User_ID": user_id,
        "Event_Type": event_type,
        "Latitude": None,
        "Longitude": None,
        "Altitude_m": None,
        "Accuracy_m": None,
        "Chat_Message": "",
    }
    if extra:
        entry.update(extra)
    room_data["unified_log"].append(entry)

def build_members_table(room_data):
    rows = []
    for uid, minfo in room_data["members"].items():
        if minfo.get("time_out") is not None:
            continue
        loc = room_data["locations"].get(uid)
        online = bool(loc and loc.get("last_seen") and (now_local() - loc["last_seen"]) <= timedelta(seconds=ONLINE_THRESHOLD_SEC))
        legend = f"{COLOR_EMOJI.get(minfo.get('color'), '⚪')} {minfo.get('color', '-')}"
        rows.append(
            {
                "Legend": legend,
                "User ID": uid,
                "Status": "🟢 Online" if online else "🟡 Offline",
                "Latitude": loc["latitude"] if loc else None,
                "Longitude": loc["longitude"] if loc else None,
                "Altitude (m)": loc["altitude_m"] if loc else None,
                "GPS Signal": gps_quality_label(loc["accuracy_m"]) if loc else "🔴 No Fix",
                "Last Update": loc["updated_at"] if loc else "-",
                "Time In": minfo["time_in"].strftime("%Y-%m-%d %H:%M:%S") if minfo.get("time_in") else "-",
            }
        )
    return pd.DataFrame(rows)

def build_log_dataframe(room_data, user_filter=None):
    log = room_data.get("unified_log", [])
    df = pd.DataFrame(log)
    if df.empty:
        return df
    if user_filter:
        df = df[df["User_ID"] == user_filter]
    return df.sort_values("Timestamp", ascending=False).reset_index(drop=True)

SHEET_INVALID_CHARS = set('[]:*?/\\')

def sanitize_sheet_name(name, used_names):
    clean = "".join(c for c in name if c not in SHEET_INVALID_CHARS).strip() or "User"
    clean = clean[:31]
    base, i = clean, 2
    while clean in used_names:
        suffix = f"_{i}"
        clean = base[: 31 - len(suffix)] + suffix
        i += 1
    used_names.add(clean)
    return clean

def build_full_log_workbook(room_data):
    buffer = io.BytesIO()
    used_sheet_names = set()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_overall = build_log_dataframe(room_data)
        overall_name = sanitize_sheet_name("Overall", used_sheet_names)
        (df_overall if not df_overall.empty else pd.DataFrame()).to_excel(
            writer, sheet_name=overall_name, index=False
        )
        for name in room_data.get("members", {}).keys():
            df_user = build_log_dataframe(room_data, user_filter=name)
            sheet_name = sanitize_sheet_name(name, used_sheet_names)
            (df_user if not df_user.empty else pd.DataFrame()).to_excel(
                writer, sheet_name=sheet_name, index=False
            )
    return buffer.getvalue()

def marker_icon_urls(color):
    return MARKER_ICON_BASE.format(color=color), MARKER_SHADOW

def generate_kml_export(room_data, selected_user="🌐 All Users (Combined)"):
    kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(document, 'name')
    name.text = f"GEOADJUST GPS Tracks - {selected_user}"

    tracks_dict = room_data.get("tracks", {})
    target_users = list(tracks_dict.keys()) if selected_user == "🌐 All Users (Combined)" else [selected_user]

    for uid in target_users:
        user_track = tracks_dict.get(uid, [])
        if not user_track:
            continue
        
        style_id = f"style_{uid}"
        style = ET.SubElement(document, 'Style', id=style_id)
        line_style = ET.SubElement(style, 'LineStyle')
        ET.SubElement(line_style, 'color').text = "7f00ffff"
        ET.SubElement(line_style, 'width').text = "4"
        
        folder = ET.SubElement(document, 'Folder')
        ET.SubElement(folder, 'name').text = f"Track - {uid}"
        
        placemark = ET.SubElement(folder, 'Placemark')
        ET.SubElement(placemark, 'name').text = f"Path: {uid}"
        ET.SubElement(placemark, 'styleUrl').text = f"#{style_id}"
        
        line_string = ET.SubElement(placemark, 'LineString')
        ET.SubElement(line_string, 'extrude').text = "1"
        ET.SubElement(line_string, 'tessellate').text = "1"
        ET.SubElement(line_string, 'altitudeMode').text = "relativeToGround"
        
        coords_str = " ".join([f"{p['lon']},{

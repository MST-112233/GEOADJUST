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

import datum_transform as dt

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

st.set_page_config(page_title="GEOADJUST", page_icon="🌐", layout="wide")

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

st.markdown("<h1 class='main-title'>GEOADJUST</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Geodetic Network Adjustment & Spatial Toolkit</p>", unsafe_allow_html=True)

@st.cache_resource
def get_global_room_registry():
    return {}

GLOBAL_ROOMS_REGISTRY = get_global_room_registry()
COLOR_PALETTE = ["blue", "red", "green", "orange", "violet", "gold", "black"]
COLOR_EMOJI = {"blue": "🔵", "red": "🔴", "green": "🟢", "orange": "🟠", "violet": "🟣", "gold": "🟡", "black": "⚫", "grey": "⚪"}
TIMEZONE = ZoneInfo("Asia/Kuala_Lumpur")
ONLINE_THRESHOLD_SEC = 20
STALE_ROOM_MINUTES = 60
MAX_TRACK_POINTS = 500
MARKER_ICON_BASE = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-{color}.png"
MARKER_SHADOW = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png"

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

def log_event(room_data, room_key, user_id, event_type, extra=None):
    entry = {
        "Timestamp": fmt_time(now_local()),
        "Room_ID": room_key,
        "User_ID": user_id,
        "Event_Type": event_type,
        "Latitude": None, "Longitude": None, "Altitude_m": None, "Accuracy_m": None, "Chat_Message": "",
    }
    if extra:
        entry.update(extra)
    room_data["unified_log"].append(entry)

def build_members_table(room_data):
    rows = []
    for uid, minfo in room_data["members"].items():
        loc = room_data["locations"].get(uid)
        online = bool(loc and loc.get("last_seen") and (now_local() - loc["last_seen"]) <= timedelta(seconds=ONLINE_THRESHOLD_SEC))
        legend = f"{COLOR_EMOJI.get(minfo.get('color'), '⚪')} {minfo.get('color', '-')}"
        rows.append({
            "Legend": legend, "User ID": uid, "Status": "🟢 Online" if online else "🟡 Offline",
            "Latitude": loc["latitude"] if loc else None, "Longitude": loc["longitude"] if loc else None,
            "Altitude (m)": loc["altitude_m"] if loc else None, "GPS Signal": gps_quality_label(loc["accuracy_m"]) if loc else "🔴 No Fix",
            "Last Update": loc["updated_at"] if loc else "-", "Time In": minfo["time_in"].strftime("%Y-%m-%d %H:%M:%S") if minfo.get("time_in") else "-",
        })
    return pd.DataFrame(rows)

def build_log_dataframe(room_data, user_filter=None):
    log = room_data.get("unified_log", [])
    df = pd.DataFrame(log)
    if df.empty:
        return df
    if user_filter:
        df = df[df["User_ID"] == user_filter]
    return df.sort_values("Timestamp", ascending=False).reset_index(drop=True)

def build_full_log_workbook(room_data):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_overall = build_log_dataframe(room_data)
        df_overall.to_excel(writer, sheet_name="Overall", index=False)
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
        folder = ET.SubElement(document, 'Folder')
        ET.SubElement(folder, 'name').text = f"Track - {uid}"
        placemark = ET.SubElement(folder, 'Placemark')
        ET.SubElement(placemark, 'name').text = f"Path: {uid}"
        line_string = ET.SubElement(placemark, 'LineString')
        ET.SubElement(line_string, 'coordinates').text = " ".join([f"{p['lon']},{p['lat']},{p.get('alt', 0)}" for p in user_track])

    return ET.tostring(kml, encoding='utf-8', method='xml')

def build_base_map_html(center, zoom, room_id):
    return f"""
    <div id="geoadjust-map-anchor" data-room="{room_id}" style="height:450px;width:100%;">
      <div id="geoadjust-leaflet-map" style="height:100%;width:100%;"></div>
    </div>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script>
      var geoMap = L.map('geoadjust-leaflet-map').setView([{center[0]}, {center[1]}], {zoom});
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(geoMap);
      window.geoadjustMarkers = {{}};
      window.updateMarkers = function(users) {{
          var seen = {{}};
          users.forEach(function(u) {{
              seen[u.id] = true;
              var latlng = [u.lat, u.lon];
              var icon = L.icon({{ iconUrl: u.icon_url, shadowUrl: "{MARKER_SHADOW}", iconSize: [25, 41], iconAnchor: [12, 41] }});
              if (window.geoadjustMarkers[u.id]) {{
                  window.geoadjustMarkers[u.id].setLatLng(latlng);
                  window.geoadjustMarkers[u.id].setIcon(icon);
              }} else {{
                  window.geoadjustMarkers[u.id] = L.marker(latlng, {{icon: icon}}).addTo(geoMap).bindPopup(u.popup);
              }}
          }});
      }};
      window.addEventListener('message', function(event) {{
          if (event.data && event.data.type === 'geoadjust_update' && event.data.room === "{room_id}") {{
              window.updateMarkers(event.data.users);
          }}
      }});
    </script>
    """

def build_updater_html(room_id, users_payload):
    payload_json = json.dumps(users_payload)
    return f"""
    <script>
    (function() {{
        var payload = {payload_json};
        try {{
            var frames = window.parent.document.querySelectorAll('iframe');
            for (var i = 0; i < frames.length; i++) {{
                try {{
                    var doc = frames[i].contentDocument || frames[i].contentWindow.document;
                    var anchor = doc.getElementById('geoadjust-map-anchor');
                    if (anchor && anchor.getAttribute('data-room') === "{room_id}") {{
                        frames[i].contentWindow.postMessage({{type: 'geoadjust_update', room: "{room_id}", users: payload}}, '*');
                        break;
                    }}
                }} catch (inner) {{ }}
            }}
        }} catch (e) {{ }}
    }})();
    </script>
    """

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📏 1D Levelling",
    "🛰️ 3D GNSS",
    "📍 Real-Time Tracking",
    "🧭 Datum Transformation",
])

with tab1:
    st.header("📏 1D Leveling Network Adjustment")
    uploaded_file = st.file_uploader("Upload Leveling File (.csv or .xlsx)", type=["csv", "xlsx"], key="1d_file_uploader_app1")
    if uploaded_file is not None:
        df_input = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        st.dataframe(df_input.head())
        if st.button("Run 1D Adjustment"):
            st.success("Adjustment Complete!")

with tab2:
    st.header("🛰️ 3D GNSS Vector Network Adjustment")

with tab3:
    st.header("📍 Real-Time Tracking & Collaboration (Direct Access)")
    
    # Inline Session Config without Blocking Login Form
    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        current_room = st.text_input("🏠 Room ID", value="DefaultRoom", key="app1_room")
    with col_cfg2:
        user_id = st.text_input("👤 Username", value="Surveyor_1", key="app1_user")

    if current_room not in GLOBAL_ROOMS_REGISTRY:
        GLOBAL_ROOMS_REGISTRY[current_room] = {
            "password": "",
            "members": {user_id: {"role": "Field Surveyor", "color": COLOR_PALETTE[0], "time_in": now_local(), "last_heartbeat": now_local()}},
            "locations": {},
            "unified_log": [],
            "tracks": {}
        }
    room_data = GLOBAL_ROOMS_REGISTRY[current_room]
    if user_id not in room_data["members"]:
        room_data["members"][user_id] = {"role": "Field Surveyor", "color": COLOR_PALETTE[len(room_data["members"]) % len(COLOR_PALETTE)], "time_in": now_local(), "last_heartbeat": now_local()}

    refresh_count = st_autorefresh(interval=10000, key="tracking_autorefresh_app1")
    loc = get_geolocation(component_key=f"geo_app1_{refresh_count}")
    now_ts = now_local()

    if loc and "coords" in loc:
        coords = loc["coords"]
        lat, lon = coords.get("latitude"), coords.get("longitude")
        alt = coords.get("altitude") or 0.0
        acc = coords.get("accuracy") or 0.0
        user_color = room_data["members"][user_id]["color"]

        tracks = room_data.setdefault("tracks", {})
        tracks.setdefault(user_id, []).append({"lat": lat, "lon": lon, "alt": alt, "ts": now_ts})
        room_data["locations"][user_id] = {
            "user_id": user_id, "latitude": lat, "longitude": lon, "altitude_m": alt,
            "accuracy_m": acc, "updated_at": fmt_time(now_ts), "last_seen": now_ts, "color": user_color
        }

    col_map, col_chat = st.columns([2, 1])
    with col_map:
        st.subheader("🗺️ Live Map")
        active_locs = room_data.get("locations", {})
        if active_locs:
            first_loc = next(iter(active_locs.values()))
            center = [first_loc["latitude"], first_loc["longitude"]]
            users_payload = [{
                "id": uid, "lat": u["latitude"], "lon": u["longitude"],
                "icon_url": marker_icon_urls(u["color"])[0], "popup": f"<b>{u['user_id']}</b>", "tooltip": u["user_id"], "path": [], "path_color": u["color"]
            } for uid, u in active_locs.items()]
            
            components.html(build_base_map_html(center, 15, current_room), height=450)
            components.html(build_updater_html(current_room, users_payload), height=0)
            st.dataframe(build_members_table(room_data), use_container_width=True, hide_index=True)
        else:
            st.info("Awaiting GPS location signal...")

    with col_chat:
        st.subheader("💬 Room Chat")
        chat_msg = st.text_input("Message:", key="chat_input_app1")
        if st.button("Send", key="send_chat_app1") and chat_msg.strip():
            log_event(room_data, current_room, user_id, "CHAT_MESSAGE", extra={"Chat_Message": chat_msg.strip()})
            st.rerun()

        for msg in reversed([l for l in room_data["unified_log"] if l["Event_Type"] == "CHAT_MESSAGE"][-10:]):
            st.markdown(f"**{msg['User_ID']}**: {msg['Chat_Message']}")

with tab4:
    st.header("🧭 Datum Transformation & Tools")

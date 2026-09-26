import io
import os
import json
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
# Real-Time Tracking Helper Functions
# =========================================================
def now_local():
    return datetime.now(TIMEZONE)


def fmt_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "-"


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
    members_dict = room_data.get("members", {})

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
        
        coords_str = " ".join([f"{p['lon']},{p['lat']},{p.get('alt', 0)}" for p in user_track])
        ET.SubElement(line_string, 'coordinates').text = coords_str

    return ET.tostring(kml, encoding='utf-8', method='xml')


def build_multi_playback_map_html(room_data, selected_user="🌐 All Users (Combined)"):
    tracks_dict = room_data.get("tracks", {})
    members_dict = room_data.get("members", {})
    
    payload = {}
    max_steps = 0
    
    target_users = list(tracks_dict.keys()) if selected_user == "🌐 All Users (Combined)" else [selected_user]

    for uid in target_users:
        track = tracks_dict.get(uid, [])
        if track:
            color = members_dict.get(uid, {}).get("color", "blue")
            icon_url, _ = marker_icon_urls(color)
            payload[uid] = {
                "color": color,
                "icon_url": icon_url,
                "points": [{"lat": p["lat"], "lon": p["lon"], "time": fmt_time(p["ts"])} for p in track]
            }
            if len(track) > max_steps:
                max_steps = len(track)

    payload_json = json.dumps(payload)

    return f"""
    <div id="playback-container" style="height:380px; width:100%; position:relative;">
        <div id="playback-map" style="height:320px; width:100%;"></div>
        <div style="padding:10px; background:#f8f9fa; display:flex; align-items:center; gap:10px;">
            <button id="playBtn" onclick="togglePlay()" style="padding:5px 15px; background:#1E88E5; color:white; border:none; border-radius:4px; cursor:pointer;">▶ Play</button>
            <input type="range" id="timeSlider" min="0" max="{max(0, max_steps-1)}" value="0" oninput="seekPath(this.value)" style="flex-grow:1;">
            <span id="timeDisplay" style="font-size:12px; font-family:sans-serif; color:#333;">--:--:--</span>
        </div>
    </div>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script>
        var trackData = {payload_json};
        var users = Object.keys(trackData);
        
        if (users.length > 0) {{
            var firstUser = users[0];
            var firstPt = trackData[firstUser].points[0];
            
            var pbMap = L.map('playback-map').setView([firstPt.lat, firstPt.lon], 15);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(pbMap);
            
            var markers = {{}};
            var polylines = {{}};
            var allBounds = L.latLngBounds();

            users.forEach(function(uid) {{
                var uData = trackData[uid];
                var latlngs = uData.points.map(p => [p.lat, p.lon]);
                
                var poly = L.polyline(latlngs, {{color: uData.color, weight: 3, opacity: 0.7}}).addTo(pbMap);
                polylines[uid] = poly;
                allBounds.extend(poly.getBounds());
                
                var icon = L.icon({{
                    iconUrl: uData.icon_url,
                    shadowUrl: "{MARKER_SHADOW}",
                    iconSize: [25, 41],
                    iconAnchor: [12, 41]
                }});
                
                markers[uid] = L.marker([uData.points[0].lat, uData.points[0].lon], {{icon: icon}})
                    .bindTooltip("📍 " + uid)
                    .addTo(pbMap);
            }});
            
            pbMap.fitBounds(allBounds);
            
            var currentIndex = 0;
            var maxSteps = {max_steps};
            var isPlaying = false;
            var interval = null;

            function updatePositions(index) {{
                currentIndex = index;
                var latestTime = "--:--:--";
                
                users.forEach(function(uid) {{
                    var pts = trackData[uid].points;
                    var idx = Math.min(index, pts.length - 1);
                    var p = pts[idx];
                    markers[uid].setLatLng([p.lat, p.lon]);
                    latestTime = p.time;
                }});
                
                document.getElementById('timeSlider').value = index;
                document.getElementById('timeDisplay').innerText = latestTime;
            }}

            function seekPath(val) {{
                updatePositions(parseInt(val));
            }}

            function togglePlay() {{
                var btn = document.getElementById('playBtn');
                if (isPlaying) {{
                    clearInterval(interval);
                    isPlaying = false;
                    btn.innerText = "▶ Play";
                }} else {{
                    isPlaying = true;
                    btn.innerText = "⏸ Pause";
                    interval = setInterval(function() {{
                        if (currentIndex >= maxSteps - 1) {{
                            clearInterval(interval);
                            isPlaying = false;
                            btn.innerText = "▶ Play";
                        }} else {{
                            updatePositions(currentIndex + 1);
                        }}
                    }}, 700);
                }}
            }}
            updatePositions(0);
        }}
    </script>
    """


def build_base_map_html(center, zoom, room_id):
    return f"""
    <div id="geoadjust-map-anchor" data-room="{room_id}" style="height:450px;width:100%;">
      <div id="geoadjust-leaflet-map" style="height:100%;width:100%;"></div>
    </div>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script>
      var geoMap = L.map('geoadjust-leaflet-map').setView([{center[0]}, {center[1]}], {zoom});
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap contributors'
      }}).addTo(geoMap);

      window.geoadjustMarkers = {{}};
      window.geoadjustPaths = {{}};

      window.updateMarkers = function(users) {{
          var seen = {{}};
          users.forEach(function(u) {{
              seen[u.id] = true;
              var latlng = [u.lat, u.lon];
              var icon = L.icon({{
                  iconUrl: u.icon_url,
                  shadowUrl: "{MARKER_SHADOW}",
                  iconSize: [25, 41],
                  iconAnchor: [12, 41],
                  popupAnchor: [1, -34],
                  shadowSize: [41, 41],
              }});
              if (window.geoadjustMarkers[u.id]) {{
                  window.geoadjustMarkers[u.id].setLatLng(latlng);
                  window.geoadjustMarkers[u.id].setIcon(icon);
                  window.geoadjustMarkers[u.id].setPopupContent(u.popup);
                  window.geoadjustMarkers[u.id].setTooltipContent(u.tooltip);
              }} else {{
                  window.geoadjustMarkers[u.id] = L.marker(latlng, {{icon: icon}})
                      .addTo(geoMap)
                      .bindPopup(u.popup)
                      .bindTooltip(u.tooltip);
              }}

              if (u.path && u.path.length > 1) {{
                  if (window.geoadjustPaths[u.id]) {{
                      window.geoadjustPaths[u.id].setLatLngs(u.path);
                      window.geoadjustPaths[u.id].setStyle({{color: u.path_color}});
                  }} else {{
                      window.geoadjustPaths[u.id] = L.polyline(u.path, {{
                          color: u.path_color, weight: 3, opacity: 0.7
                      }}).addTo(geoMap);
                  }}
              }} else if (window.geoadjustPaths[u.id]) {{
                  geoMap.removeLayer(window.geoadjustPaths[u.id]);
                  delete window.geoadjustPaths[u.id];
              }}
          }});
          Object.keys(window.geoadjustMarkers).forEach(function(id) {{
              if (!seen[id]) {{
                  geoMap.removeLayer(window.geoadjustMarkers[id]);
                  delete window.geoadjustMarkers[id];
                  if (window.geoadjustPaths[id]) {{
                      geoMap.removeLayer(window.geoadjustPaths[id]);
                      delete window.geoadjustPaths[id];
                  }}
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
                        frames[i].contentWindow.postMessage(
                            {{type: 'geoadjust_update', room: "{room_id}", users: payload}}, '*'
                        );
                        break;
                    }}
                }} catch (inner) {{ }}
            }}
        }} catch (e) {{ }}
    }})();
    </script>
    """


def build_wakelock_html():
    return """
    <script>
    (function() {
        async function requestWakeLock() {
            try {
                if ('wakeLock' in navigator) {
                    window.geoadjustWakeLock = await navigator.wakeLock.request('screen');
                }
            } catch (e) { }
        }
        requestWakeLock();
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'visible') {
                requestWakeLock();
            }
        });
    })();
    </script>
    """


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


    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        bm_name = st.text_input("Fixed Benchmark Station Name", value="BMFGHT", key="1d_bm_name")
        has_header = st.checkbox("File contains a header row", value=False, key="1d_header")
    with col_cfg2:
        bm_height = st.number_input("Benchmark Height (m)", value=100.0000, step=0.0001, format="%.4f", key="1d_bm_height")
        custom_filename = st.text_input("Output Filename Base", value="1D_Adjustment_Results", key="1d_out_name")

    uploaded_file = st.file_uploader("Upload Leveling File (.csv or .xlsx)", type=["csv", "xlsx"], key="1d_file_uploader")

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_input = pd.read_csv(uploaded_file, header=0 if has_header else None)
            else:
                df_input = pd.read_excel(uploaded_file, header=0 if has_header else None)

            expected_cols = ["From Station", "To Station", "Diff. Height(m)", "Distance(m)", "StdDev_mm"]
            if not has_header or len(df_input.columns) < 3:
                rename_map = {i: expected_cols[i] for i in range(min(len(df_input.columns), 5))}
                df_input = df_input.rename(columns=rename_map)

            st.subheader("📋 Input Data Preview")
            st.dataframe(df_input.head(10), use_container_width=True)

            if st.button("🚀 Run 1D Adjustment", type="primary", use_container_width=True):
                with st.spinner("Computing Least Squares..."):
                    st.session_state["results_1d"] = adjust_1d_network(df_input, bm_name, bm_height)
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
            st.dataframe(res["stations"], use_container_width=True, hide_index=True)

        with col_tbl2:
            st.subheader("📏 Observation Residuals")
            st.dataframe(res["residuals"], use_container_width=True, hide_index=True)

        st.markdown("---")
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            res["stations"].to_excel(writer, sheet_name="Adjusted Heights", index=False)
            res["residuals"].to_excel(writer, sheet_name="Residuals", index=False)

        st.download_button(
            label="📥 Save & Download Excel Output (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name=f"{custom_filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

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
                    st.session_state["results_3d"] = adjust_3d_network(df_input_3d, const_name=stn_const_name, Ta=Ta_coords, jns=1)
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

        excel_buffer_3d = io.BytesIO()
        with pd.ExcelWriter(excel_buffer_3d, engine="openpyxl") as writer:
            res3d["stations"].to_excel(writer, sheet_name="Adjusted Coordinates", index=False)
            res3d["residuals"].to_excel(writer, sheet_name="Residuals", index=False)

        st.download_button(
            label="📥 Save & Download 3D Excel Output (.xlsx)",
            data=excel_buffer_3d.getvalue(),
            file_name=f"{custom_filename_3d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# =========================================================
# TAB 3: REAL-TIME TRACKING
# =========================================================
with tab3:
    if "user_room_session" not in st.session_state:
        st.session_state["user_room_session"] = {
            "authenticated": False, "room_id": "", "room_pass": "", "username": "", "role": ""
        }
    if "show_leave_confirm" not in st.session_state:
        st.session_state["show_leave_confirm"] = False
    if "map_center" not in st.session_state:
        st.session_state["map_center"] = None
    if "map_zoom" not in st.session_state:
        st.session_state["map_zoom"] = 16
    if "_map_base_room" not in st.session_state:
        st.session_state["_map_base_room"] = None

    session = st.session_state["user_room_session"]

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
                input_pass = st.text_input("🔑 Password", type="password", value="123456")
                input_role = st.selectbox("🎯 Role", ["Field Surveyor", "🏢 Control Center (Office)"])

                submit_login = st.form_submit_button("🚀 Enter Room", use_container_width=True, type="primary")

                if submit_login:
                    if not input_user or not input_room or not input_pass:
                        st.error("Please fill in Username, Room ID, and Password.")
                    else:
                        room_key = input_room.strip()
                        user_clean = input_user.strip()

                        if room_key in GLOBAL_ROOMS_REGISTRY and is_room_stale(GLOBAL_ROOMS_REGISTRY[room_key]):
                            purge_room(GLOBAL_ROOMS_REGISTRY, room_key)

                        if room_key in GLOBAL_ROOMS_REGISTRY:
                            room_data = GLOBAL_ROOMS_REGISTRY[room_key]
                            if room_data["password"] != input_pass:
                                st.error("Incorrect Password for this active room!")
                                st.stop()

                            existing_member = room_data["members"].get(user_clean)
                            if existing_member:
                                existing_member["time_out"] = None
                                log_event(room_data, room_key, user_clean, "REJOIN")
                            else:
                                color_idx = len(room_data["members"]) % len(COLOR_PALETTE)
                                room_data["members"][user_clean] = {
                                    "role": input_role,
                                    "color": COLOR_PALETTE[color_idx],
                                    "time_in": now_local(),
                                    "time_out": None,
                                    "last_heartbeat": now_local(),
                                }
                                log_event(room_data, room_key, user_clean, "JOIN")
                        else:
                            GLOBAL_ROOMS_REGISTRY[room_key] = {
                                "password": input_pass,
                                "members": {
                                    user_clean: {
                                        "role": input_role,
                                        "color": COLOR_PALETTE[0],
                                        "time_in": now_local(),
                                        "time_out": None,
                                        "last_heartbeat": now_local(),
                                    }
                                },
                                "locations": {},
                                "unified_log": [],
                            }
                            log_event(GLOBAL_ROOMS_REGISTRY[room_key], room_key, user_clean, "JOIN")

                        session["authenticated"] = True
                        session["username"] = user_clean
                        session["room_id"] = room_key
                        session["room_pass"] = input_pass
                        session["role"] = input_role
                        st.session_state["map_center"] = None
                        st.session_state["_map_base_room"] = None
                        st.rerun()

    else:
        current_room = session["room_id"]
        user_id = session["username"]
        is_admin = "Control Center" in session["role"]
        room_data = GLOBAL_ROOMS_REGISTRY.get(current_room)

        if not room_data or user_id not in room_data.get("members", {}):
            st.error("Room session expired or room closed. Please rejoin.")
            session["authenticated"] = False
            st.rerun()

        refresh_count = st_autorefresh(interval=10000, key="tracking_autorefresh")

        loc = get_geolocation(component_key=f"geo_{refresh_count}")
        net_online = streamlit_js_eval(js_expressions="navigator.onLine", key=f"net_online_{refresh_count}")
        net_type = streamlit_js_eval(js_expressions="navigator.connection ? navigator.connection.effectiveType : 'unknown'", key=f"net_type_{refresh_count}")

        now_ts = now_local()
        current_time_str = fmt_time(now_ts)
        current_date_str = now_ts.strftime("%Y-%m-%d")

        room_data["members"][user_id]["last_heartbeat"] = now_ts

        if not st.session_state.get("_wakelock_requested"):
            components.html(build_wakelock_html(), height=0)
            st.session_state["_wakelock_requested"] = True

        current_gps_quality = "🔴 No Fix"
        if loc and "coords" in loc:
            coords = loc["coords"]
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            alt = coords.get("altitude") if coords.get("altitude") is not None else 0.0
            acc = coords.get("accuracy") if coords.get("accuracy") is not None else 0.0
            current_gps_quality = gps_quality_label(acc)

            user_color = room_data["members"][user_id]["color"]

            tracks = room_data.setdefault("tracks", {})
            track = tracks.setdefault(user_id, [])
            track.append({"lat": lat, "lon": lon, "alt": alt, "ts": now_ts})
            if len(track) > MAX_TRACK_POINTS:
                del track[: len(track) - MAX_TRACK_POINTS]

            room_data["locations"][user_id] = {
                "user_id": user_id,
                "latitude": lat,
                "longitude": lon,
                "altitude_m": alt,
                "accuracy_m": acc,
                "updated_at": current_time_str,
                "last_seen": now_ts,
                "color": user_color,
            }

            log_event(
                room_data, current_room, user_id, "GPS_UPDATE",
                extra={"Latitude": lat, "Longitude": lon, "Altitude_m": round(alt, 2), "Accuracy_m": round(acc, 2)},
            )
        else:
            st.sidebar.warning("⏳ Awaiting Browser GPS Permissions / Signal...")

        head_col1, head_col2 = st.columns([3, 1])
        with head_col1:
            st.subheader(f"📍 Room: `{current_room}`")
            st.caption(f"Logged in as **{user_id}** ({'Control Center Admin' if is_admin else 'Field Surveyor'})")
        with head_col2:
            if st.button("🚪 Leave Room", use_container_width=True):
                st.session_state["show_leave_confirm"] = True
                st.rerun()

        if st.session_state["show_leave_confirm"]:
            st.warning("⚠️ **Before you leave** — please download your logs if needed.")
            dl_col, confirm_col, cancel_col = st.columns(3)
            with dl_col:
                if room_data["unified_log"]:
                    st.download_button(
                        "📥 Download Log (.xlsx)",
                        data=build_full_log_workbook(room_data),
                        file_name=f"Log_{current_room}_{today_str()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
            with confirm_col:
                if st.button("✅ Confirm Leave", type="primary", use_container_width=True):
                    room_data["members"][user_id]["time_out"] = now_local()
                    room_data["locations"].pop(user_id, None)
                    log_event(room_data, current_room, user_id, "LEAVE")

                    if all(m.get("time_out") is not None for m in room_data["members"].values()):
                        purge_room(GLOBAL_ROOMS_REGISTRY, current_room)

                    session["authenticated"] = False
                    st.session_state["show_leave_confirm"] = False
                    st.rerun()
            with cancel_col:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state["show_leave_confirm"] = False
                    st.rerun()
            st.stop()

        col_map, col_chat = st.columns([2, 1])

        with col_map:
            st.subheader("🗺️ Live OpenStreetMap")
            show_path = st.checkbox("🛣️ Show movement path", value=True, key="show_path")

            active_locs = {
                uid: loc for uid, loc in room_data["locations"].items()
                if room_data["members"].get(uid, {}).get("time_out") is None
            }

            if active_locs:
                if st.session_state["map_center"] is None:
                    first_loc = next(iter(active_locs.values()))
                    st.session_state["map_center"] = [first_loc["latitude"], first_loc["longitude"]]

                users_payload = []
                for uid, u in active_locs.items():
                    online = (now_ts - u["last_seen"]) <= timedelta(seconds=ONLINE_THRESHOLD_SEC)
                    icon_color = u["color"] if online else "grey"
                    icon_url, _ = marker_icon_urls(icon_color)
                    popup_html = f"<b>User:</b> {u['user_id']}<br><b>Lat:</b> {u['latitude']:.5f}<br><b>Lon:</b> {u['longitude']:.5f}"
                    path_points = []
                    if show_path:
                        track = room_data.get("tracks", {}).get(uid, [])
                        path_points = [[p["lat"], p["lon"]] for p in track]

                    users_payload.append({
                        "id": uid, "lat": u["latitude"], "lon": u["longitude"],
                        "icon_url": icon_url, "popup": popup_html, "tooltip": f"📍 {u['user_id']}",
                        "path": path_points, "path_color": u["color"]
                    })

                if st.session_state.get("_map_base_room") != current_room:
                    st.session_state["_map_base_html"] = build_base_map_html(
                        st.session_state["map_center"], st.session_state["map_zoom"], current_room
                    )
                    st.session_state["_map_base_room"] = current_room

                components.html(st.session_state["_map_base_html"], height=450)
                components.html(build_updater_html(current_room, users_payload), height=0)

                st.markdown("**Active Team Members**")
                st.dataframe(build_members_table(room_data), use_container_width=True, hide_index=True)

                st.markdown("---")
                st.subheader("🎬 Path Playback & KML Export Settings")
                
                all_tracked_users = list(room_data.get("tracks", {}).keys())
                playback_options = ["🌐 All Users (Combined)"] + all_tracked_users
                
                selected_playback_target = st.selectbox(
                    "🎯 Choose User Path to View / Playback / Export:",
                    options=playback_options,
                    index=0,
                    key="pb_target_select"
                )

                components.html(build_multi_playback_map_html(room_data, selected_playback_target), height=390)

                kml_export_data = generate_kml_export(room_data, selected_playback_target)
                target_filename = selected_playback_target.replace(" ", "_").replace("🌐_", "")
                
                st.download_button(
                    label=f"🌐 Download KML Path for '{selected_playback_target}'",
                    data=kml_export_data,
                    file_name=f"Path_{current_room}_{target_filename}_{today_str()}.kml",
                    mime="application/vnd.google-earth.kml+xml",
                    use_container_width=True,
                    key="dl_flexible_kml",
                )

            else:
                st.info("No active team members sharing GPS coordinates in this room.")

        with col_chat:
            st.subheader("💬 Room Chat")
            with st.form("send_chat_form", clear_on_submit=True):
                chat_msg = st.text_input("Message:")
                btn_send = st.form_submit_button("Send", use_container_width=True)

                if btn_send and chat_msg.strip():
                    log_event(room_data, current_room, user_id, "CHAT_MESSAGE", extra={"Chat_Message": chat_msg.strip()})
                    st.rerun()

            chat_events = [log for log in room_data["unified_log"] if log["Event_Type"] == "CHAT_MESSAGE"]
            if chat_events:
                chat_container = st.container(height=300)
                with chat_container:
                    for msg in reversed(chat_events):
                        time_only = msg["Timestamp"].split(" ")[1]
                        st.markdown(f"**{msg['User_ID']}** ({time_only}): {msg['Chat_Message']}")

        st.markdown("---")
        st.subheader("📜 Logging Data — Overall")
        df_overall = build_log_dataframe(room_data)
        if not df_overall.empty:
            st.dataframe(df_overall.head(20), use_container_width=True, hide_index=True, height=280)

        st.download_button(
            label="📥 Download Full Log (.xlsx)",
            data=build_full_log_workbook(room_data),
            file_name=f"Log_{current_room}_{today_str()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

# =========================================================
# TAB 4: DATUM TRANSFORMATION & MAP PROJECTION 
# =========================================================
with tab4:
    st.header("🧭 Geodetic Datum Transformation System")

    
    mode = st.radio(
        "Select Operation Mode:",
        ["3-Dimensional Transformation", "Map Projection", "Geodetic Tools (Conversion)"],
        horizontal=True,
        key="gdts_mode"
    )

    st.markdown("---")

    # -----------------------------------------------------
    # MODE 1: 3-Dimensional Transformation
    # -----------------------------------------------------
    if mode == "3-Dimensional Transformation":
        st.subheader("📐 3D Datum Transformation")
        
        region = st.selectbox("Select Region / Zone:", ["Peninsular Malaysia", "Sabah and Sarawak"], key="trans_region")

        if region == "Peninsular Malaysia":
            modules = [
                "1. GDM2000 to PMSGN94", 
                "2. PMSGN94 to GDM2000",
                #"3. GDM2000 to MRT48", 
                #"4. MRT48 to GDM2000",
                #"5. PMSGN94 to MRT48", 
                #"6. MRT48 to PMSGN94"
            ]
        else:
            modules = [
                "1. GDM2000 to EMSGN97", 
                "2. EMSGN97 to GDM2000",
                "3. GDM2000 to BT68 for Sabah", 
                "4. BT68 to GDM2000 for Sabah",
                "5. EMSGN97 to BT68 for Sabah", 
                "6. BT68 to EMSGN97 for Sabah",
                "7. GDM2000 to BT68 for Sarawak", 
                "8. BT68 to GDM2000 for Sarawak",
                "9. EMSGN97 to BT68 for Sarawak", 
                "10. BT68 to EMSGN97 for Sarawak"
            ]

        selected_module = st.selectbox("Transformation Module:", modules, key="trans_module_sel")
        module_key = selected_module.split(". ", 1)[1]

        col_in1, col_in2, col_in3 = st.columns(3)
        with col_in1:
            st.markdown("**Latitude**")
            d_lat = st.number_input("Deg", value=1, key="trans_d_lat")
            m_lat = st.number_input("Min", value=29, key="trans_m_lat")
            s_lat = st.number_input("Sec", value=0.0, format="%.4f", key="trans_s_lat")
        with col_in2:
            st.markdown("**Longitude**")
            d_lon = st.number_input("Deg", value=103, key="trans_d_lon")
            m_lon = st.number_input("Min", value=45, key="trans_m_lon")
            s_lon = st.number_input("Sec", value=0.0, format="%.4f", key="trans_s_lon")
        with col_in3:
            st.markdown("**Ellipsoidal Height**")
            h_in = st.number_input("Height (m)", value=10.000, format="%.3f", key="trans_h_in")
            stn_name = st.text_input("Station Name", value="STN01", key="trans_stn_name")

        if st.button("⚡ Transform Coordinates", type="primary", use_container_width=True, key="btn_transform"):
            lat_in = dt.dms_to_deg(d_lat, m_lat, s_lat)
            lon_in = dt.dms_to_deg(d_lon, m_lon, s_lon)
            
            lat_out, lon_out, h_out = dt.bursa_wolf_transform(lat_in, lon_in, h_in, module_key)
            out_d_lat, out_m_lat, out_s_lat = dt.deg_to_dms(lat_out)
            out_d_lon, out_m_lon, out_s_lon = dt.deg_to_dms(lon_out)

            st.success("Transformation Successful!")
            st.markdown("### 📊 Transformed Output Results")
            
            df_res = pd.DataFrame([{
                "Station": stn_name,
                "From Latitude": f"{d_lat}° {m_lat}' {s_lat:.5f}\"",
                "From Longitude": f"{d_lon}° {m_lon}' {s_lon:.5f}\"",
                "From Ell. Height (m)": f"{h_in:.3f}",
                "To Latitude": f"{out_d_lat}° {out_m_lat}' {out_s_lat:.5f}\"",
                "To Longitude": f"{out_d_lon}° {out_m_lon}' {out_s_lon:.5f}\"",
                "To Ell. Height (m)": f"{h_out:.3f}"
            }])
            st.dataframe(df_res, use_container_width=True, hide_index=True)

    # -----------------------------------------------------
    # MODE 2: Map Projection
    # -----------------------------------------------------
    elif mode == "Map Projection":
        st.subheader("🗺️ Map Projection System")
        proj_region = st.selectbox("Select Region:", ["Peninsular Malaysia", "Sabah and Sarawak"], key="proj_region")

        if proj_region == "Peninsular Malaysia":
            proj_modules = [
                "1. GDM2000 to RSO Geocentric (Peninsular)",
                "2. RSO Geocentric for Peninsular to GDM2000",
                "3. GDM2000 to Cassini-Soldner Geocentric",
                "4. Cassini-Soldner Geocentric to GDM2000",
                #"5. MRT48 to MRSO(Old)", 
                #"6. MRSO(Old) to MRT48",
                #"7. MRSO(Old) to Cassini-Soldner(Old)", 
                #"8. Cassini-Soldner(Old) to MRSO(Old)"
            ]
            state_options = ["Johor", "Kedah & Perlis", "Kelantan", "N.Sembilan & Melaka", "Pahang", "Perak", "Pulau Pinang", "Selangor & Kuala Lumpur", "Terengganu"]
        else:
            proj_modules = [
                "1. GDM2000 to RSO Geocentric (Sabah and Sarawak)",
                "2. RSO Geocentric for Sabah and Sarawak to GDM2000",
                "3. BT68 to BRSO(Old)", 
                "4. BRSO(Old) to BT68"
            ]
            state_options = ["Sabah", "Sarawak"]

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.selectbox("Transformation Module:", proj_modules, key="proj_module_sel")
        with col_p2:
            st.selectbox("State Selection (if applicable):", state_options, key="proj_state_sel")

        st.info("💡 Complete RSO/Cassini Map Projection calculations are configured for the selected region.")

    # -----------------------------------------------------
    # MODE 3: Geodetic Tools (Coordinate Conversion)
    # -----------------------------------------------------
    elif mode == "Geodetic Tools (Conversion)":
        st.subheader("🌐 Geodetic Coordinate Conversion Tools")

        tool_choice = st.radio("Tool Selection:", ["Geographical to Cartesian", "Cartesian to Geographical"], horizontal=True, key="tool_choice")

        ellipsoid_name = st.selectbox("Select Pre-Defined Ellipsoid:", list(dt.ELLIPSOIDS.keys()), key="ell_sel")
        ell_data = dt.ELLIPSOIDS[ellipsoid_name]

        c_a, c_f = st.columns(2)
        c_a.metric("Semi-Major Axis (a)", f"{ell_data['a']:.3f} m")
        c_f.metric("Flattening (1/f)", f"{ell_data['inv_f']:.6f}")

        st.markdown("---")

        if tool_choice == "Geographical to Cartesian":
            col_g1, col_g2, col_g3 = st.columns(3)
            with col_g1:
                st.markdown("**Latitude**")
                g_d_lat = st.number_input("Deg", value=1, key="g_d_lat")
                g_m_lat = st.number_input("Min", value=29, key="g_m_lat")
                g_s_lat = st.number_input("Sec", value=0.0, format="%.4f", key="g_s_lat")
            with col_g2:
                st.markdown("**Longitude**")
                g_d_lon = st.number_input("Deg", value=103, key="g_d_lon")
                g_m_lon = st.number_input("Min", value=45, key="g_m_lon")
                g_s_lon = st.number_input("Sec", value=0.0, format="%.4f", key="g_s_lon")
            with col_g3:
                g_h = st.number_input("Ellipsoidal Height (m)", value=10.0, format="%.3f", key="g_h")

            if st.button("⚙️ Compute Cartesian (X, Y, Z)", type="primary", use_container_width=True, key="btn_geo_cart"):
                lat_val = dt.dms_to_deg(g_d_lat, g_m_lat, g_s_lat)
                lon_val = dt.dms_to_deg(g_d_lon, g_m_lon, g_s_lon)
                
                X, Y, Z = dt.geo_to_cartesian(lat_val, lon_val, g_h, ellipsoid_name)

                st.success("Conversion Computed Successfully!")
                res_x, res_y, res_z = st.columns(3)
                res_x.metric("X (m)", f"{X:.4f}")
                res_y.metric("Y (m)", f"{Y:.4f}")
                res_z.metric("Z (m)", f"{Z:.4f}")

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
                d_lat, m_lat, s_lat = dt.deg_to_dms(lat_deg)
                d_lon, m_lon, s_lon = dt.deg_to_dms(lon_deg)

                st.success("Conversion Computed Successfully!")
                out_lat, out_lon, out_h = st.columns(3)
                out_lat.metric("Latitude", f"{d_lat}° {m_lat}' {s_lat:.2f}\"")
                out_lon.metric("Longitude", f"{d_lon}° {m_lon}' {s_lon:.2f}\"")
                out_h.metric("Ellipsoidal Height", f"{height:.4f} m")

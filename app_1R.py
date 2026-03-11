"""
Smart Pet Feeder — Streamlit Dashboard
=======================================
pip install streamlit requests
streamlit run app.py

Enter the ESP32's IP address (shown in Serial Monitor) in the
connection box at the top of the page to connect.
"""

import streamlit as st
import requests
import time
from datetime import datetime

# ── Config ────────────────────────────────────────────────
HOPPER_MAX     = 1000
LOW_FOOD_ALERT = 100
SERVING_GRAMS  = 70
POLL_INTERVAL  = 3   # seconds

# ─────────────────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────────────────
defaults = {
    "esp32_ip":         "",
    "connected":        False,
    "hopper_grams":     HOPPER_MAX,
    "motion":           False,
    "feeding":          False,
    "device_time":      "--:--",
    "low_food":         False,
    "schedule":         [],
    "last_motion_time": None,
    "schedule_inputs":  ["08:00"],
    "freq":             1,
    "freq_confirmed":   False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────
#  HTTP HELPERS
# ─────────────────────────────────────────────────────────
def fetch_status(ip):
    try:
        r = requests.get(f"http://{ip}/status", timeout=2)
        if r.status_code == 200:
            return r.json(), True
    except Exception:
        pass
    return None, False

def send_command(ip, payload):
    try:
        r = requests.post(f"http://{ip}/command", json=payload, timeout=3)
        return r.status_code == 200
    except Exception:
        return False

# ─────────────────────────────────────────────────────────
#  PAGE CONFIG & STYLES
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="🐾 Smart Pet Feeder", page_icon="🐾", layout="wide")

st.markdown("""
<style>
.connect-box {
    background:#1a1f2e; border:1.5px solid #3b82f6;
    border-radius:12px; padding:20px 24px; margin-bottom:20px;
}
.alert-low-food {
    background:#2d0a0a; border:1.5px solid #dc2626; border-radius:10px;
    padding:14px 20px; color:#fca5a5; font-size:15px; font-weight:600; margin-bottom:12px;
}
.alert-motion {
    background:#052e16; border:1.5px solid #16a34a; border-radius:10px;
    padding:14px 20px; color:#86efac; font-size:15px; margin-bottom:12px;
}
.food-bar-wrap {
    background:#1f2937; border-radius:8px; height:24px;
    overflow:hidden; margin:4px 0 20px 0;
}
.food-bar-fill {
    height:100%; border-radius:8px; display:flex; align-items:center;
    padding-left:12px; color:white; font-size:12px; font-weight:700;
}
.sched-pill {
    display:inline-block; background:#1e3a5f; color:#93c5fd;
    border-radius:20px; padding:4px 14px; margin:3px 4px;
    font-size:14px; font-weight:600;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────────────────
st.title("🐾 Smart Pet Feeder Dashboard")
st.divider()

# ─────────────────────────────────────────────────────────
#  CONNECTION BOX
# ─────────────────────────────────────────────────────────
st.markdown('<div class="connect-box">', unsafe_allow_html=True)
cc1, cc2, cc3 = st.columns([3, 1, 1])
with cc1:
    ip_input = st.text_input(
        "📡 ESP32 IP Address",
        value=st.session_state.esp32_ip,
        placeholder="e.g. 172.20.10.5",
        help="Find this in Arduino Serial Monitor after flashing. Look for 'ESP32 IP: x.x.x.x'",
        label_visibility="visible",
    )
with cc2:
    st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
    connect_btn = st.button("🔌 Connect", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
with cc3:
    st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
    disconnect_btn = st.button("⏏️ Disconnect", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Handle connect/disconnect
if connect_btn and ip_input.strip():
    st.session_state.esp32_ip = ip_input.strip()
    data, ok = fetch_status(ip_input.strip())
    if ok:
        st.session_state.connected = True
        st.success(f"✅ Connected to ESP32 at {ip_input.strip()}")
    else:
        st.session_state.connected = False
        st.error(f"❌ Could not reach ESP32 at {ip_input.strip()}. Check the IP and make sure the ESP32 is running.")

if disconnect_btn:
    st.session_state.connected = False
    st.session_state.esp32_ip  = ""
    st.info("Disconnected.")

# Show connection status
dot   = "🟢" if st.session_state.connected else "🔴"
label = f"Connected to {st.session_state.esp32_ip}" if st.session_state.connected else "Not connected"
st.markdown(f"**{dot} {label}**")

st.divider()

# ─────────────────────────────────────────────────────────
#  POLL ESP32 IF CONNECTED
# ─────────────────────────────────────────────────────────
if st.session_state.connected and st.session_state.esp32_ip:
    data, ok = fetch_status(st.session_state.esp32_ip)
    if ok:
        prev_motion = st.session_state.motion
        st.session_state.hopper_grams = data.get("hopper_grams", st.session_state.hopper_grams)
        st.session_state.motion       = data.get("motion",       False)
        st.session_state.feeding      = data.get("feeding",      False)
        st.session_state.device_time  = data.get("time",         "--:--")
        st.session_state.low_food     = data.get("low_food",     False)

        if data.get("motion") and not prev_motion:
            st.session_state.last_motion_time = datetime.now().strftime("%H:%M:%S")

        sched = data.get("schedule", [])
        if sched:
            st.session_state.schedule = sched
    else:
        st.session_state.connected = False
        st.warning("⚠️ Lost connection to ESP32.")

# ─────────────────────────────────────────────────────────
#  ALERTS
# ─────────────────────────────────────────────────────────
if st.session_state.hopper_grams <= LOW_FOOD_ALERT:
    st.markdown(
        f'<div class="alert-low-food">⚠️  Food level critically low — '
        f'only <strong>{st.session_state.hopper_grams} g</strong> remaining. '
        f'Please refill the hopper.</div>',
        unsafe_allow_html=True,
    )

if st.session_state.last_motion_time:
    st.markdown(
        f'<div class="alert-motion">🐶 Your pet was detected and fed at '
        f'<strong>{st.session_state.last_motion_time}</strong>.</div>',
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────
#  METRICS
# ─────────────────────────────────────────────────────────
hopper_pct    = min(100, max(0, int(st.session_state.hopper_grams / HOPPER_MAX * 100)))
servings_left = int(st.session_state.hopper_grams / SERVING_GRAMS)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("🌾 Hopper Level",  f'{st.session_state.hopper_grams} g', delta=f'{hopper_pct}% full')
with m2:
    st.metric("🥣 Servings Left", str(servings_left), delta=f'{SERVING_GRAMS} g each')
with m3:
    st.metric("🔧 Feeder Status", "⚙️ Dispensing…" if st.session_state.feeding else "😴 Idle")
with m4:
    st.metric("⏰ Device Time", st.session_state.device_time)

bar_color = ("#ef4444" if st.session_state.hopper_grams <= LOW_FOOD_ALERT
             else "#f59e0b" if st.session_state.hopper_grams < 300
             else "#22c55e")
st.markdown(f"""
<div class="food-bar-wrap">
  <div class="food-bar-fill" style="width:{hopper_pct}%;background:{bar_color};">
    {hopper_pct}%
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────────────────
#  LAYOUT — Schedule | Controls
# ─────────────────────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

# ══════════════════════════════════════
#  LEFT — Schedule
# ══════════════════════════════════════
with left:
    st.subheader("📅 Feeding Schedule")

    freq = st.number_input(
        "How many times per day should your pet be fed? (max 10)",
        min_value=1, max_value=10,
        value=st.session_state.freq,
        step=1, key="freq_widget",
    )

    save_allowed = True
    if freq >= 5:
        total_g     = freq * SERVING_GRAMS
        days_supply = HOPPER_MAX // total_g
        st.warning(
            f"⚠️  **{freq} feedings per day** means **{total_g} g** of food daily. "
            f"Your hopper holds {HOPPER_MAX} g — that's only **{days_supply} day(s)** "
            f"of supply. Please confirm this is intentional."
        )
        confirmed = st.checkbox(
            "Yes, I confirm this feeding frequency.",
            value=st.session_state.freq_confirmed,
            key="freq_confirm_widget",
        )
        st.session_state.freq_confirmed = confirmed
        save_allowed = confirmed
    else:
        st.session_state.freq_confirmed = True

    inputs = st.session_state.schedule_inputs
    while len(inputs) < freq: inputs.append("08:00")
    while len(inputs) > freq: inputs.pop()

    st.markdown("**Enter each feeding time (24-hour HH:MM):**")
    new_inputs = []
    COLS = 3
    for row_start in range(0, freq, COLS):
        row_idxs = list(range(row_start, min(row_start + COLS, freq)))
        cols = st.columns(len(row_idxs))
        for ci, idx in enumerate(row_idxs):
            with cols[ci]:
                val = st.text_input(
                    f"Feeding {idx + 1}",
                    value=inputs[idx],
                    placeholder="HH:MM",
                    key=f"slot_{idx}",
                )
                new_inputs.append(val.strip())

    st.session_state.schedule_inputs = new_inputs
    st.session_state.freq = freq

    if st.button("💾  Save & Send Schedule to Feeder",
                 type="primary", disabled=not save_allowed,
                 use_container_width=True):
        if not st.session_state.connected:
            st.error("Not connected to ESP32.")
        else:
            valid, errors = [], []
            for i, t in enumerate(new_inputs):
                try:
                    datetime.strptime(t, "%H:%M")
                    valid.append(t)
                except ValueError:
                    errors.append(f"Feeding {i + 1}: '{t}' is not a valid HH:MM time.")

            if errors:
                for e in errors: st.error(e)
            else:
                valid_sorted = sorted(set(valid))
                ok = send_command(st.session_state.esp32_ip,
                                  {"cmd": "schedule", "schedule": valid_sorted})
                if ok:
                    st.session_state.schedule = valid_sorted
                    st.success(f"✅ Schedule saved: {', '.join(valid_sorted)}")
                else:
                    st.error("Failed to send schedule to ESP32.")

    st.markdown("---")
    st.markdown("**Active schedule on device:**")
    if st.session_state.schedule:
        pills = "".join(
            f'<span class="sched-pill">🕐 {t}</span>'
            for t in sorted(st.session_state.schedule)
        )
        st.markdown(pills, unsafe_allow_html=True)
    else:
        st.caption("No schedule loaded on device yet.")

# ══════════════════════════════════════
#  RIGHT — Controls
# ══════════════════════════════════════
with right:
    st.subheader("🎛️ Controls")

    st.markdown("**Manual override**")
    if st.button("🍽️  Dispense One Serving Now", use_container_width=True):
        if not st.session_state.connected:
            st.error("Not connected to ESP32.")
        else:
            ok = send_command(st.session_state.esp32_ip, {"cmd": "feed"})
            st.success("Feed command sent!") if ok else st.error("Failed to send command.")

    st.markdown("---")
    st.markdown("**Hopper management**")
    if st.button("🔄  Mark Hopper as Refilled (1 kg)", use_container_width=True):
        if not st.session_state.connected:
            st.error("Not connected to ESP32.")
        else:
            ok = send_command(st.session_state.esp32_ip, {"cmd": "refill"})
            if ok:
                st.session_state.hopper_grams = HOPPER_MAX
                st.session_state.low_food     = False
                st.success("Hopper reset to 1000 g.")
            else:
                st.error("Failed to send command.")

    st.markdown("---")
    st.markdown("**Live sensor readings**")

    ir_color  = "#22c55e" if st.session_state.motion  else "#6b7280"
    fed_color = "#3b82f6" if st.session_state.feeding else "#6b7280"
    ir_label  = "🟢 Motion detected" if st.session_state.motion  else "⚫ No motion"
    fed_label = "🔵 Dispensing"       if st.session_state.feeding else "⚫ Idle"

    st.markdown(
        f"<div style='background:#1f2937;border-radius:8px;padding:14px 18px;margin:6px 0'>"
        f"<b style='color:#9ca3af'>IR Sensor</b><br>"
        f"<span style='color:{ir_color};font-size:15px'>{ir_label}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='background:#1f2937;border-radius:8px;padding:14px 18px;margin:6px 0'>"
        f"<b style='color:#9ca3af'>Mechanism</b><br>"
        f"<span style='color:{fed_color};font-size:15px'>{fed_label}</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.caption(
        f"Serving: **{SERVING_GRAMS} g**  ·  "
        f"Hopper max: **{HOPPER_MAX} g**  ·  "
        f"Alert below: **{LOW_FOOD_ALERT} g**"
    )

# ─────────────────────────────────────────────────────────
#  AUTO-REFRESH
# ─────────────────────────────────────────────────────────
st.markdown("---")
st.caption("⟳  Dashboard refreshes every 3 seconds.")
time.sleep(POLL_INTERVAL)
st.rerun()

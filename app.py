"""
Smart Pet Feeder — Streamlit + Flask Dashboard
===============================================
Install : pip install streamlit flask requests
Run     : streamlit run app.py

Flask runs silently in the background on port 8765.
You only ever interact with the Streamlit UI at localhost:8501.
Set SERVER_IP in pet_feeder.ino to your PC's local IP (run ipconfig).
"""

import streamlit as st
import threading
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify

# ── Config ────────────────────────────────────────────────
FLASK_PORT     = 8765
HOPPER_MAX     = 1000
LOW_FOOD_ALERT = 100
SERVING_GRAMS  = 70

# ─────────────────────────────────────────────────────────
#  SHARED STATE  (Flask thread <-> Streamlit thread)
# ─────────────────────────────────────────────────────────
_lock  = threading.Lock()
_state = {
    "hopper_grams":     HOPPER_MAX,
    "motion":           False,
    "feeding":          False,
    "time":             "--:--",
    "low_food":         False,
    "schedule":         [],
    "last_motion":      "",
    "last_motion_time": None,
    "esp32_seen":       False,
    "pending_cmd":      None,
}

def get_state():
    with _lock:
        return dict(_state)

def update_state(**kwargs):
    with _lock:
        _state.update(kwargs)

def set_cmd(cmd):
    with _lock:
        _state["pending_cmd"] = cmd

def pop_cmd():
    with _lock:
        cmd = _state["pending_cmd"]
        _state["pending_cmd"] = None
        return cmd

# ─────────────────────────────────────────────────────────
#  FLASK SERVER
# ─────────────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/update", methods=["POST"])
def handle_update():
    """ESP32 pushes its status here every 5 s."""
    try:
        data = request.get_json(force=True)
        prev = get_state()

        # Capture the exact time a new motion event arrives
        if data.get("motion") and not prev["motion"]:
            update_state(last_motion_time=datetime.now().strftime("%H:%M:%S"))

        update_state(
            hopper_grams = data.get("hopper_grams", prev["hopper_grams"]),
            motion       = data.get("motion",       False),
            feeding      = data.get("feeding",      False),
            time         = data.get("time",         prev["time"]),
            low_food     = data.get("low_food",     False),
            last_motion  = data.get("last_motion",  prev["last_motion"]),
            esp32_seen   = True,
        )
        sched = data.get("schedule", [])
        if sched:
            update_state(schedule=sched)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@flask_app.route("/command", methods=["GET"])
def handle_command():
    """ESP32 polls here every 2 s for pending commands."""
    cmd = pop_cmd()
    return jsonify(cmd if cmd else {"cmd": "none"})


def run_flask():
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    flask_app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False)


# Start Flask once per Streamlit process
if "flask_started" not in st.session_state:
    threading.Thread(target=run_flask, daemon=True).start()
    st.session_state.flask_started = True
    time.sleep(0.5)

# ─────────────────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────────────────
if "schedule_inputs" not in st.session_state:
    st.session_state.schedule_inputs = ["08:00"]
if "freq" not in st.session_state:
    st.session_state.freq = 1
if "freq_confirmed" not in st.session_state:
    st.session_state.freq_confirmed = False

# ─────────────────────────────────────────────────────────
#  PAGE CONFIG & STYLES
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="🐾 Smart Pet Feeder", page_icon="🐾", layout="wide")

st.markdown("""
<style>
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
dev = get_state()

hcol, scol = st.columns([6, 1])
with hcol:
    st.title("🐾 Smart Pet Feeder Dashboard")
with scol:
    dot   = "🟢" if dev["esp32_seen"] else "🔴"
    label = "ESP32 Online" if dev["esp32_seen"] else "Waiting for ESP32"
    st.markdown(
        f"<div style='text-align:right;padding-top:30px;font-size:14px'>{dot} {label}</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ─────────────────────────────────────────────────────────
#  ALERTS  (persistent — visible every page load)
# ─────────────────────────────────────────────────────────
if dev["hopper_grams"] <= LOW_FOOD_ALERT:
    st.markdown(
        f'<div class="alert-low-food">⚠️  Food level critically low — '
        f'only <strong>{dev["hopper_grams"]} g</strong> remaining. '
        f'Please refill the hopper.</div>',
        unsafe_allow_html=True,
    )

if dev["last_motion_time"]:
    st.markdown(
        f'<div class="alert-motion">🐶 Your pet was detected and fed at '
        f'<strong>{dev["last_motion_time"]}</strong>.</div>',
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────
#  METRICS
# ─────────────────────────────────────────────────────────
hopper_pct    = min(100, max(0, int(dev["hopper_grams"] / HOPPER_MAX * 100)))
servings_left = int(dev["hopper_grams"] / SERVING_GRAMS)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("🌾 Hopper Level",  f'{dev["hopper_grams"]} g', delta=f'{hopper_pct}% full')
with m2:
    st.metric("🥣 Servings Left", str(servings_left),         delta=f'{SERVING_GRAMS} g each')
with m3:
    st.metric("🔧 Feeder Status", "⚙️ Dispensing…" if dev["feeding"] else "😴 Idle")
with m4:
    st.metric("⏰ Device Time",   dev["time"])

bar_color = ("#ef4444" if dev["hopper_grams"] <= LOW_FOOD_ALERT
             else "#f59e0b" if dev["hopper_grams"] < 300
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

    # Sync slot list to chosen frequency
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
            update_state(schedule=valid_sorted)
            set_cmd({"cmd": "schedule", "schedule": valid_sorted})
            st.success(f"✅ Schedule saved: {', '.join(valid_sorted)}")

    st.markdown("---")
    st.markdown("**Active schedule on device:**")
    sched = get_state()["schedule"]
    if sched:
        pills = "".join(f'<span class="sched-pill">🕐 {t}</span>' for t in sorted(sched))
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
        set_cmd({"cmd": "feed"})
        st.info("Feed command queued — ESP32 picks it up within 2 seconds.")

    st.markdown("---")
    st.markdown("**Hopper management**")
    if st.button("🔄  Mark Hopper as Refilled (1 kg)", use_container_width=True):
        update_state(hopper_grams=HOPPER_MAX, low_food=False)
        set_cmd({"cmd": "refill"})
        st.success("Refill command sent. Scale will re-tare on ESP32.")

    st.markdown("---")
    st.markdown("**Live sensor readings**")

    ir_color  = "#22c55e" if dev["motion"]  else "#6b7280"
    fed_color = "#3b82f6" if dev["feeding"] else "#6b7280"
    ir_label  = "🟢 Motion detected" if dev["motion"]  else "⚫ No motion"
    fed_label = "🔵 Dispensing"       if dev["feeding"] else "⚫ Idle"

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
        f"Alert below: **{LOW_FOOD_ALERT} g**  ·  "
        f"Server port: **{FLASK_PORT}**"
    )

# ─────────────────────────────────────────────────────────
#  AUTO-REFRESH every 3 seconds
# ─────────────────────────────────────────────────────────
st.markdown("---")
st.caption("⟳  Dashboard refreshes every 3 seconds.")
time.sleep(3)
st.rerun()

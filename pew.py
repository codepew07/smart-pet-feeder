import streamlit as st
from supabase import create_client
import datetime
import pandas as pd

# ---------------------------
# Streamlit config
# ---------------------------
st.set_page_config(
    page_title="Smart Pet Feeder",
    page_icon="🐾",
    layout="wide"
)

# ---------------------------
# Supabase setup
# ---------------------------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

if "user" not in st.session_state:
    st.session_state.user = None

if "feeder_connected" not in st.session_state:
    st.session_state.feeder_connected = False

# ---------------------------
# AUTH
# ---------------------------
st.title("🐾 Smart Pet Feeder")

if st.session_state.user is None:
    st.subheader("Login / Sign up")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Sign up"):
            supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            st.info("Check your email to confirm your account.")

    with col2:
        if st.button("Log in"):
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state.user = res.user
            st.rerun()

else:
    st.success(f"Logged in as {st.session_state.user.email}")
    if st.button("Log out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

# Stop everything if not logged in
if st.session_state.user is None:
    st.stop()

USER_ID = st.session_state.user.id

# ---------------------------
# DATABASE HELPERS
# ---------------------------
def log_feed(portion, feed_type):
    supabase.table("feed_history").insert({
        "user_id": USER_ID,
        "portion": portion,
        "type": feed_type
    }).execute()

def fetch_history():
    return supabase.table("feed_history") \
        .select("*") \
        .eq("user_id", USER_ID) \
        .order("timestamp", desc=True) \
        .execute().data

def fetch_schedules():
    return supabase.table("feed_schedules") \
        .select("*") \
        .eq("user_id", USER_ID) \
        .eq("enabled", True) \
        .execute().data

def run_scheduled_feeds():
    now = datetime.datetime.now()
    today = now.strftime("%A")
    current_time = now.time().replace(second=0, microsecond=0)

    schedules = fetch_schedules()

    for s in schedules:
        if today in s["days"]:
            scheduled_time = datetime.time.fromisoformat(s["feed_time"])
            if scheduled_time == current_time:
                log_feed(s["portion"], "Scheduled")

# Execute scheduled feeds on every interaction
run_scheduled_feeds()

# ---------------------------
# SIDEBAR
# ---------------------------
with st.sidebar:
    st.header("⚙️ Feeder Settings")
    feeder_ip = st.text_input("Feeder IP", "192.168.1.100")

    if st.button("Connect to Feeder"):
        st.session_state.feeder_connected = True
        st.success("Feeder connected")

    st.markdown(
        "🟢 Connected" if st.session_state.feeder_connected else "🔴 Disconnected"
    )

# ---------------------------
# MAIN TABS
# ---------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Dashboard", "🍽️ Manual Feed", "⏰ Schedule", "📈 History"]
)

# ---------------------------
# DASHBOARD
# ---------------------------
with tab1:
    history = fetch_history()
    today = datetime.date.today()

    today_count = len([
        h for h in history
        if datetime.datetime.fromisoformat(h["timestamp"]).date() == today
    ])

    st.metric("Feedings Today", today_count)
    st.metric("Total Feedings", len(history))

# ---------------------------
# MANUAL FEED
# ---------------------------
with tab2:
    portion = st.slider("Portion (cups)", 0.25, 5.0, 1.0, 0.25)

    if st.button("Dispense Now"):
        if not st.session_state.feeder_connected:
            st.error("Connect feeder first")
        else:
            log_feed(portion, "Manual")
            st.success("Food dispensed")
            st.rerun()

# ---------------------------
# SCHEDULE FEED
# ---------------------------
with tab3:
    st.subheader("Add Schedule")

    feed_time = st.time_input("Time", datetime.time(8, 0))
    portion = st.number_input("Portion", 0.25, 5.0, 1.0, 0.25)
    days = st.multiselect(
        "Days",
        ["Monday", "Tuesday", "Wednesday", "Thursday",
         "Friday", "Saturday", "Sunday"],
        default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    )

    if st.button("Add Schedule"):
        supabase.table("feed_schedules").insert({
            "user_id": USER_ID,
            "feed_time": feed_time.isoformat(),
            "portion": portion,
            "days": days,
            "enabled": True
        }).execute()
        st.success("Schedule added")

# ---------------------------
# HISTORY
# ---------------------------
with tab4:
    history = fetch_history()

    if history:
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        st.dataframe(
            df[["timestamp", "portion", "type"]]
            .rename(columns={
                "timestamp": "Time",
                "portion": "Portion (cups)",
                "type": "Type"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No feeding history yet")

# ---------------------------
# FOOTER
# ---------------------------
st.divider()
st.caption(
    f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

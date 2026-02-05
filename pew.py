import streamlit as st
from supabase import create_client
import sqlite3
from twilio.rest import Client
import datetime
import requests
import json
from typing import List, Dict
import pandas as pd

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

if "user" not in st.session_state:
    st.session_state.user = None

# Ensure page config is the first Streamlit command in the script
st.set_page_config(
    page_title="Smart Pet Feeder Control",
    page_icon="🐾",
    layout="wide"
)

st.title("Smart Pet Feeder")

if st.session_state.user is None:
    st.subheader("Login / Sign up")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Sign up"):
            try:
                supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                st.info("Check your email to confirm your account.")
            except Exception as e:
                st.error(str(e))

    with col2:
        if st.button("Log in"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.user = res.user
                st.success("Logged in!")
                st.rerun()
            except Exception as e:
                st.error("Login failed. Did you confirm your email?")
else:
    st.success(f"Logged in as {st.session_state.user.email}")

    if st.button("Log out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

# ---------------------------
# Twilio setup (replace with your actual credentials)
# ---------------------------
ACCOUNT_SID = "your_account_sid"
AUTH_TOKEN = "your_auth_token"
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"

client = Client(ACCOUNT_SID, AUTH_TOKEN)

def send_whatsapp_alert(message, to_number):
    client.messages.create(
        body=message,
        from_=TWILIO_WHATSAPP_NUMBER,
        to=f"whatsapp:{to_number}"
    )

# ---------------------------
# Database setup
# ---------------------------
conn = sqlite3.connect("pet_feeder.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL UNIQUE,
    pet_name TEXT NOT NULL
)
""")
conn.commit()

# ---------------------------
# Streamlit UI
# ---------------------------

# Custom CSS for better styling
st.markdown("""
<style>
.big-font {
    font-size:30px !important;
    font-weight: bold;
}
.status-connected {
    color: #28a745;
    font-weight: bold;
}
.status-disconnected {
    color: #dc3545;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'feeding_history' not in st.session_state:
    st.session_state.feeding_history = []

if 'scheduled_feedings' not in st.session_state:
    st.session_state.scheduled_feedings = []

if 'feeder_connected' not in st.session_state:
    st.session_state.feeder_connected = False

# API Configuration (replace with your pet feeder's actual API)
FEEDER_API_URL = "http://your-pet-feeder-ip:port/api"
API_KEY = "your-api-key-here"

# Helper Functions
def connect_to_feeder(ip_address: str, api_key: str = None) -> bool:
    """Connect to the pet feeder"""
    try:
        st.session_state.feeder_connected = True
        return True
    except Exception as e:
        st.error(f"Connection failed: {str(e)}")
        return False

def dispense_food(portion_size: float) -> bool:
    """Dispense food immediately"""
    try:
        st.session_state.feeding_history.append({
            "timestamp": datetime.datetime.now(),
            "portion": portion_size,
            "type": "Manual"
        })
        return True
    except Exception as e:
        st.error(f"Dispensing failed: {str(e)}")
        return False

def schedule_feeding(time: datetime.time, portion: float, days: List[str]) -> bool:
    """Schedule a feeding time"""
    try:
        st.session_state.scheduled_feedings.append({
            "time": time,
            "portion": portion,
            "days": days,
            "enabled": True
        })
        return True
    except Exception as e:
        st.error(f"Scheduling failed: {str(e)}")
        return False

def get_food_level() -> float:
    """Get current food level in the hopper (percentage)"""
    try:
        return 75.0
    except Exception as e:
        st.error(f"Failed to get food level: {str(e)}")
        return 0.0

# Main App Layout
st.title("🐾 Smart Pet Feeder Control Panel")

# Sidebar - Connection Settings
with st.sidebar:
    st.header("⚙️ Settings")

    feeder_ip = st.text_input("Feeder IP Address", value="192.168.1.100")
    feeder_api_key = st.text_input("API Key (if required)", type="password")

    if st.button("Connect to Feeder"):
        if connect_to_feeder(feeder_ip, feeder_api_key):
            st.success("Connected successfully!")
        else:
            st.error("Connection failed!")

    st.divider()

    st.subheader("Connection Status")
    if st.session_state.feeder_connected:
        st.markdown('<p class="status-connected">● Connected</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-disconnected">● Disconnected</p>', unsafe_allow_html=True)

    st.divider()

    st.subheader("Pet Information")
    pet_name = st.text_input("Pet Name", value="Fluffy")
    pet_type = st.selectbox("Pet Type", ["Cat", "Dog", "Other"])

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Dashboard", "🍽️ Manual Feed", "⏰ Schedule", "📈 History"]
)

with tab1:
    st.header("Dashboard")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Food Level", f"{get_food_level():.0f}%")
        st.progress(get_food_level() / 100)

    with col2:
        today_feedings = len([
            f for f in st.session_state.feeding_history
            if f["timestamp"].date() == datetime.date.today()
        ])
        st.metric("Feedings Today", today_feedings)

    with col3:
        active_schedules = len([
            s for s in st.session_state.scheduled_feedings
            if s.get("enabled", True)
        ])
        st.metric("Active Schedules", active_schedules)

with tab2:
    st.header("Manual Feeding")

    col1, col2 = st.columns([2, 1])

    with col1:
        portion_size = st.slider(
            "Portion Size (cups)",
            min_value=0.25,
            max_value=5.0,
            value=1.0,
            step=0.25
        )
        st.info(f"Selected portion: {portion_size} cup(s)")

    with col2:
        if st.button("🍽️ Dispense Now", use_container_width=True):
            if not st.session_state.feeder_connected:
                st.error("Please connect to feeder first!")
            else:
                if dispense_food(portion_size):
                    st.success(f"Dispensed {portion_size} cup(s) successfully!")
                    st.balloons()
                    st.rerun()

with tab3:
    st.header("Feeding Schedule")

    with st.expander("➕ Add New Schedule", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            schedule_time = st.time_input(
                "Feeding Time",
                value=datetime.time(8, 0)
            )
            schedule_portion = st.number_input(
                "Portion Size (cups)",
                min_value=0.25,
                max_value=5.0,
                value=1.0,
                step=0.25
            )

        with col2:
            schedule_days = st.multiselect(
                "Select Days",
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            )

        if st.button("Add Schedule"):
            if schedule_days:
                if schedule_feeding(schedule_time, schedule_portion, schedule_days):
                    st.success("Schedule added successfully!")
                    st.rerun()
            else:
                st.warning("Please select at least one day!")

with tab4:
    st.header("Feeding History")

    if st.session_state.feeding_history:
        df = pd.DataFrame(st.session_state.feeding_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp', ascending=False)

        st.dataframe(df, use_container_width=True)
    else:
        st.info("No feeding history yet. Dispense some food to see it here!")

st.divider()
st.caption(
    f"Smart Pet Feeder Control Panel | Last updated: {datetime.datetime.now()}"
)

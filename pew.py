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
FEEDER_API_URL = "http://your-pet-feeder-ip:port/api"  # Replace with actual URL
API_KEY = "your-api-key-here"  # Replace with actual API key

# Helper Functions
def connect_to_feeder(ip_address: str, api_key: str = None) -> bool:
    """Connect to the pet feeder"""
    try:
        # Replace this with actual connection logic for your device
        # Example: response = requests.get(f"http://{ip_address}/status", headers={"Authorization": f"Bearer {api_key}"})
        # For demo purposes, we'll simulate a connection
        st.session_state.feeder_connected = True
        return True
    except Exception as e:
        st.error(f"Connection failed: {str(e)}")
        return False

def dispense_food(portion_size: float) -> bool:
    """Dispense food immediately"""
    try:
        # Replace with actual API call
        # Example: requests.post(f"{FEEDER_API_URL}/dispense", json={"portion": portion_size})
        
        # Log the feeding
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
        # Replace with actual API call
        # Example: requests.post(f"{FEEDER_API_URL}/schedule", json={"time": str(time), "portion": portion, "days": days})
        
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
        # Replace with actual API call
        # Example: response = requests.get(f"{FEEDER_API_URL}/food-level")
        # return response.json()["level"]
        
        # Demo value
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
    
    # Connection Status
    st.subheader("Connection Status")
    if st.session_state.feeder_connected:
        st.markdown('<p class="status-connected">● Connected</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-disconnected">● Disconnected</p>', unsafe_allow_html=True)
    
    st.divider()
    
    # Pet Information
    st.subheader("Pet Information")
    pet_name = st.text_input("Pet Name", value="Fluffy")
    pet_type = st.selectbox("Pet Type", ["Cat", "Dog", "Other"])

# Main Content Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🍽️ Manual Feed", "⏰ Schedule", "📈 History"])

# Dashboard Tab
with tab1:
    st.header("Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Food Level", f"{get_food_level():.0f}%", delta=None)
        st.progress(get_food_level() / 100)
    
    with col2:
        today_feedings = len([f for f in st.session_state.feeding_history 
                             if f["timestamp"].date() == datetime.date.today()])
        st.metric("Feedings Today", today_feedings)
    
    with col3:
        active_schedules = len([s for s in st.session_state.scheduled_feedings if s.get("enabled", True)])
        st.metric("Active Schedules", active_schedules)
    
    st.divider()
    
    # Quick Actions
    st.subheader("Quick Actions")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🍖 Feed Small Portion (1 cup)", use_container_width=True):
            if dispense_food(1.0):
                st.success("Small portion dispensed!")
                st.rerun()
    
    with col2:
        if st.button("🍗 Feed Large Portion (2 cups)", use_container_width=True):
            if dispense_food(2.0):
                st.success("Large portion dispensed!")
                st.rerun()

# Manual Feed Tab
with tab2:
    st.header("Manual Feeding")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        portion_size = st.slider("Portion Size (cups)", 
                                min_value=0.25, 
                                max_value=5.0, 
                                value=1.0, 
                                step=0.25)
        
        st.info(f"Selected portion: {portion_size} cup(s)")
    
    with col2:
        st.write("")
        st.write("")
        # Removed invalid `type="primary"` argument from st.button (Streamlit doesn't accept it)
        if st.button("🍽️ Dispense Now", use_container_width=True):
            if not st.session_state.feeder_connected:
                st.error("Please connect to feeder first!")
            else:
                if dispense_food(portion_size):
                    st.success(f"Dispensed {portion_size} cup(s) successfully!")
                    st.balloons()
                    st.rerun()

# Schedule Tab
with tab3:
    st.header("Feeding Schedule")
    
    # Add new schedule
    with st.expander("➕ Add New Schedule", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            schedule_time = st.time_input("Feeding Time", value=datetime.time(8, 0))
            schedule_portion = st.number_input("Portion Size (cups)", 
                                              min_value=0.25, 
                                              max_value=5.0, 
                                              value=1.0, 
                                              step=0.25)
        
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
    
    st.divider()
    
    # Display existing schedules
    st.subheader("Current Schedules")
    
    if st.session_state.scheduled_feedings:
        for idx, schedule in enumerate(st.session_state.scheduled_feedings):
            col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
            
            with col1:
                st.write(f"**{schedule['time'].strftime('%I:%M %p')}**")
            
            with col2:
                st.write(f"{schedule['portion']} cup(s)")
            
            with col3:
                days_str = ", ".join(schedule['days'])
                st.write(f"{days_str}")
            
            with col4:
                if st.button("🗑️", key=f"delete_{idx}"):
                    st.session_state.scheduled_feedings.pop(idx)
                    st.rerun()
            
            st.divider()
    else:
        st.info("No schedules configured. Add your first schedule above!")

# History Tab
with tab4:
    st.header("Feeding History")
    
    if st.session_state.feeding_history:
        # Convert to DataFrame for better display
        df = pd.DataFrame(st.session_state.feeding_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp', ascending=False)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_feedings = len(df)
            st.metric("Total Feedings", total_feedings)
        
        with col2:
            total_food = df['portion'].sum()
            st.metric("Total Food Dispensed", f"{total_food:.2f} cups")
        
        with col3:
            avg_portion = df['portion'].mean()
            st.metric("Average Portion", f"{avg_portion:.2f} cups")
        
        st.divider()
        
        # Filter options
        col1, col2 = st.columns(2)
        
        with col1:
            # Do not pass value=None; st.date_input will return today's date by default
            filter_date = st.date_input("Filter by Date")
        
        with col2:
            filter_type = st.selectbox("Filter by Type", ["All", "Manual", "Scheduled"])
        
        # Apply filters
        filtered_df = df.copy()
        if filter_date:
            filtered_df = filtered_df[filtered_df['timestamp'].dt.date == filter_date]
        if filter_type != "All":
            filtered_df = filtered_df[filtered_df['type'] == filter_type]
        
        # Display table
        st.dataframe(
            filtered_df[['timestamp', 'portion', 'type']].rename(columns={
                'timestamp': 'Time',
                'portion': 'Portion (cups)',
                'type': 'Type'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Clear history button
        if st.button("🗑️ Clear History"):
            st.session_state.feeding_history = []
            st.rerun()
    else:
        st.info("No feeding history yet. Dispense some food to see it here!")

# Footer
st.divider()
st.caption(f"Smart Pet Feeder Control Panel | Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


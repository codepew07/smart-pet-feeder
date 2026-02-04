import streamlit as st
from supabase import create_client
import datetime
import requests
import json
from typing import List, Dict
import pandas as pd
import time
from threading import Thread

# Supabase setup
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

# Initialize session state for user
if "user" not in st.session_state:
    st.session_state.user = None

# Page config must be first
st.set_page_config(
    page_title="Smart Pet Feeder Control",
    page_icon="🐾",
    layout="wide"
)

# ==========================================
# DATABASE HELPER FUNCTIONS
# ==========================================

def init_user_data(user_id: str):
    """Initialize user data in Supabase if it doesn't exist"""
    try:
        # Check if user profile exists
        response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if not response.data:
            # Create default user profile
            supabase.table('user_profiles').insert({
                'user_id': user_id,
                'pet_name': 'Fluffy',
                'pet_type': 'Cat',
                'phone_number': None
            }).execute()
    except Exception as e:
        st.error(f"Error initializing user data: {e}")

def get_user_profile(user_id: str) -> Dict:
    """Get user profile from Supabase"""
    try:
        response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Error fetching profile: {e}")
        return None

def update_user_profile(user_id: str, pet_name: str, pet_type: str, phone_number: str = None):
    """Update user profile"""
    try:
        supabase.table('user_profiles').update({
            'pet_name': pet_name,
            'pet_type': pet_type,
            'phone_number': phone_number
        }).eq('user_id', user_id).execute()
    except Exception as e:
        st.error(f"Error updating profile: {e}")

def get_user_schedules(user_id: str) -> List[Dict]:
    """Get all schedules for a user"""
    try:
        response = supabase.table('feeding_schedules').select('*').eq('user_id', user_id).eq('enabled', True).execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Error fetching schedules: {e}")
        return []

def add_schedule(user_id: str, schedule_time: str, portion: float, days: List[str]):
    """Add a new feeding schedule"""
    try:
        supabase.table('feeding_schedules').insert({
            'user_id': user_id,
            'schedule_time': schedule_time,
            'portion': portion,
            'days': days,
            'enabled': True
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error adding schedule: {e}")
        return False

def delete_schedule(schedule_id: int):
    """Delete a feeding schedule"""
    try:
        supabase.table('feeding_schedules').delete().eq('id', schedule_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting schedule: {e}")
        return False

def get_feeding_history(user_id: str, limit: int = 100) -> List[Dict]:
    """Get feeding history for a user"""
    try:
        response = supabase.table('feeding_history').select('*').eq('user_id', user_id).order('fed_at', desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Error fetching history: {e}")
        return []

def log_feeding(user_id: str, portion: float, feed_type: str, schedule_id: int = None):
    """Log a feeding event"""
    try:
        supabase.table('feeding_history').insert({
            'user_id': user_id,
            'portion': portion,
            'type': feed_type,
            'schedule_id': schedule_id,
            'fed_at': datetime.datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error logging feeding: {e}")
        return False

def clear_feeding_history(user_id: str):
    """Clear all feeding history for a user"""
    try:
        supabase.table('feeding_history').delete().eq('user_id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error clearing history: {e}")
        return False

# ==========================================
# SCHEDULE CHECKER (Background Task)
# ==========================================

def check_and_execute_schedules(user_id: str):
    """Check if any schedules should be executed now"""
    schedules = get_user_schedules(user_id)
    now = datetime.datetime.now()
    current_day = now.strftime('%A')
    current_time = now.strftime('%H:%M')
    
    for schedule in schedules:
        schedule_time = schedule['schedule_time']  # Format: "HH:MM"
        schedule_days = schedule['days']
        
        # Check if current day is in schedule and time matches (within 1 minute window)
        if current_day in schedule_days:
            # Parse schedule time
            schedule_hour, schedule_min = map(int, schedule_time.split(':'))
            schedule_dt = now.replace(hour=schedule_hour, minute=schedule_min, second=0, microsecond=0)
            
            # Check if we're within 1 minute of scheduled time
            time_diff = abs((now - schedule_dt).total_seconds())
            
            if time_diff < 60:  # Within 1 minute
                # Check if we already dispensed in the last 2 minutes (prevent duplicates)
                recent_history = get_feeding_history(user_id, limit=10)
                already_dispensed = False
                
                for entry in recent_history:
                    entry_time = datetime.datetime.fromisoformat(entry['fed_at'])
                    if (now - entry_time).total_seconds() < 120 and entry.get('schedule_id') == schedule['id']:
                        already_dispensed = True
                        break
                
                if not already_dispensed:
                    # Execute the feeding!
                    if dispense_food_api(schedule['portion']):
                        log_feeding(user_id, schedule['portion'], 'Scheduled', schedule['id'])
                        return True
    return False

# ==========================================
# FEEDER API FUNCTIONS
# ==========================================

def connect_to_feeder(ip_address: str, api_key: str = None) -> bool:
    """Connect to the ESP32 pet feeder"""
    try:
        response = requests.get(
            f"http://{ip_address}/api/status",
            timeout=5
        )
        
        if response.status_code == 200:
            return True
        return False
    except:
        return False

def dispense_food_api(portion_size: float, ip_address: str = None) -> bool:
    """Dispense food via ESP32 API"""
    try:
        if ip_address is None:
            ip_address = st.session_state.get('feeder_ip', '192.168.1.100')
        
        response = requests.post(
            f"http://{ip_address}/api/dispense",
            json={"portion": portion_size},
            timeout=10
        )
        
        return response.status_code == 200
    except Exception as e:
        print(f"Dispense error: {e}")
        return False

def get_food_level(ip_address: str = None) -> float:
    """Get current food level from ESP32"""
    try:
        if ip_address is None:
            ip_address = st.session_state.get('feeder_ip', '192.168.1.100')
        
        response = requests.get(
            f"http://{ip_address}/api/food-level",
            timeout=3
        )
        
        if response.status_code == 200:
            return response.json().get('level', 0.0)
        return 0.0
    except:
        return 0.0

# ==========================================
# STREAMLIT UI
# ==========================================

st.title("🐾 Smart Pet Feeder")

# Custom CSS
st.markdown("""
    <style>
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

# ==========================================
# LOGIN / SIGNUP
# ==========================================

if st.session_state.user is None:
    st.subheader("Login / Sign up")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Sign up"):
            try:
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                st.info("✅ Check your email to confirm your account!")
            except Exception as e:
                st.error(f"Sign up failed: {str(e)}")

    with col2:
        if st.button("Log in"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.user = res.user
                
                # Initialize user data if first time
                init_user_data(res.user.id)
                
                st.success("Logged in!")
                st.rerun()
            except Exception as e:
                st.error("Login failed. Check your credentials or confirm your email.")

else:
    # ==========================================
    # LOGGED IN VIEW
    # ==========================================
    
    user_id = st.session_state.user.id
    user_email = st.session_state.user.email
    
    st.success(f"Logged in as {user_email}")

    if st.button("Log out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    # Get user profile
    profile = get_user_profile(user_id)
    
    # ==========================================
    # SIDEBAR - Settings
    # ==========================================
    
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # ESP32 Connection
        feeder_ip = st.text_input("Feeder IP Address", value=st.session_state.get('feeder_ip', '192.168.1.100'))
        
        if st.button("Connect to Feeder"):
            if connect_to_feeder(feeder_ip):
                st.session_state.feeder_ip = feeder_ip
                st.session_state.feeder_connected = True
                st.success("✅ Connected!")
            else:
                st.session_state.feeder_connected = False
                st.error("❌ Connection failed!")
        
        st.divider()
        
        # Connection Status
        st.subheader("Connection Status")
        if st.session_state.get('feeder_connected', False):
            st.markdown('<p class="status-connected">● Connected</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="status-disconnected">● Disconnected</p>', unsafe_allow_html=True)
        
        st.divider()
        
        # Pet Information
        st.subheader("Pet Information")
        
        if profile:
            pet_name = st.text_input("Pet Name", value=profile.get('pet_name', 'Fluffy'))
            pet_type = st.selectbox("Pet Type", ["Cat", "Dog", "Other"], 
                                   index=["Cat", "Dog", "Other"].index(profile.get('pet_type', 'Cat')))
            phone_number = st.text_input("Phone Number (for alerts)", value=profile.get('phone_number', ''))
            
            if st.button("Save Profile"):
                update_user_profile(user_id, pet_name, pet_type, phone_number)
                st.success("Profile updated!")
                st.rerun()
    
    # ==========================================
    # MAIN TABS
    # ==========================================
    
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "⏰ Schedule", "📈 History"])
    
    # ==========================================
    # DASHBOARD TAB
    # ==========================================
    
    with tab1:
        st.header("Dashboard")
        
        # Check and execute schedules
        check_and_execute_schedules(user_id)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            food_level = get_food_level(st.session_state.get('feeder_ip'))
            st.metric("Food Level", f"{food_level:.0f}%")
            st.progress(food_level / 100)
        
        with col2:
            today_history = get_feeding_history(user_id, limit=100)
            today_feedings = len([h for h in today_history 
                                 if datetime.datetime.fromisoformat(h['fed_at']).date() == datetime.date.today()])
            st.metric("Feedings Today", today_feedings)
        
        with col3:
            schedules = get_user_schedules(user_id)
            st.metric("Active Schedules", len(schedules))
        
        st.divider()
        
        # Next Scheduled Feeding
        st.subheader("Next Scheduled Feeding")
        
        if schedules:
            now = datetime.datetime.now()
            current_day = now.strftime('%A')
            
            upcoming = []
            for schedule in schedules:
                if current_day in schedule['days']:
                    time_parts = schedule['schedule_time'].split(':')
                    schedule_time = datetime.datetime.now().replace(
                        hour=int(time_parts[0]),
                        minute=int(time_parts[1]),
                        second=0,
                        microsecond=0
                    )
                    if schedule_time > now:
                        upcoming.append((schedule_time, schedule))
            
            if upcoming:
                upcoming.sort(key=lambda x: x[0])
                next_feeding = upcoming[0]
                time_until = next_feeding[0] - now
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                
                st.info(f"⏰ Next feeding: {next_feeding[1]['schedule_time']} ({hours}h {minutes}m from now) - {next_feeding[1]['portion']} cup(s)")
            else:
                st.info("No more feedings scheduled for today")
        else:
            st.warning("No schedules configured. Go to Schedule tab to add one.")
    
    # ==========================================
    # SCHEDULE TAB
    # ==========================================
    
    with tab2:
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
                    time_str = schedule_time.strftime('%H:%M')
                    if add_schedule(user_id, time_str, schedule_portion, schedule_days):
                        st.success("✅ Schedule added successfully!")
                        st.rerun()
                else:
                    st.warning("Please select at least one day!")
        
        st.divider()
        
        # Display existing schedules
        st.subheader("Current Schedules")
        
        schedules = get_user_schedules(user_id)
        
        if schedules:
            for schedule in schedules:
                col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
                
                with col1:
                    # Parse time string
                    time_parts = schedule['schedule_time'].split(':')
                    display_time = datetime.time(int(time_parts[0]), int(time_parts[1]))
                    st.write(f"**{display_time.strftime('%I:%M %p')}**")
                
                with col2:
                    st.write(f"{schedule['portion']} cup(s)")
                
                with col3:
                    days_str = ", ".join(schedule['days'])
                    st.write(f"{days_str}")
                
                with col4:
                    if st.button("🗑️", key=f"delete_{schedule['id']}"):
                        if delete_schedule(schedule['id']):
                            st.success("Deleted!")
                            st.rerun()
                
                st.divider()
        else:
            st.info("No schedules configured. Add your first schedule above!")
    
    # ==========================================
    # HISTORY TAB
    # ==========================================
    
    with tab3:
        st.header("Feeding History")
        
        history = get_feeding_history(user_id, limit=100)
        
        if history:
            # Convert to DataFrame
            df = pd.DataFrame(history)
            df['fed_at'] = pd.to_datetime(df['fed_at'])
            df = df.sort_values('fed_at', ascending=False)
            
            # Summary statistics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Feedings", len(df))
            
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
                filter_date = st.date_input("Filter by Date")
            
            with col2:
                filter_type = st.selectbox("Filter by Type", ["All", "Scheduled"])
            
            # Apply filters
            filtered_df = df.copy()
            if filter_date:
                filtered_df = filtered_df[filtered_df['fed_at'].dt.date == filter_date]
            if filter_type != "All":
                filtered_df = filtered_df[filtered_df['type'] == filter_type]
            
            # Display table
            st.dataframe(
                filtered_df[['fed_at', 'portion', 'type']].rename(columns={
                    'fed_at': 'Time',
                    'portion': 'Portion (cups)',
                    'type': 'Type'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Clear history button
            if st.button("🗑️ Clear All History"):
                if clear_feeding_history(user_id):
                    st.success("History cleared!")
                    st.rerun()
        else:
            st.info("No feeding history yet. Schedules will appear here when executed.")
    
    # Footer
    st.divider()
    st.caption(f"Smart Pet Feeder Control Panel | Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

import streamlit as st
from supabase import create_client
from datetime import datetime, time

# ---------------- CONFIG ----------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

# ---------------- SESSION INIT ----------------
if "user" not in st.session_state:
    st.session_state.user = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None

# ---------------- AUTH ----------------
def login(email, password):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    res = client.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    st.session_state.user = res.user
    st.session_state.access_token = res.session.access_token


def get_authed_client():
    return create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        headers={
            "Authorization": f"Bearer {st.session_state.access_token}"
        }
    )

# ---------------- UI ----------------
st.title("🐾 Smart Pet Feeder")

if not st.session_state.user:
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login(email, password)
        st.rerun()
    st.stop()

supabase = get_authed_client()
USER_ID = st.session_state.user.id

# ---------------- PET DATA ----------------
st.subheader("🐶 Pet Profile")

pet_res = supabase.table("pets").select("*").eq("user_id", USER_ID).execute()
pet = pet_res.data[0] if pet_res.data else None

pet_name = st.text_input("Pet Name", pet["name"] if pet else "")
pet_type = st.selectbox("Pet Type", ["Dog", "Cat", "Other"], index=0 if not pet else ["Dog", "Cat", "Other"].index(pet["type"]))

if st.button("Save Pet"):
    supabase.table("pets").upsert({
        "user_id": USER_ID,
        "name": pet_name,
        "type": pet_type
    }).execute()
    st.success("Pet saved")

# ---------------- FEED SCHEDULING ----------------
st.subheader("⏰ Schedule Feeding")

feed_time = st.time_input("Feeding Time")
portion = st.number_input("Portion (grams)", min_value=1, max_value=500)

if st.button("Schedule Feed"):
    supabase.table("feed_schedules").insert({
        "user_id": USER_ID,
        "feed_time": feed_time.strftime("%H:%M:%S"),
        "portion": portion
    }).execute()
    st.success("Feed scheduled")

# ---------------- RUN SCHEDULES ----------------
st.subheader("▶ Feeding Execution")

now = datetime.now().time().replace(second=0, microsecond=0)
schedules = supabase.table("feed_schedules").select("*").eq("user_id", USER_ID).execute().data

for sched in schedules:
    sched_time = datetime.strptime(sched["feed_time"], "%H:%M:%S").time()
    if sched_time == now:
        supabase.table("feed_history").insert({
            "user_id": USER_ID,
            "pet_name": pet_name,
            "pet_type": pet_type,
            "fed_at": datetime.now().isoformat(),
            "portion": sched["portion"]
        }).execute()

# ---------------- HISTORY ----------------
st.subheader("📜 Feed History")
history = supabase.table("feed_history").select("*").eq("user_id", USER_ID).order("fed_at", desc=True).execute().data

if history:
    st.table(history)
else:
    st.info("No feeding history yet")

# ---------------- LOGOUT ----------------
if st.button("Logout"):
    st.session_state.clear()
    st.rerun()

# main.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import json, time, uuid
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

# Refresh the page every 2 seconds so the big screen shows near-real-time updates
st_autorefresh(interval=2000, key="autorefresh")

st.set_page_config(page_title="Vote to Reveal", layout="wide")

# ---- Initialize Firebase (server-side using service account) ----
def init_firebase():
    # avoid double-init
    if firebase_admin._apps:
        return

    if "FIREBASE_SERVICE_ACCOUNT" in st.secrets:
        # when deployed to Streamlit Cloud, store service account JSON in secrets
        sa = json.loads(st.secrets["FIREBASE_SERVICE_ACCOUNT"])
        cred = credentials.Certificate(sa)
        databaseURL = st.secrets["FIREBASE_DATABASE_URL"]
    else:
        # local fallback: put serviceAccountKey.json in project root for local testing
        cred = credentials.Certificate("serviceAccountKey.json")
        databaseURL = "https://your-project-id-default-rtdb.firebaseio.com/"

    firebase_admin.initialize_app(cred, {"databaseURL": databaseURL})

init_firebase()

# DB references
votes_ref = db.reference("/votes/total")
users_ref = db.reference("/votes/users")
logs_ref = db.reference("/votes/logs")
force_reveal_ref = db.reference("/admin/force_reveal")

# Helper functions
def get_votes():
    v = votes_ref.get()
    return int(v) if v else 0

def has_voted(client_id):
    return users_ref.child(client_id).get() is not None

def record_vote(client_id):
    # atomic increment using transaction
    def txn(current):
        return (current or 0) + 1
    new_total = votes_ref.transaction(txn)
    users_ref.child(client_id).set({"time": int(time.time())})
    logs_ref.push({"user": client_id, "time": int(time.time())})
    return new_total

def is_force_revealed():
    return force_reveal_ref.get() or False

def set_force_reveal(value):
    force_reveal_ref.set(value)

# Admin credentials (store in secrets for security)
ADMIN_USERNAME = st.secrets.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "password123")

# Initialize session state - DEFAULT TO USER
if 'user_role' not in st.session_state:
    st.session_state.user_role = "user"

if 'client_id' not in st.session_state:
    st.session_state.client_id = str(uuid.uuid4())

# Admin login in sidebar (only show if user)
if st.session_state.user_role == "user":
    with st.sidebar:
        st.header("🔐 Admin Login")
        with st.form("admin_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login as Admin")
            
            if login_btn:
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    st.session_state.user_role = "admin"
                    st.success("Admin login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials!")

# Logout button for admin
if st.session_state.user_role == "admin":
    if st.sidebar.button("Logout to User"):
        st.session_state.user_role = "user"
        st.rerun()

st.title("🎉 Vote to Reveal the Theme")
st.sidebar.write(f"**Role:** {st.session_state.user_role.title()}")

# UI: config from secrets or sidebar (admin can change threshold)
default_thresh = int(st.secrets.get("THRESHOLD", 50))
if st.session_state.user_role == "admin":
    threshold = int(st.sidebar.number_input("Reveal threshold", min_value=1, value=default_thresh))
else:
    threshold = default_thresh
    st.sidebar.write(f"**Threshold:** {threshold}")

theme = st.secrets.get("THEME", "Your Theme Here")

# Current votes and progress
votes = get_votes()
force_revealed = is_force_revealed()

st.metric("Total Votes", votes)
st.progress(min(votes/threshold, 1.0))

# Admin controls (ONLY FOR ADMIN)
if st.session_state.user_role == "admin":
    st.sidebar.header("🔧 Admin Controls")
    
    if force_revealed:
        if st.sidebar.button("🔒 Hide Theme"):
            set_force_reveal(False)
            st.sidebar.success("Theme hidden!")
            st.rerun()
    else:
        if st.sidebar.button("🔓 Force Reveal Theme"):
            set_force_reveal(True)
            st.sidebar.success("Theme force revealed!")
            st.rerun()
    
    if st.sidebar.button("🗑️ Reset All Votes"):
        votes_ref.set(0)
        users_ref.delete()
        logs_ref.delete()
        set_force_reveal(False)
        st.sidebar.success("All data reset!")
        st.rerun()

# Voting section (ONLY FOR USERS)
if st.session_state.user_role == "user":
    left, right = st.columns([2,1])
    with left:
        if has_voted(st.session_state.client_id):
            st.info("✅ You already voted — thank you!")
        else:
            if st.button("Vote", type="primary"):
                try:
                    record_vote(st.session_state.client_id)
                    st.success("Thanks — your vote has been counted! 🎉")
                    st.rerun()
                except Exception as e:
                    st.error("Could not record vote. Try again or contact the organizer.")
    with right:
        st.write(f"Threshold: **{threshold}**")
        if votes < threshold and not force_revealed:
            st.write(f"**{threshold - votes}** votes left to reveal")
        else:
            st.write("Threshold reached!" if votes >= threshold else "Admin force revealed!")

# Reveal logic (SHOWS FOR EVERYONE)
if votes >= threshold or force_revealed:
    st.balloons()
    reveal_html = f"""
    <div style="text-align:center; padding:20px;">
      <h1 style="font-size:48px; margin:0;">🎊 THE THEME 🎊</h1>
      <h2 style="font-size:36px; margin-top:10px;">{theme}</h2>
    </div>
    """
    components.html(reveal_html, height=220)
    
    if force_revealed and st.session_state.user_role == "admin":
        st.info("⚡ Theme force revealed by admin")

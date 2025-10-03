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
st.title("🎉 Vote to Reveal the Theme")

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

# Give each visitor a persistent client id for this browser tab/session
if 'client_id' not in st.session_state:
    st.session_state.client_id = str(uuid.uuid4())

# UI: config from secrets or sidebar
default_thresh = int(st.secrets.get("THRESHOLD", 50))
threshold = int(st.sidebar.number_input("Reveal threshold", min_value=1, value=default_thresh))
theme = st.secrets.get("THEME", "Your Theme Here")

# Current votes and progress
votes = get_votes()
st.metric("Total Votes", votes)
st.progress(min(votes/threshold, 1.0))

# Voting column
left, right = st.columns([2,1])
with left:
    if has_voted(st.session_state.client_id):
        st.info("✅ You already voted — thank you!")
    else:
        if st.button("Vote"):
            try:
                record_vote(st.session_state.client_id)
                st.success("Thanks — your vote has been counted! 🎉")
            except Exception as e:
                st.error("Could not record vote. Try again or contact the organizer.")
with right:
    st.write(f"Threshold: **{threshold}**")
    if votes < threshold:
        st.write(f"**{threshold - votes}** votes left to reveal")
    else:
        st.write("Threshold reached!")

# Reveal logic
if votes >= threshold:
    st.balloons()
    reveal_html = f"""
    <div style="text-align:center; padding:20px;">
      <h1 style="font-size:48px; margin:0;">🎊 THE THEME 🎊</h1>
      <h2 style="font-size:36px; margin-top:10px;">{theme}</h2>
    </div>
    """
    components.html(reveal_html, height=220)

# Admin: optional force-reveal (use only on host machine)
if st.sidebar.checkbox("Admin: Force reveal (local override)"):
    st.balloons()
    components.html(f"<h2 style='text-align:center'>{theme}</h2>", height=120)

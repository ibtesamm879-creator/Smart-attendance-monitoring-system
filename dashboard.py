"""Admin dashboard.   Run:  streamlit run dashboard.py"""
import hmac
import io
import shutil
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

import config
import database as db

st.set_page_config(page_title="SmartAttend", page_icon="🎓", layout="wide")
db.init_db()


# ---------------------------------------------------------------- helpers
def check_login() -> bool:
    if st.session_state.get("auth"):
        return True
    st.title("🎓 SmartAttend")
    pwd = st.text_input("Admin password", type="password")
    if st.button("Login"):
        if hmac.compare_digest(pwd.encode(), config.ADMIN_PASSWORD.encode()):
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Ghalat password.")
    return False


def to_excel(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def download_buttons(df: pd.DataFrame, stem: str) -> None:
    c1, c2, _ = st.columns([1, 1, 4])
    c1.download_button("⬇ CSV", df.to_csv(index=False).encode(), f"{stem}.csv", "text/csv")
    c2.download_button(
        "⬇ Excel", to_excel({"Report": df}), f"{stem}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ------------------------------------------------------------- live page
@st.fragment(run_every=5)
def live_panel() -> None:
    today = date.today().isoformat()
    report = pd.DataFrame(db.daily_report(today))
    total = len(report)
    present = int((report["status"] != "Absent").sum()) if total else 0
    late = int((report["status"] == "Late").sum()) if total else 0
    inside = db.currently_inside(today)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registered", total)
    c2.metric("Present today", present)
    c3.metric("Late", late)
    c4.metric("Abhi andar", len(inside))

    st.subheader("Live log")
    events = pd.DataFrame(db.recent_events(30))
    if events.empty:
        st.info("Abhi tak koi entry/exit record nahi hui.")
    else:
        st.dataframe(events[["timestamp", "name", "code", "role", "event_type", "confidence"]],
                     hide_index=True)
        with st.expander("Latest snapshots"):
            snaps = [r for r in events.to_dict("records") if r.get("snapshot")][:6]
            cols = st.columns(max(len(snaps), 1))
            for col, r in zip(cols, snaps):
                path = config.BASE_DIR / r["snapshot"]
                if path.exists():
                    col.image(str(path), caption=f'{r["name"]} {r["event_type"]}')


def page_live() -> None:
    st.header("📊 Live Overview")
    live_panel()


# ----------------------------------------------------------- daily report
def page_daily() -> None:
    st.header("📅 Daily Report")
    day = st.date_input("Date", date.today()).isoformat()
    df = pd.DataFrame(db.daily_report(day))
    if df.empty:
        st.info("Koi registered person nahi.")
        return
    c1, c2 = st.columns(2)
    role = c1.selectbox("Role", ["All", "student", "teacher"])
    status = c2.selectbox("Status", ["All", "Present", "Late", "Absent"])
    if role != "All":
        df = df[df["role"] == role]
    if status != "All":
        df = df[df["status"] == status]
    st.dataframe(df, hide_index=True)
    download_buttons(df, f"attendance_{day}")


# -------------------------------------------------------------- analytics
def page_analytics() -> None:
    st.header("📈 Analytics")
    rng = st.date_input("Date range", (date.today() - timedelta(days=30), date.today()))
    if len(rng) != 2:
        st.info("Start aur end dono date chuno.")
        return
    start, end = (d.isoformat() for d in rng)

    days = db.class_days(start, end)
    summary = pd.DataFrame(db.attendance_summary(start, end))
    if days == 0 or summary.empty:
        st.info("Is range mein koi attendance data nahi.")
        return

    summary["attendance_%"] = (summary["days_present"] / days * 100).round(1)
    low = summary[summary["attendance_%"] < config.LOW_ATTENDANCE_THRESHOLD]

    c1, c2, c3 = st.columns(3)
    c1.metric("Class days", days)
    c2.metric("Average attendance", f'{summary["attendance_%"].mean():.1f}%')
    c3.metric(f"Below {config.LOW_ATTENDANCE_THRESHOLD}%", len(low))

    st.subheader("Attendance % per person")
    st.bar_chart(summary.set_index("name")["attendance_%"])

    st.subheader("Daily trend")
    trend = pd.DataFrame(db.daily_counts(start, end)).set_index("date")[["present", "late"]]
    st.line_chart(trend)

    if not low.empty:
        st.subheader("⚠ Low attendance")
        st.dataframe(low[["code", "name", "days_present", "attendance_%"]], hide_index=True)

    st.subheader("Full summary")
    st.dataframe(summary, hide_index=True)
    records = pd.DataFrame(db.attendance_records(start, end))
    st.download_button(
        "⬇ Excel (summary + detailed records)",
        to_excel({"Summary": summary, "Records": records}),
        f"attendance_{start}_to_{end}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- people
def page_people() -> None:
    import cv2  # lazy: dashboard still opens without face libs installed

    st.header("👥 People & Enrollment")
    people = pd.DataFrame(db.list_people())
    if people.empty:
        st.info("Abhi koi registered nahi.")
    else:
        st.dataframe(people.drop(columns=["id"]), hide_index=True)

    st.subheader("Register / add samples")
    c1, c2 = st.columns(2)
    code = c1.text_input("Roll no / Employee ID")
    name = c2.text_input("Full name")
    role = c1.selectbox("Role", ["student", "teacher"])
    dept = c2.text_input("Department")
    uploads = st.file_uploader("Photos (3-6, alag alag angles)", type=["jpg", "jpeg", "png"],
                               accept_multiple_files=True)
    shot = st.camera_input("Ya webcam se photo lo")

    if st.button("Enroll", type="primary"):
        if not code.strip() or not name.strip():
            st.error("Code aur name zaroori hain.")
        else:
            files = list(uploads) + ([shot] if shot else [])
            images = [cv2.imdecode(np.frombuffer(f.getvalue(), np.uint8), cv2.IMREAD_COLOR)
                      for f in files]
            if not images:
                st.error("Kam az kam ek photo do.")
            else:
                try:
                    from face_engine import enroll_person
                    _, ok, bad = enroll_person(code, name, role, dept, images)
                    st.success(f"{name} enrolled. Accepted: {ok}, rejected: {bad}")
                except ValueError as e:
                    st.error(str(e))

    if not people.empty:
        st.subheader("Remove a person")
        label = {r["id"]: f'{r["name"]} ({r["code"]})' for r in people.to_dict("records")}
        pid = st.selectbox("Person", list(label), format_func=label.get)
        confirm = st.checkbox("Haan, is person ka saara data delete karo")
        if st.button("Delete") and confirm:
            code_del = people.loc[people["id"] == pid, "code"].iloc[0]
            db.delete_person(pid)
            shutil.rmtree(config.FACES_DIR / code_del, ignore_errors=True)
            st.success("Deleted.")
            st.rerun()


# ------------------------------------------------------------------ main
if check_login():
    page = st.sidebar.radio("Menu", ["📊 Live Overview", "📅 Daily Report",
                                     "📈 Analytics", "👥 People & Enrollment"])
    if st.sidebar.button("Logout"):
        st.session_state.auth = False
        st.rerun()
    {"📊 Live Overview": page_live, "📅 Daily Report": page_daily,
     "📈 Analytics": page_analytics, "👥 People & Enrollment": page_people}[page]()

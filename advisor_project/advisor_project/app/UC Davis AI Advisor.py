import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import re

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

sys.path.append(str(ROOT))
sys.path.append(str(BACKEND))

# Components
from components.header import render_header
from components.sidebar import render_sidebar
from components.course_tables import render_results



# --------------------------------------------------------------
# 🔧 Lazy Loaders (Keeps App Fast)
# --------------------------------------------------------------
def load_advisor_backend():
    from backend.a_backend import (
        suggest_eligible_courses,
        chatbot_engine,
        advisor_chat_llm,
        extract_completed_from_text,
    )
    return (
        suggest_eligible_courses,
        chatbot_engine,
        advisor_chat_llm,
        extract_completed_from_text,
    )

def load_ai_engine():
    from backend.ai_engine import ask_deepseek
    return ask_deepseek

def load_readTranscript():
    from backend.readTranscript import readTranscript
    return readTranscript

def load_degree_checker():
    from backend.degreeChecker import majorData, keepSentence
    return majorData, keepSentence

def load_course_graphs():
    from backend.course_graphs import plot_course_dependency_graph
    return plot_course_dependency_graph



# --------------------------------------------------------------
# 🌟 Unified App Config
# --------------------------------------------------------------
st.set_page_config(page_title="UC Davis AI Advisor", page_icon="🎓", layout="wide")

render_header()
render_sidebar()


# --------------------------------------------------------------
# 🧠 Initialize Global Session State
# --------------------------------------------------------------
DEFAULT_STATE = {
    "completed_courses_master": [],
    "completed_input_textarea" : None,
    "messages": [],
    "declared_majors": [],
    "active_tab": "Eligibility",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


if "elig_completed_textarea" not in st.session_state:
    st.session_state.elig_completed_textarea = ""

# --------------------------------------------------------------
# 🌐 Navigation Bar (Replaces streamlit native tabs)
# --------------------------------------------------------------
tabs = ["Eligibility", "AI Chatbot", "Degree Progress Checker"]

choice = st.radio(
    "Navigation",
    tabs,
    horizontal=True,
    index=tabs.index(st.session_state.active_tab),
)

st.session_state.active_tab = choice



# --------------------------------------------------------------
# 🟦 PAGE 1 — COURSE ELIGIBILITY
# --------------------------------------------------------------
def render_eligibility_page():

    st.header("Course Eligibility Checker")
    st.warning("⚠️ This is a student-built project. No data is saved after your session ends.")

    col1, col2 = st.columns([1, 2])

    # -------------------------
    # SUBJECT CODE INPUT
    # -------------------------
    with col1:
        subject_code = st.text_input(
            "Subject Code (e.g., STA)",
            value=st.session_state.get("subject_code", "STA"),
            key="subject_code"
        ).upper()
    if st.session_state.completed_input_textarea is not None:
        st.session_state.elig_completed_textarea = st.session_state.completed_input_textarea
        st.session_state.completed_input_textarea = None
    # -------------------------
    # COMPLETED COURSES INPUT
    # -------------------------
    with col2:
        default_text = ", ".join(st.session_state.completed_courses_master)

        text_value = st.text_area(
            "Completed Courses (e.g., MAT 021A, STA 013):",
            value=default_text,
            key="elig_completed_textarea"
        )

        if text_value.strip() != default_text.strip():
            st.session_state.completed_courses_master = [
                c.strip().upper() for c in text_value.split(",") if c.strip()
            ]

        # Transcript Upload
        uploaded_pdf = st.file_uploader("Upload Transcript (PDF):", type=["pdf"])
        st.caption("Uploaded transcripts are processed in memory and deleted immediately.")

        if uploaded_pdf is not None and st.button("Process Transcript"):
            with st.spinner("Processing transcript..."):
                try:
                    readTranscript = load_readTranscript()
                    transcript = readTranscript(uploaded_pdf)

                    extracted = [
                        c.strip().upper()
                        for c in transcript["Course"].tolist()
                    ]

                    # Update master list
                    st.session_state.completed_courses_master = sorted(
                        list(set(st.session_state.completed_courses_master + extracted))
                    )

                    # Update the UI text area
                    st.session_state.completed_input_textarea = ", ".join(
                        st.session_state.completed_courses_master
                    )

                    st.success("Transcript processed!")
                    st.rerun()

                except Exception as e:
                    st.error("Failed to process transcript. Please upload a valid UC Davis PDF transcript.")

    # Academic Level
    level = st.radio(
        "Select your academic level:",
        ["Undergraduate", "Graduate"],
        horizontal=True
    )
    level_key = "undergrad" if level == "Undergraduate" else "grad"

    # Eligibility Button
    if st.button("Check My Eligibility"):
        with st.spinner("Analyzing your eligibility..."):
            suggest_eligible_courses, *_ = load_advisor_backend()

            eligible_df, blocked_df = suggest_eligible_courses(
                subject_code,
                st.session_state.completed_courses_master,
                level_key
            )

        render_results(eligible_df, blocked_df, subject_code)

    if st.button("Show Prerequisite Graph"):
        with st.spinner("Building course graph..."):
            plot_course_dependency_graph = load_course_graphs()
            plot_course_dependency_graph(
                subject_code,
                st.session_state.completed_courses_master
            )



# --------------------------------------------------------------
# 🟩 PAGE 2 — AI CHATBOT
# --------------------------------------------------------------
def render_chatbot_page():

    st.markdown("## 🤖 AI Academic Advisor (DeepSeek-Powered)")

    # -------------------------
    # Completed Courses Editor
    # -------------------------
    display_text = ", ".join(st.session_state.completed_courses_master)

    textarea = st.text_area(
        "Edit your completed courses:",
        value=display_text,
        key="chat_completed_textarea"
    )

    if textarea.strip() != display_text.strip():
        st.session_state.completed_courses_master = [
            c.strip().upper() for c in textarea.split(",") if c.strip()
        ]

    st.divider()

    # -------------------------
    # Chat History
    # -------------------------
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # -------------------------
    # Chat Input Handler
    # -------------------------
    user_input = st.chat_input("Ask me anything about your courses, planning, or major…")

    if user_input:
        st.session_state.active_tab = "AI Chatbot"     # Stay on Chatbot
        st.session_state.last_message = user_input
        st.rerun()

    # -------------------------
    # Respond AFTER rerun
    # -------------------------
    if "last_message" in st.session_state:

        msg = st.session_state.last_message
        del st.session_state.last_message

        # Lazy imports
        (
            suggest_eligible_courses,
            chatbot_engine,
            advisor_chat_llm,
            extract_completed_from_text
        ) = load_advisor_backend()
        ask_deepseek = load_ai_engine()

        # Show user's message
        st.chat_message("user").write(msg)
        st.session_state.messages.append({"role": "user", "content": msg})

        # Extract courses mentioned
        extracted = extract_completed_from_text(msg)
        if extracted:
            st.session_state.completed_courses_master = sorted(
                set(st.session_state.completed_courses_master + extracted)
            )

        # Primary Advisor Model
        try:
            with st.spinner("Thinking..."):
                response, updated_courses, declared_majors = advisor_chat_llm(
                    user_text=msg,
                    completed_courses=st.session_state.completed_courses_master,
                    declared_majors=st.session_state.declared_majors
                )

            if not response:
                raise ValueError("Empty")

        except Exception:
            # Fallback model
            with st.spinner("Consulting DeepSeek…"):
                try:
                    response = ask_deepseek(
                        f"User asked: {msg}\nCompleted: {st.session_state.completed_courses_master}"
                    )
                except:
                    response = "Sorry, I am unable to answer right now."

            updated_courses = st.session_state.completed_courses_master
            declared_majors = st.session_state.declared_majors

        # Save updated state
        st.session_state.completed_courses_master = sorted(set(updated_courses))
        st.session_state.declared_majors = declared_majors

        # Show assistant response
        st.chat_message("assistant").write(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

        # Stay on chatbot page
        st.session_state.active_tab = "AI Chatbot"
        st.rerun()



# --------------------------------------------------------------
# 🟪 PAGE 3 — DEGREE PROGRESS CHECKER
# --------------------------------------------------------------
def render_degree_checker_page():

    majorData, keepSentence = load_degree_checker()
    md = majorData()

    st.header("Degree Progress Checker")

    col1, col2, col3 = st.columns([2, 3, 3])

    # Degree type
    with col1:
        type_of_degree = st.selectbox(
            "Select Degree Type:",
            ["Bachelor of Science", "Bachelor of Arts"]
        )

    # Major
    with col2:
        major = st.selectbox("Select Major:", list(md.keys()))

    # Track / Specialization
    chosenMajor = md.get(major)
    trackOpt = ["-- No tracks available --"]

    if chosenMajor is not None:
        degCode = "B.S." if type_of_degree == "Bachelor of Science" else "B.A."
        filtering = chosenMajor[chosenMajor["degreeType"] == degCode]

        for col in ["Track", "Specialization", "Plan", "Emphasis"]:
            if col in filtering.columns:
                trackOpt = filtering[col].dropna().unique().tolist()
                break

    with col3:
        track = st.selectbox("Select Track/Specialization:", trackOpt)

    # Completed courses
    deg_text = ", ".join(st.session_state.completed_courses_master)

    deg_text_value = st.text_area(
        "Completed Courses (comma separated):",
        value=deg_text,
        key="degree_completed_textarea"
    )

    st.session_state.completed_courses_master = [
        c.strip().upper() for c in deg_text_value.split(",") if c.strip()
    ]

    # Degree Check Button
    if st.button("Evaluate Progress"):
        dfMajor = md.get(major)
        if dfMajor is None:
            st.error("Major not found.")
            return

        # Filter by degree type
        degCode = "B.S." if type_of_degree == "Bachelor of Science" else "B.A."
        filtered = dfMajor[dfMajor["degreeType"] == degCode]

        if filtered.empty:
            st.warning(f"{major} does not offer a {degCode}.")
            return

        # Track filtering
        if track in filtered.get("Track", []):
            select = filtered[filtered["Track"] == track]
        else:
            select = filtered

        if select.empty:
            st.warning("Select a valid track/options.")
            return

        row = select.iloc[0]

        completedSet = set(st.session_state.completed_courses_master)
        met, unmet = [], []

        ignore = {"degreeType", "Major", "Track", "Specialization", "Plan", "Emphasis"}

        for col in row.index:
            if col in ignore:
                continue

            reqStr = str(row[col])
            if not reqStr.strip() or reqStr == "nan":
                continue

            isSentence = keepSentence(reqStr)

            if isSentence:
                met.append({
                    "Category": col,
                    "Completed": [],
                    "Requirement Text": reqStr
                })
                unmet.append({
                    "Category": col,
                    "Not Completed": [],
                    "Requirement Text": reqStr
                })
                continue

            # Extract course codes
            reqCourses = re.findall(r"[A-Z]{2,4}\s*\d{1,4}[A-Z]?", reqStr)
            reqCourses = [
                re.sub(r"\s+", " ", c).upper() for c in reqCourses
            ]

            metC = [c for c in reqCourses if c in completedSet]
            unmetC = [c for c in reqCourses if c not in completedSet]

            met.append({"Category": col, "Completed": metC})
            unmet.append({"Category": col, "Not Completed": unmetC})

        # Show results
        st.subheader("Requirements Met")
        st.dataframe(pd.DataFrame(met), use_container_width=True)

        st.subheader("Requirements Still Needed")
        st.dataframe(pd.DataFrame(unmet), use_container_width=True)



# --------------------------------------------------------------
# 🟩 RENDER THE ACTIVE PAGE
# --------------------------------------------------------------
if st.session_state.active_tab == "Eligibility":
    render_eligibility_page()

elif st.session_state.active_tab == "AI Chatbot":
    render_chatbot_page()

elif st.session_state.active_tab == "Degree Progress":
    render_degree_checker_page()

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

from components.header import render_header
from components.sidebar import render_sidebar
from components.course_tables import render_results

backend_path = Path(__file__).resolve().parents[1] / "backend"
sys.path.append(str(backend_path))

from advisor_backend import suggest_eligible_courses, chatbot_engine
from readTranscript import readTranscript


st.set_page_config(
    page_title="UC Davis AI Advisor",
    page_icon="🎓",
    layout="wide"
)


render_header()
render_sidebar()

# Initialize session state keys
if "completed_courses_input" not in st.session_state:
    st.session_state.completed_courses_input = ""
if "new_completed_courses" not in st.session_state:
    st.session_state.new_completed_courses = None

if ("new_completed_courses" in st.session_state and st.session_state.new_completed_courses is not None):
    st.session_state.completed_courses_input = st.session_state.new_completed_courses
    st.session_state.completed_courses_chat_value = st.session_state.new_completed_courses
    st.session_state.new_completed_courses = None

tab1, tab2 = st.tabs(["Course Eligibility", "AI Chatbot"])


with tab1:
    st.header("Course Eligibility Checker")

    col1, col2 = st.columns([1, 2])
    with col1:
        subject_code = st.text_input(
            "Subject Code (e.g., STA):",
            value="STA",
            key="subject_code_input"
        ).upper()

    if st.session_state.new_completed_courses is not None:
        st.session_state.completed_courses_input = st.session_state.new_completed_courses
        st.session_state.new_completed_courses = None

    with col2:
        completed_courses_text = st.text_area(
            "Completed Courses: (e.g., MAT 021A, STA 013)",
            key="completed_courses_input"
        )
        uploaded_pdf = st.file_uploader(
        "Upload Transcript (PDF):",
        type=["pdf"],
        key="upload_transcript"
        )
        

        if uploaded_pdf is not None:
            if st.button("Process Transcript"):
                with st.spinner("Processing transcript..."):
                    transcript = readTranscript(uploaded_pdf)
                    completed = transcript["Course"].tolist()
                    completedCourses = ", ".join(completed)

                    st.session_state.new_completed_courses = completedCourses
                    st.success("Transcript processed!")
                st.rerun()
        

    level = st.radio(
        "Select your academic level:",
        ["Undergraduate", "Graduate"],
        horizontal=True,
        key="academic_level_radio"
    )

    level_key = "undergrad" if level == "Undergraduate" else "grad"

    if st.button("Check My Eligibility", key="check_button"):
        completed_list = [c.strip().upper() for c in completed_courses_text.split(",")]

        with st.spinner("Analyzing your eligibility..."):
            eligible_df, blocked_df = suggest_eligible_courses(
                subject_code,
                completed_list,
                level_key
            )

        render_results(eligible_df, blocked_df, subject_code)


with tab2:
    st.header("AI Academic Advisor Chatbot")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    if "completed_courses_chat_value" not in st.session_state:
        # Start with new_completed_courses or fallback to completed_courses_input or empty string
        st.session_state.completed_courses_chat_value = st.session_state.get("completed_courses_input", "")


    st.subheader("Your Completed Courses")
    completed_sidebar = st.text_area(
        "Completed Courses (comma separated):",
        key="completed_courses_chat_value",
    )

    completed_for_chat = [c.strip().upper() for c in (completed_sidebar or "").split(",") if c.strip()]

    st.divider()


    for msg in st.session_state["messages"]:
        st.chat_message(msg["role"]).write(msg["content"])


    user_msg = st.chat_input("Ask me anything about the courses, requirements, or planning!")


    if user_msg: 

        st.session_state["messages"].append({"role": "user", "content": user_msg})
        st.chat_message("user").write(user_msg)


        response = chatbot_engine(user_msg, completed_for_chat)

        st.session_state["messages"].append({"role": "assistant", "content": response})
        st.chat_message("assistant").write(response)


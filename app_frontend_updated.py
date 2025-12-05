import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import re

from components.header import render_header
from components.sidebar import render_sidebar
from components.course_tables import render_results

backend_path = Path(__file__).resolve().parents[1] / "backend"
sys.path.append(str(backend_path))

from advisor_backend import suggest_eligible_courses, chatbot_engine
from readTranscript import readTranscript
from degreeChecker import majorData, keepSentence


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

tab1, tab2, tab3 = st.tabs(["Course Eligibility", "AI Chatbot", "Degree Progress Checker"])


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

with tab3:
    md = majorData()
    st.header("Degree Progress Checker")

    st.markdown("**Important note:** This Checker does not account for \"OR\" cases or \"Choose n from from the list\" scenarios. It simply checks which courses from the degree requirements you have completed based on your input.")

    col1, col2, col3 = st.columns([2, 3, 3])
    with col1:
        typeOfDegree = st.selectbox(
            "Select Degree Type:",
            ["Bachelor of Science", "Bachelor of Arts"],
            key="degree_type_selectbox"
        )

    with col2:
        major = st.selectbox(
            "Select Major:",
            list(md.keys()),
            key="major_selectbox"
    )
    
    chosenMajor = md.get(major)
    trackOpt = ["-- No tracks available --"]

    if chosenMajor is not None:
        degCode = "B.S." if typeOfDegree == "Bachelor of Science" else "B.A."

        filtering = chosenMajor[chosenMajor["degreeType"] == degCode]
        tit = ["Track", "Specialization", "Plan", "Emphasis"]

        trackCol = None
        for col in tit:
            if col in filtering.columns:
                trackCol = col
                break
        
        if trackCol is not None and not filtering[trackCol].dropna().empty:
            trackOpt = filtering[trackCol].dropna().unique().tolist()


    with col3:
        track = st.selectbox(
            "Select Track/Specialization/Plan/Emphasis:",
            trackOpt,
            key="track_selectbox"
        )

    if "completed_courses_degree_value" not in st.session_state:
        # Start with new_completed_courses or fallback to completed_courses_input or empty string
        st.session_state.completed_courses_degree_value = st.session_state.get("completed_courses_input", "")

    completed_degree_check = st.text_area(
        "Completed Courses (comma separated):",
        key="completed_courses_degree_value",
    )

    st.caption("You may need to click the button twice to see results after changing inputs above.")
    submitted = st.button("Check", key="degCheck_button")

    if submitted:
        dfMajor = md.get(major)
        select = None

        degCode = "B.S." if typeOfDegree == "Bachelor of Science" else "B.A."
        filtered = dfMajor[dfMajor["degreeType"] == degCode]

        if filtered.empty:
            st.warning(f"{major} does not have a {degCode} degree.")
        else:
            tit2 = ["Track", "Specialization", "Plan", "Emphasis"]
            m = next((col for col in tit2 if col in filtered.columns), None)

            if m:
                valid = filtered[m].dropna()
                if track in valid.values:
                    select = filtered[filtered[m] == track]
                else:
                    st.info("Please select a valid track/specialization/plan/emphasis.")
            else:
                select = filtered

        if select is not None and not select.empty:
            completed_for_degree = [
                c.strip().upper()
                for c in st.session_state.completed_courses_degree_value.split(",")
                if c.strip()
            ]

            completedSet = set(completed_for_degree)


            row = select.iloc[0]

            met = []
            unmet = []

            ignore = {"degreeType", "Major", "Track", "Specialization", "Plan", "Emphasis"}

            for col in row.index:
                if col in ignore:
                    continue

                reqStr = row[col]
                if pd.isna(reqStr) or str(reqStr).strip() == "":
                    continue

                if keepSentence(reqStr):
                    # It's a descriptive sentence
                    met.append({"Category": col, "Completed": [], "Requirement Text": reqStr})
                    unmet.append({"Category": col, "Not Completed": [], "Requirement Text": reqStr})
                else:
                    # It's a list of courses: check against completed courses
                    reqCourses = re.findall(r"[A-Z]{2,4}\s*\d{1,4}[A-Z]?", str(reqStr)) 

                    reqCourses = [re.sub(r"\s+", " ", c).replace("\xa0", " ").strip().upper() for c in reqCourses] 

                    metC = sorted(list(set([course for course in reqCourses if course.upper() in completedSet])))
                    unmetC = sorted(list(set([course for course in reqCourses if course.upper() not in completedSet])))

                    met.append({"Category": col, "Completed": metC})
                    unmet.append({"Category": col, "Not Completed": unmetC})

            

            met_df = pd.DataFrame(met)
            unmet_df = pd.DataFrame(unmet)
                
            st.subheader("Degree Requirements Met")
            st.caption("Double click on a cell to view full content if cut off.")
            st.dataframe(met_df, width = "stretch")

            st.subheader("Degree Requirements Not Yet Met")
            st.dataframe(unmet_df, width = "stretch")
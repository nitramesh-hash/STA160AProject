import streamlit as st
import pandas as pd
from pathlib import Path
import sys


st.set_page_config(page_title="UC Davis AI Advisor", page_icon="🎓", layout="wide")

backend_path = Path(__file__).resolve().parents[1] / "backend"
sys.path.append(str(backend_path))

from advisor_backend import suggest_eligible_courses
from components.header import render_header
from components.sidebar import render_sidebar


render_header()
render_sidebar()


col1, col2 = st.columns([1, 2])
with col1:
    subject_code = st.text_input("Subject Code (e.g., STA):", value="STA").upper()
with col2:
    completed_courses = st.text_area("Completed Courses:", value="STA 013, MAT 016B")


level = st.radio("Select your academic level:", ["Undergraduate", "Graduate"], horizontal=True)
level_key = "undergrad" if level == "Undergraduate" else "grad"


if st.button("Check My Eligibility"):
    completed_list = [c.strip().upper() for c in completed_courses.split(",")]

    with st.spinner("Analyzing your eligibility..."):
        eligible_df, blocked_df = suggest_eligible_courses(subject_code, completed_list, level_key)

        offerings_path = backend_path / "datasets" / f"{subject_code}_all_offerings.csv"
        if offerings_path.exists():
            off_df = pd.read_csv(offerings_path)
            if "Course Code" in off_df.columns and "Term" in off_df.columns:
                off_df["Course Code"] = off_df["Course Code"].astype(str).str.strip().str.upper()
                eligible_df["Course Code"] = eligible_df["Course Code"].astype(str).str.strip().str.upper()


                term_summary = (
                    off_df.groupby("Course Code")["Term"]
                    .apply(lambda x: ", ".join(sorted(set(x))))
                    .reset_index()
                    .rename(columns={"Term": "Term Offered"})
                )
                eligible_df = eligible_df.merge(term_summary, on="Course Code", how="left").fillna({"Term Offered": "—"})
            else:
                st.warning("⚠️ Offerings file missing 'Course Code' or 'Term' columns.")
        else:
            st.info(f"No offerings file found for {subject_code}. Run the scraper first.")


        st.markdown("### Eligible Courses and When Offered")
        if not eligible_df.empty:
            st.dataframe(eligible_df[["Course Code", "Title", "Term Offered"]], use_container_width=True)
        else:
            st.write("No eligible courses found.")

        st.markdown("### Blocked Courses (Unmet Prerequisites)")
        if blocked_df is not None and not blocked_df.empty:
            cols = [c for c in ["Course Code", "Title", "Course", "Missing"] if c in blocked_df.columns]
            st.dataframe(blocked_df[cols], use_container_width=True)
        else:
            st.success("No blocked courses found!")



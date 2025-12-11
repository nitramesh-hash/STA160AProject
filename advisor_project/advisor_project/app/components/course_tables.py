import streamlit as st
def render_results(eligible_df, blocked_df, subject_code):
    st.subheader(f"Eligible Courses for {subject_code}")
    if eligible_df is not None and not eligible_df.empty:
        display_cols = ["Course Code", "Title"]
        if "Offered" in eligible_df.columns:
            display_cols.append("Offered")
        st.dataframe(eligible_df[display_cols], use_container_width=True)
    else:
        st.info("No eligible courses found.")

    st.subheader("Blocked Courses (Unmet Prerequisites)")
    if blocked_df is not None and not blocked_df.empty:

        #  Convert OR-groups to readable strings 
        formatted_blocked = blocked_df.copy()

        def format_missing(cell):
            formatted = []
            for group in cell:
                formatted.append(" OR ".join(group)) 
            return formatted

        formatted_blocked["Missing"] = formatted_blocked["Missing"].apply(format_missing)

        st.dataframe(formatted_blocked, use_container_width=True)

    else:
        st.info("No blocked courses.")

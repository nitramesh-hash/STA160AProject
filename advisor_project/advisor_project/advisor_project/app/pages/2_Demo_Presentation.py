import streamlit as st

st.set_page_config(
    page_title="Video Presentation",
    page_icon="▶️",
    layout="wide"
)

st.title("Demo Presentation")
st.markdown("---")

st.video("https://youtu.be/mwLja5z_vzE")  # Replace with actual video URL

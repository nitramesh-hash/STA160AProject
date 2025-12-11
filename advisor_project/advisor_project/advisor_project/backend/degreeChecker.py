import pandas as pd
import numpy as np
import re
import streamlit as st
from pathlib import Path


def majorData():
    # The folder "majorReqs" MUST be in the same backend directory
    base = Path(__file__).resolve().parent / "majorReqs"

    # Map majors to filenames
    files = {
        "Chemistry": "chemistryMajorReqs.csv",
        "Computer Science": "computerscienceMajorReqs.csv",
        "Economics": "economicsMajorReqs.csv",
        "Mathematics": "mathematicsMajorReqs.csv",
        "Physics": "physicsMajorReqs.csv",
        "Statistics": "statisticsMajorReqs.csv",
    }

    majorDf = {}
    for major, fname in files.items():
        path = base / fname   # Combine folder + filename
        majorDf[major] = pd.read_csv(path)

    return majorDf



def keepSentence(reqStr):
    if pd.isna(reqStr) or str(reqStr).strip() == "":
        return False
    

    # Split by commas
    parts = [p.strip() for p in str(reqStr).split(",") if p.strip()]
    if len(parts) < 2:
        # Single item, probably a sentence
        return True
    
    # Count how many course codes are in the string
    # Course codes are like ABC 123 or ABC123A
    course_pattern = re.compile(r"^[A-Z]{2,4}\s?\d{3}[A-Z]{0,2}$")
    course_count = sum(bool(course_pattern.match(p)) for p in parts)
    
    # Checks if 20% or more of the parts are course codes
    # If yes, then it's a list of courses, not a sentence
    if course_count / len(parts) >= 0.20:  # 20% or more
        return False
    
    return True  # Otherwise, it's a sentence describing the requirement
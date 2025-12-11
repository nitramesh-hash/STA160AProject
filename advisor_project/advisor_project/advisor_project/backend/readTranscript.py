import pandas as pd
import re
from pypdf import PdfReader


def readTranscript(pdf):
    # Reads the PDF transcript
    reader = PdfReader(pdf)
    # Stores the text for each page in a list
    pages = [p.extract_text() for p in reader.pages if p.extract_text() != ""]
    
    # Create empty series to store all the text in chronological order
    comb = pd.Series()

    # Loops over each page
    for p in pages:
        # Stores each line in a list
        lines = [line for line in p.split('\n') if line.strip() != '']
        # Takes the first 61 spaces as left column
        left = pd.Series([line[:61].strip() for line in lines])
        # Takes the remaining spaces as right column
        right = pd.Series([line[61:].strip() for line in lines])
        # Stacks the left column text ontop of the right column
        tog = pd.concat([left, right], ignore_index=True)
        # If there's more than one page, then the left and right are put under the previous page
        comb = pd.concat([comb, tog], ignore_index=True)

    df = extQandInfo(comb)
    df = parseCourses(df)
    df = splitQuarterYear(df)
    return df


# Separates the quarter from the classes
def extQandInfo(comb):
    # Find the lines that indicates the quarter
    q = comb.str.contains(r"^(FALL|WINTER|SPRING|SUMMER) (QUARTER|SESSION [12]) ([0-9]{4})")

    # Extract the quarters and fill down so each class is labeled with its quarter
    quarters = comb.where(q).str.extract(r"^((FALL|WINTER|SPRING|SUMMER) (QUARTER|SESSION [12])) ([0-9]{4})")
    quarters = quarters[0].str.title() + ' ' + quarters[3]
    quarters = quarters.ffill()

    # Makess a df with quarters and course info
    df = pd.DataFrame({"Quarter": quarters, "Info": comb})
    # Removes non-course info rows
    df = df[df['Info'].str.contains(r"([A-Z ]+[0-9]+[A-Z]?[A-Z]?) +([A-Z &/:]+) +([A-Z+-]+) +([0-9.]+).*")].reset_index(drop=True)
    return df

# Gets the course, course title, grade, and units from the info
def parseCourses(df):
    info = df["Info"]
    # Extract course parts
    parts = info.str.extract(r"([A-Z]+) +([0-9]+[A-Z]?[A-Z]?) +(.+?)\s+(?:([^\s]{1,2})\s+)?([0-9.]+).*")
    df["Course"] = parts[0] + ' ' + parts[1]
    df["Title"] = parts[2]
    df["Grade"] = parts[3]
    df["Units"] = parts[4].astype(float)
    df1 = df[["Quarter", "Course", "Title", "Grade", "Units"]]
    return df1

# Splits the quarter column into quarter (season) and year
def splitQuarterYear(df):
    # Extract quarter and year
    times = df["Quarter"].str.extract(r"(Winter|Summer Session [1,2]|Fall|Spring)( Quarter)? ([0-9]{4})")
    df["Quarter"] = times[0]
    df["Year"] = times[2].astype(int)
    # Puts columns in order
    df = df[["Year", "Quarter", "Course", "Title", "Grade", "Units"]]
    return df
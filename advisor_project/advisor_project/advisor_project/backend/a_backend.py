import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from pathlib import Path
from ai_engine import ask_deepseek
import json
import streamlit as st


from degree_engine import (
    evaluate_major_progress,
    evaluate_multi_major_progress,
    list_available_degrees,
    can_take_course_backend,
    missing_prereqs_backend,
    find_eligible_courses_backend,
    count_future_unlocks,
    PREREQ_GRAPH,
    get_course_unlocks,
    get_unlock_chain,
    get_reverse_prereq_chain,   
)

def recommend_best_next_courses(completed_courses, declared_majors, limit=5):
    """
    Recommend the best next courses based on:
    - eligibility (graph)
    - major requirements remaining
    - how many future courses they unlock
    """

    completed_norm = [normalize_course_code(c) for c in completed_courses]

    # 1. Get eligible courses
    eligible = find_eligible_courses_backend(completed_norm)

    if not eligible:
        return []

    # 2. Load student's remaining requirements from degree engine
    remaining = set()
    if declared_majors:
        progress = evaluate_major_progress(completed_norm, declared_majors)
        for cat, items in progress.get("remaining_requirements", {}).items():
            for req in items:
                remaining.add(req)

    # 3. Score eligible courses
    scored = []
    for course in eligible:
        score = 0

        # +10 if the course is part of major requirements
        if course in remaining:
            score += 10

        # + number of future unlocks
        unlocks = count_future_unlocks(course)
        score += unlocks

        scored.append((score, course))

    # 4. Sort by score (highest first)
    scored.sort(reverse=True)

    # 5. Return the top recommendations
    return [course for _, course in scored[:limit]]



def suggest_eligible_courses_graph(completed_courses, limit=20):
    
    # Normalize inputs
    completed_norm = [normalize_course_code(c) for c in completed_courses if c]

    # Backend call — returns list of eligible course codes
    eligible = find_eligible_courses_backend(completed_norm)

    # Sort alphabetically for consistency
    eligible = sorted(eligible)

    # Return a limited set if desired
    return eligible[:limit]


def scrape_course_catalog(subject_code, save_dir="datasets"):
    base_dir = Path(__file__).resolve().parent
    datasets_dir = base_dir / save_dir
    os.makedirs(datasets_dir, exist_ok=True)

    url = f"https://catalog.ucdavis.edu/courses-subject-code/{subject_code.lower()}/"
    print(f"Scraping {url}")

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to load page: HTTP {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    courses = soup.find_all("div", class_="courseblock")

    data = []
    for course in courses:
        code = course.find("span", class_="detail-code")
        title = course.find("span", class_="detail-title")
        units = course.find("span", class_="detail-hours_html")
        desc = course.find("div", class_="courseblockextra")
        prereq = course.find(
            lambda tag: tag.has_attr("class")
            and any("detail-prerequisite" in c for c in tag["class"])
        )

        data.append(
            {
                "Course Code": code.get_text(strip=True) if code else "",
                "Title": title.get_text(strip=True) if title else "",
                "Units": units.get_text(strip=True) if units else "",
                "Description": desc.get_text(strip=True) if desc else "",
                "Prerequisites": (
                    prereq.get_text(strip=True)
                    .replace("Prerequisite(s):", "")
                    .strip()
                    if prereq
                    else ""),})

    df = pd.DataFrame(data)
    return df

@st.cache_data
def get_clean_catalog(subject_code: str):
    df = load_or_scrape_catalog(subject_code.upper())
    return cleanCSV2(df)


def cleanCSV2(df):
    import re
    clean_df = df.copy()

    def clean_prereq_text(raw):
        if not isinstance(raw, str):
            return ""

        t = raw

        # Normalize unicode spaces and dashes
        for bad in ["\xa0", "\u2007", "\u202f", "\u2060"]:
            t = t.replace(bad, " ")
        t = t.replace("—", "-").replace("–", "-")

        # (orMAT → OR MAT)
        t = re.sub(r"(?i)\bor(?=[A-Z])", " OR ", t)

        # (MAT017A → MAT 017A)
        t = re.sub(r"([A-Z]{2,4})(\d{2,3})([A-Z]{0,2})", r"\1 \2\3", t)

        # Remove grade requirement
        t = re.sub(
            r"\b([A-Z]{2,4}\s*\d{2,3})([A-Z])C-\s*(?:OR\s+BETTER|AND\s+ABOVE)",
            r"\1\2",
            t,
            flags=re.I
        )

        # Suffix then grade (e.g., MAT 017B C- or better)
        t = re.sub(
            r"\b([A-Z]{2,4}\s*\d{2,3})([A-Z])\s+[ABCDF][+-]?\s*(?:OR\s+BETTER|AND\s+ABOVE)?",
            r"\1\2",
            t,
            flags=re.I
        )

        t = re.sub(
            r"\b([A-Z]{2,4}\s*\d{2,3})\s+[ABCDF][+-]?\s*(?:OR\s+BETTER|AND\s+ABOVE)?",
            r"\1",
            t,
            flags=re.I
        )

        # Cleanup of glued grade minus (STA 013C- → STA 013)
        t = re.sub(
            r"\b([A-Z]{2,4}\s*\d{2,3})C-",
            r"\1",
            t
        )

        # Remove "can be concurrent"
        t = re.sub(r"\(\s*can be concurrent\s*\)", "", t, flags=re.I)
        t = re.sub(r"can be concurrent", "", t, flags=re.I)

        # Remove braces artifacts
        t = t.replace("{ }", "").replace("{}", "")

        # Space parentheses
        t = t.replace("(", " ( ").replace(")", " ) ")

        # Collapse whitespace
        t = re.sub(r"\s+", " ", t).strip()

        if t.endswith("."):
            t = t[:-1]

        t = re.sub(
    r"\b([A-Z]{2,4}\s*\d{2,3})C(?=\s*-\s*(OR\s+BETTER|AND\s+ABOVE))",
    r"\1",
    t,
    flags=re.I)

        return t

    clean_df["Prerequisites"] = clean_df["Prerequisites"].apply(clean_prereq_text)
    return clean_df




def cleanCSV(csv): 
    d = csv.copy()
    d["Title"] = cleanTitle(d["Title"])
    d["Units"] = cleanUnits(d["Units"])
    d["Learning Activities"] = learnActivities(d["Description"])
    d["Grade Mode"] = gradeMode(d["Description"])
    d["General Education"] = genEd(d["Description"])
    return d


def cleanTitle(titles):
    rx = r"^—\u00A0([A-Za-z &:+,'-]+).*"
    titles = titles.str.extract(rx, expand=False).str.strip()
    return titles


def cleanUnits(units):
    rx0 = r"^\(([0-9]).*"
    units = units.str.extract(rx0, expand=False).astype(int)
    return units


def learnActivities(descriptions):
    rx2 = r"(?<=Learning Activities:)([^.]+)"
    act = descriptions.str.extract(rx2)
    return act


def gradeMode(descriptions):
    rx3 = r"(?<=Grade Mode:)([^.]+)"
    mode = descriptions.str.extract(rx3)
    mode[mode == "P/NP only"] = "Pass/No Pass only"
    return mode


def genEd(descriptions):
    rx4 = r"(?<=General Education:)([^.]+)"
    genEd = descriptions.str.extract(rx4)
    rx5 = r"(?<=\()[A-Z]+(?=\))"
    l = genEd[0].str.findall(rx5).str.join(", ")
    return l

def extract_courses_codes(text):
    """
    Extract UC Davis-style course codes like STA 013, MAT 021A.
    """
    if not text:
        return []
    return re.findall(r"[A-Z]{2,4}\s*\d{1,3}[A-Z]?", str(text))


def extract_codes(text):
    t = text.upper()
    raw = re.findall(r"\b([A-Z]{2,4})\s*0?(\d{1,3})([A-Z]?)\b", t)

    normalized = []
    for dept, num, suf in raw:
        code = f"{dept} {num.zfill(3)}{suf}"
        normalized.append(code)

    return normalized


def load_or_scrape_catalog(subject_code, force_refresh=False):
    base_dir = Path(__file__).resolve().parent
    datasets_dir = base_dir / "datasets"
    datasets_dir.mkdir(exist_ok=True)

    file_path = datasets_dir / f"{subject_code.upper()}_courses.csv"

    if file_path.exists() and not force_refresh:
        print(f"Using cached CLEAN catalog for {subject_code.upper()}: {file_path}")
        return pd.read_csv(file_path)

    print(f"Refreshing catalog for {subject_code.upper()}...")
    raw_df = scrape_course_catalog(subject_code)

    if raw_df is None:
        print("Scrape failed; returning empty DataFrame.")
        return pd.DataFrame()

    clean_df = cleanCSV(raw_df)

    clean_df = cleanCSV2(clean_df)

    clean_df.to_csv(file_path, index=False)

    return clean_df


def advisor_can_take_graph(course_code, completed_courses):
    """
    Use the master prereq graph + backend logic to decide
    if the student can take a course.
    """
    # Nice display form (ECS 036B)
    course = normalize_course_code(course_code)

    # What the backend/graph actually use (ECS036B)
    course_key = course.replace(" ", "").upper()

    # Normalize completed courses to display form
    completed = {normalize_course_code(c) for c in completed_courses if c}

    # If course isn't in the prereq graph, fall back to "no data"
    if course_key not in PREREQ_GRAPH.nodes:
        return f"I don't have prerequisite data for **{course}**, so you may be free to take it."

    # Use degree engine backend logic (it does its own normalization)
    if can_take_course_backend(course, list(completed)):
        return f"Yes — you meet **all prerequisites** for **{course}**."

    # Show missing prereqs (pretty-print AND / OR groups)
    missing = missing_prereqs_backend(course, list(completed))
    if missing:
        pretty_parts = []

        for m in missing:
        # OR groups come in formatted like "(ECS040 or ECS036B)"
        # These should NOT be normalized; keep them exactly as-is
            if "(" in m or ")" in m:
                pretty_parts.append(m)
            else:
                pretty_parts.append(normalize_course_code(m))

        pretty = ", ".join(pretty_parts)
        return f"No — you must complete **{pretty}** before taking **{course}**."

    return f"I'm unable to determine prerequisites for **{course}**."


def get_subject_prefix(course_code):
    match = re.match(r"([A-Z]{3})", course_code.strip().upper())
    return match.group(1).lower() if match else None


def normalize_course_code(raw):
    if not isinstance(raw, str):
        return ""

    t = raw.upper().strip()
    t = re.sub(r"[^A-Z0-9]", "", t)

    m = re.match(r"([A-Z]{2,4})(\d{1,3})([A-Z]?)", t)
    if not m:
        return ""

    subj = m.group(1)
    num = m.group(2).zfill(3)
    suf = m.group(3)

    return f"{subj} {num}{suf}"


@st.cache_data
def get_parsed_catalog(subject_code):
    df = get_clean_catalog(subject_code)
    df = df.copy()  # avoid SettingWithCopy warnings
    df["Parsed"] = df["Prerequisites"].apply(parse_prereq_structure)
    return df



COURSE_PATTERN = re.compile(r"\b[A-Z]{2,4}\s?\d{2,3}[A-Z]?\b")
@st.cache_data
def parse_prereq_structure(text):
    if not isinstance(text, str) or not text.strip():
        return {"course_groups": [], "special_flags": []}

    t = text.upper().replace("\xa0", " ")

    special_flags = []
    if "CONSENT" in t: special_flags.append("consent")
    if "SENIOR" in t or "UPPER DIVISION" in t:
        special_flags.append("senior")
    if "GRADUATE" in t:
        special_flags.append("graduate_standing")
    if " RESTRICTED" in t or " MAJOR" in t:
        special_flags.append("major_restriction")

    # remove concurrency notes safely
    t = re.sub(r"\(CAN BE CONCURRENT\)", "", t, flags=re.I)
    t = re.sub(r"CAN BE CONCURRENT", "", t, flags=re.I)

    # recommended phrases
    t = re.sub(r"[^;,.]*PREFERRED", "", t)
    t = re.sub(r"[^;,.]*RECOMMENDED", "", t)

    # remove grade text after a course code
    t = re.sub(r"\b([A-Z]{2,4}\s*\d{3}[A-Z]?)\s+[ABCDF][+-]?\b", r"\1", t)

    # fix glued OR, ensure proper spacing
    t = re.sub(r'\bor(?=[A-Z])', ' OR ', t, flags=re.I)

    t = re.sub(r"\s+", " ", t).strip()

    # split AND groups
    and_groups = re.split(r"[.;]", t)

    course_groups = []
    for block in and_groups:
        block = block.strip()
        if not block:
            continue

        # split OR groups
        or_parts = re.split(r"\bOR\b", block)

        group_codes = []
        for part in or_parts:
            found = COURSE_PATTERN.findall(part)
            for code in found:
                code = re.sub(r"\s+", " ", code).strip()
                if code not in group_codes:
                    group_codes.append(code)

        if group_codes:
            course_groups.append(group_codes)

    return {
        "course_groups": course_groups,
        "special_flags": special_flags
    }



def suggest_eligible_courses(subject_code, completed_courses, student_level="undergrad"):
    df = get_parsed_catalog(subject_code)
    df = df[df["Course Code"].str.startswith(subject_code.upper())]
    df["Parsed"] = df["Prerequisites"].apply(parse_prereq_structure)
    
    # Normalize completed courses
    completed = {normalize_course_code(c) for c in completed_courses}

    eligible = []
    blocked = []

    # Level ranges
    if student_level == "undergrad":
        min_num, max_num = 1, 199
    elif student_level == "grad":
        min_num, max_num = 200, 499
    else:
        min_num, max_num = 1, 499

    for _, row in df.iterrows():

        course_code = row["Course Code"].upper().strip()
        title = row.get("Title", "").strip()
        prereq_text = str(row.get("Prerequisites", "")).strip()

        # Skip courses the student already completed
        if course_code in completed:
            continue

        # Check course level
        match = re.search(r"\d+", course_code)
        if not match:
            continue

        num = int(match.group())
        if not (min_num <= num <= max_num):
            continue

       
        prereq_result = df.loc[df["Course Code"] == course_code, "Parsed"].iloc[0]
        prereq_groups = prereq_result["course_groups"]
        special_flags = prereq_result["special_flags"]

        #No prereqs
        if not prereq_groups and not special_flags:
            eligible.append({
                "Course Code": course_code,
                "Title": title,
                "Missing": []
            })
            continue

        unmet = []


        for group in prereq_groups:
            # OR-logic: any one satisfies
            if not any(req in completed for req in group):
                unmet.append(group)

        if "consent" in special_flags:
            unmet.append(["Consent of instructor"])

        if "senior" in special_flags and student_level != "undergrad":
            pass
        elif "senior" in special_flags:
            unmet.append(["Senior standing"])

        if "graduate" in special_flags: 
            unmet.append(["Graduate standing"])
            
        if "major_restriction" in special_flags:
            unmet.append(["Restricted to majors"])

        if "restricted_enrollment" in special_flags:
            unmet.append(["Pass One / Pass Two enrollment restriction"])


        if unmet:
            blocked.append({
                "Course": course_code,
                "Title": title,
                "Missing": unmet
            })
        else:
            eligible.append({
                "Course Code": course_code,
                "Title": title,
                "Missing": []
            })

    # Convert to DataFrames
    eligible_df = pd.DataFrame(eligible)
    blocked_df = pd.DataFrame(blocked)

    return eligible_df, blocked_df

def advisor_can_take(course_code, completed_courses):
    return advisor_can_take_graph(course_code, completed_courses)

def advisor_course_unlocks(course_code):
    """
    User-facing function that explains what a course unlocks.
    """
    course = normalize_course_code(course_code)
    unlocks = get_course_unlocks(course)

    if not unlocks:
        return f"**{course}** does not unlock any additional courses, or I have no data for it."

    unlock_list = ", ".join(unlocks)
    return f"**{course}** unlocks the following courses: {unlock_list}"

def advisor_course_unlock_chain(course_code):
    """
    User-facing helper that returns the full chain of courses unlocked
    directly or indirectly by the given course.
    """
    course = normalize_course_code(course_code)
    chain = get_unlock_chain(course)

    if not chain:
        return f"**{course}** does not unlock any additional courses in its chain."

    return f"**{course}** leads to: {', '.join(chain)}"

def advisor_reverse_prereq_chain(course_code):
    """
    User-facing helper that explains what courses are required
    before taking a given course (direct + indirect prerequisites).
    """
    course = normalize_course_code(course_code)
    chain = get_reverse_prereq_chain(course)

    if not chain:
        return f"There are no recorded prerequisites required before **{course}**, or I have no data for it."

    return f"To take **{course}**, you should complete: {', '.join(chain)}"




def classify_intent(user_text: str) -> str:
    text = user_text.lower()

    # --------------------------------------
    # 1. Strong eligibility detection
    # --------------------------------------
    eligibility_phrases = [
        "can i take",
        "am i allowed to take",
        "eligible for",
        "eligible to take",
        "do i qualify for",
        "can i enroll in",
        "can i register for",
    ]
    if any(p in text for p in eligibility_phrases):
        return "eligibility"

    # --------------------------------------
    # 2. Reverse prerequisite chain
    # --------------------------------------
    reverse_phrases = [
        "what do i need before",
        "what do i need for",
        "need before",
        "before i can take",
        "before taking",
    ]
    if any(p in text for p in reverse_phrases):
        return "reverse_chain"

    # --------------------------------------
    # 3. Unlocks (“what does X unlock?”)
    # --------------------------------------
    unlock_phrases = [
        "what does",
        "lead to",
        "unlock",
        "allow me to take",
        "open up",
    ]
    if any(p in text for p in unlock_phrases):
        # If user says "what does X need" it's NOT unlock
        if "need" not in text:
            return "course_unlocks"

    # --------------------------------------
    # 4. Prerequisite listing (info)
    # --------------------------------------
    prereq_info_phrases = [
        "prerequisite",
        "prereq",
        "requirement for",
        "what is required for",
        "what do i need to qualify for",
    ]
    if any(p in text for p in prereq_info_phrases):
        return "prereq_info"

    # --------------------------------------
    # 5. Course info (description-type)
    # --------------------------------------
    info_phrases = [
    "what is ",
    "what is the",
    "tell me about",
    "course info",
    "description of",
]

# Prevent accidental match on "what"
    if any(p in text for p in info_phrases):

    # Block phrases about planning courses
        planning_phrases = [
            "what can i take",
            "what should i take",
            "what do i take after",
            "what should i take after",
            "what comes after",
            "what to take after",
    ]

    # If it's a planning question, DO NOT return course_info
        if any(p in text for p in planning_phrases):
            pass  # continue checking other intents
        else:
            return "course_info"

    # --------------------------------------
    # 6. Recommendation engine
    # --------------------------------------
    rec_phrases = [
        "what should i take next",
        "recommend",
        "next course",
        "next class",
    ]
    if any(p in text for p in rec_phrases):
        return "recommendation"

    # --------------------------------------
    # 7. Default
    # --------------------------------------
    return "other"
    
    
def chatbot_course_info(course_code):
    prefix = get_subject_prefix(course_code)
    if not prefix:
        return "I couldn't identify the subject for that course."

    df = get_clean_catalog(prefix)

    # Normalize BOTH sides
    df["Normalized"] = df["Course Code"].apply(normalize_course_code)
    code = normalize_course_code(course_code)

    row = df[df["Normalized"] == code]

    if row.empty:
        return f"No info found for {code}."

    title = row.iloc[0]["Title"]
    desc = row.iloc[0]["Description"]

    return f"**{code} — {title}**\n\n{desc}"


def chatbot_list_prereqs(course_code):
    code = normalize_course_code(course_code)
    prefix = get_subject_prefix(code)
    df = load_or_scrape_catalog(prefix)

    row = df[df["Course Code"].str.upper() == code]
    if row.empty:
        return f"I couldn't find {code} in the catalog."

    title = row.iloc[0]["Title"]
    prereq_text = str(row.iloc[0]["Prerequisites"] or "")

    parsed = parse_prereq_structure(prereq_text)
    groups = parsed["course_groups"]
    flags = parsed["special_flags"]

    if not groups and not flags:
        return f"**{code} ({title})** has **no prerequisites**."

    lines = []

    for group in groups:
        lines.append("- " + " OR ".join(group))

    for flag in flags:
        if flag == "consent":
            lines.append("- Or consent of instructor")
        elif flag == "senior":
            lines.append("- Upper-division/senior standing")
        elif flag == "major_restriction":
            lines.append("- Restricted to certain majors")
        elif flag == "restricted_enrollment":
            lines.append("- Pass One / Pass Two enrollment restriction")

    return (
        f"**Prerequisites for {code} ({title}):**\n\n" +
        "\n".join(lines)
    )


def chatbot_engine(message, completed_courses, declared_majors=None):
    intent = classify_intent(message)
    codes = [normalize_course_code(c) for c in extract_codes(message)]
    codes = [c for c in codes if c]

    # Normalize completed courses for all operations
    completed_norm = [normalize_course_code(c) for c in completed_courses]

    if intent in {"prerequisite_check", "prereq_info", "course_info"} and not codes:
        return "Which course are you asking about?"

    if intent == "prereq_info":
        return chatbot_list_prereqs(codes[0])

    if intent == "prerequisite_check":
        return advisor_can_take(codes[0], completed_norm)

    if intent == "course_info":
        return chatbot_course_info(codes[0])

    if intent == "course_unlocks":
        if not codes:
            return "Which course are you asking about?"
        return advisor_course_unlocks(codes[0])

    if intent == "unlock_chain":
        if not codes:
            return "Which course are you asking about?"
        return advisor_course_unlock_chain(codes[0])
    
    if intent == "reverse_chain":
        if not codes:
            return "Which course are you asking about?"
        return advisor_reverse_prereq_chain(codes[0])

    if intent == "recommendation":
        if not completed_courses:
            return "Tell me at least one course you've taken first."

        best = recommend_best_next_courses(
            completed_norm,
            declared_majors,
            limit=5
        )

        if not best:
            return "You are not eligible for any new courses right now."

        return "Your best next courses are: " + ", ".join(best)

    return "I can help with prerequisites, course info, or recommendations!"



def llm_extract_intent(user_text: str) -> dict:
    """
    Hybrid intent parser:
    - First use deterministic keyword logic
    - Then let the LLM confirm or refine
    - NEVER let LLM override strong-rule categories (eligibility / reverse_chain)
    """

    # Step 1: Strong deterministic classification
    strong_intent = classify_intent(user_text)

    # If we already know it's eligibility or reverse chain,
    # DO NOT let the LLM rewrite it.
    if strong_intent in {"eligibility", "reverse_chain"}:
        return {"intent": strong_intent, "course_codes": extract_codes(user_text)}

    # Step 2: Ask LLM only for softer cases
    prompt = f"""
Extract the student's intent from the text below.

TEXT:
"{user_text}"

Return ONLY a JSON dictionary with:
- "intent": one of ["eligibility","reverse_chain","prereq_info","course_info","course_unlocks","unlock_chain","recommendation","other"]
- "course_codes": list of detected course codes (use uppercase, no spaces)

Rules:
- Do NOT guess prerequisites.
- Do NOT invent intent categories.
- If unsure, return "other".
- If the question contains "next", "recommend", treat as recommendation.
- If the question asks "what does X unlock", return course_unlocks.
- If the question asks "what are the prerequisites for X", return prereq_info.
"""

    raw = ask_deepseek(
        [
            {"role": "system", "content": "You are an intent classification engine."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
    )

    # Try parsing JSON safely
    try:
        parsed = json.loads(raw)
        intent = parsed.get("intent", "other")
        codes = parsed.get("course_codes", [])
    except:
        intent = "other"
        codes = extract_codes(user_text)

    # If LLM picked something weak but keyword logic knows better:
    if intent == "other":
        intent = strong_intent  # fallback

    return {"intent": intent, "course_codes": codes}
    


def rule_engine_response(intent: str,
                         course_codes: list[str],
                         user_text: str,
                         completed_courses: list[str]):
    

    # Normalize completed courses using your function
    completed_norm = [normalize_course_code(c) for c in completed_courses if c]

    
    if intent == "course_info":
        if not course_codes:
            return "The student asked for course information but no specific course code was found."
        return chatbot_course_info(course_codes[0])

    
    if intent == "prereq_check":
        if not course_codes:
            return "The student asked whether they can take a course, but did not specify which one."
        return advisor_can_take(course_codes[0], completed_norm)

    
    if intent == "eligibility":
        if not completed_norm:
            return "The student asked for eligibility but did not list any completed courses."

        # Use your suggest_eligible_courses()
        last = completed_norm[-1]
        prefix = get_subject_prefix(last)
        if not prefix:
            return "Could not determine subject prefix for eligibility check."

        eligible_df, blocked_df = compute_eligibility(prefix, tuple(completed_norm), student_level)

        if eligible_df.empty:
            return "Based on completed courses, no eligible courses were found."

        first_ten = ", ".join(eligible_df["Course Code"].head(10).tolist())
        return f"Eligible courses based on completed classes: {first_ten}"

    
    if intent == "recommendation":
        if not completed_norm:
            return "The student asked for recommendations but did not list completed courses."

        last = completed_norm[-1]
        prefix = get_subject_prefix(last)
        if not prefix:
            return "Could not determine subject prefix for recommendations."

        eligible_df, blocked_df = suggest_eligible_courses(prefix, completed_norm)

        if eligible_df.empty:
            return "No follow-up courses appear eligible based on the rule engine."

        first_ten = ", ".join(eligible_df["Course Code"].head(10).tolist())
        return (
            "Student is asking for recommendations.\n"
            f"Completed courses: {completed_norm}\n"
            f"Eligible follow-up courses: {first_ten}\n"
            "Use this list to form recommendations based on student interests."
        )

    
    return (
        "The question does not match a structured intent. "
        f"Extracted course codes: {course_codes}. Completed courses: {completed_norm}."
    )


@st.cache_data
def cached_evaluate_multi_major_progress(completed, majors):
    return evaluate_multi_major_progress(completed_courses=completed, major_files=majors)
   

def advisor_chat_llm(user_text: str, completed_courses: list[str], declared_majors=None):
    """
    Handles:
    - detecting completed courses
    - intent parsing
    - declared majors memory (multi-turn)
    - multi-major degree evaluation
    - rule-engine-first prerequisite answers (prevents hallucination)
    """

    # -------------------------------
    # MAJOR MEMORY INITIALIZATION
    # -------------------------------
    if declared_majors is None:
        declared_majors = []

    # -------------------------------
    # HARD OVERRIDE: REVERSE PREREQ CHAIN
    # -------------------------------
    text_lower = user_text.lower()
    if ("need before" in text_lower or
        "before i can take" in text_lower or
        "before taking" in text_lower or
        "what do i need for" in text_lower):

        codes = [normalize_course_code(c) for c in extract_codes(user_text)]
        codes = [c for c in codes if c]

        if not codes:
            return "Which course are you asking about?", completed_courses, declared_majors

        answer = advisor_reverse_prereq_chain(codes[0])
        return answer, completed_courses, declared_majors

    # -------------------------------
    # DETECT NEWLY DECLARED MAJORS
    # -------------------------------
    new_majors = extract_majors_from_text(user_text)
    if new_majors:
        declared_majors = list(set(declared_majors + new_majors))
        major_note = f"\n\nI updated your declared majors: {declared_majors}"
    else:
        major_note = ""

    # -------------------------------
    # DETECT COMPLETED COURSES
    # -------------------------------
    explicit_completed = extract_completed_from_text(user_text)

    normalized_inbox = [
        normalize_course_code(c) for c in completed_courses if normalize_course_code(c)
    ]
    merged_completed = set(normalized_inbox + explicit_completed)

    # -------------------------------
    # INTENT PARSING
    # -------------------------------
    parsed = llm_extract_intent(user_text)
    intent = parsed["intent"]
    codes = parsed["course_codes"]

    lowered = user_text.lower()
    if any(phrase in lowered for phrase in [
        "can i take",
        "am i allowed to take",
        "am i allowed for",
        "do i qualify for",
        "eligible for",
        "eligible to take",
        "can i enroll in",
        "can i register for",
    ]):
        intent = "eligibility"


    update_note = ""
    if explicit_completed or (intent == "eligibility" and codes):
        update_note = f" I updated your completed courses to: {sorted(merged_completed)}."

    # -------------------------------
    # DEGREE PROGRESS (MULTI-MAJOR)
    # -------------------------------
    degree_evaluation_text = ""

    degree_related_phrases = [
        "major requirements",
        "degree progress",
        "how close am i",
        "requirements for my major",
        "what classes do i still need",
        "what do i need to graduate",
        "degree audit",
        "how far am i",
    ]

    user_asked_degree_progress = any(
        phrase in user_text.lower()
        for phrase in degree_related_phrases
    )

    if declared_majors and user_asked_degree_progress:
        try:
            progress_result = evaluate_multi_major_progress(
                completed_courses=list(merged_completed),
                major_files=declared_majors
            )
            degree_evaluation_text = (
                "\n\nDEGREE PROGRESS SUMMARY:\n"
                f"{json.dumps(progress_result.get('summary', {}), indent=2)}"
            )
        except Exception as e:
            degree_evaluation_text = f"\n\n[Degree engine error: {e}]"



    # --------------------------------------------------------------
    # 🚨 RULE-ENGINE-FIRST HANDLING FOR ANY PREREQ / ELIGIBILITY / INFO
    # --------------------------------------------------------------

    # If user asked about a specific course prereq, eligibility, or course info:
    if intent in {"eligibility", "prerequisite_check", "prereq_info", "course_info"}:
        if not codes:
            return "Which course are you asking about?", list(merged_completed), declared_majors

        course = codes[0]

        # 1. Prereq listing
        if intent == "prereq_info":
            answer = chatbot_list_prereqs(course)
            return answer, list(merged_completed), declared_majors

        # 2. Eligibility check (TRUE RULE ENGINE)
        if intent == "eligibility" or intent == "prerequisite_check":
            answer = advisor_can_take(course, list(merged_completed))
            return answer, list(merged_completed), declared_majors

        # 3. Course info could eventually use catalog, but for now use prereq info
        if intent == "course_info":
            answer = chatbot_course_info(course)
            return answer, list(merged_completed), declared_majors

    # --------------------------------------------------------------
    # RULE ENGINE BASE FACTS FOR OTHER INTENTS
    # --------------------------------------------------------------
    base_facts = rule_engine_response(
        intent=intent,
        course_codes=codes,
        user_text=user_text,
        completed_courses=list(merged_completed),
    )

    # --------------------------------------------------------------
    # LLM PROMPT (USED ONLY WHEN RULE ENGINE DOES NOT HANDLE IT)
    # --------------------------------------------------------------
    system_prompt = """
You are a friendly UC Davis academic advisor.
Use ONLY the provided rule-engine facts.
Do NOT invent prerequisites or guess missing data.
If the rule engine gives a result, trust it as absolute truth.
"""

    user_prompt = f"""
STUDENT INPUT:
{user_text}

COMPLETED COURSES:
{sorted(merged_completed)}

DECLARED MAJORS:
{declared_majors}

INTENT:
{intent}

FACTS FROM RULE ENGINE:
{base_facts}

{degree_evaluation_text}

Please answer the student clearly and helpfully.{update_note}{major_note}
"""

    # --------------------------------------------------------------
    # LLM CALL (SAFE, SECOND PRIORITY)
    # --------------------------------------------------------------
    final_answer = ask_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )

    # --------------------------------------------------------------
    # FINAL RETURN (frontend expects these)
    # --------------------------------------------------------------
    return final_answer, list(merged_completed), declared_majors



def extract_completed_from_text(text: str):
    """
    Extracts completed courses ONLY when the user clearly indicates
    completion, such as:
      - I took STA 013
      - I completed MAT 021A
    """
    text_lower = text.lower()

    completion_keywords = [
        "i took", "i have taken", "i've taken",
        "i completed", "i have completed",
        "i passed", "i finished", "i've done",
        "i already did", "i already took",
        "i already completed", "i have credit for",
    ]

    if not any(kw in text_lower for kw in completion_keywords):
        return []

    codes = extract_codes(text)
    normalized = [normalize_course_code(c) for c in codes if normalize_course_code(c)]
    return normalized

def extract_majors_from_text(text: str) -> list[str]:
    """
    Detect declared majors in natural language.

    Examples it detects:
    - "I am a CS major"
    - "I'm majoring in computer science"
    - "I am double majoring in CS and Statistics"
    - "My majors are ECS and STA"
    """

    text_low = text.lower()
    declared = []

    # Natural-language → JSON file mapping
    major_aliases = {
        # Computer Science
        "cs": "ecs_bs_2025_2026.json",
        "ecs": "ecs_bs_2025_2026.json",
        "computer science": "ecs_bs_2025_2026.json",

        # Statistics
        "statistics": "stats_bs_applied_2025_2026.json",
        "stats": "stats_bs_applied_2025_2026.json",
        "stat": "stats_bs_applied_2025_2026.json",
    }

    # Match whole words to avoid false matches:
    words = text_low.split()

    # Check different match modes
    for phrase, filename in major_aliases.items():

        # Mode 1: Exact phrase match
        if phrase in text_low:
            declared.append(filename)
            continue

        # Mode 2: Word-based match (prevents matching substrings accidentally)
        if phrase in words:
            declared.append(filename)
            continue

    # Remove duplicates
    return list(set(declared))



def extract_majors_from_text(text: str):
    """
    Detect if the student says:
    - I am a CS major
    - I'm double majoring in CS and Statistics
    - My majors are ECS and STA
    Returns a list of major filenames matching degree_requirements/.
    """

    text_low = text.lower()
    majors = []

    # Map natural-language majors → JSON filenames
    major_aliases = {
        "cs": "ecs_bs_2025_2026.json",
        "computer science": "ecs_bs_2025_2026.json",
        "ecs": "ecs_bs_2025_2026.json",

        "statistics": "stats_bs_applied_2025_2026.json",
        "stats": "stats_bs_applied_2025_2026.json",
        "stat": "stats_bs_applied_2025_2026.json"
    }

    for phrase, filename in major_aliases.items():
        if phrase in text_low:
            majors.append(filename)

    return majors

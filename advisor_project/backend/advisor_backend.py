import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from pathlib import Path
from ai_engine import ask_deepseek
from degree_engine import evaluate_multi_major_progress
import json
import streamlit as st

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

@st.cache_data(show_spinner=False)
def get_clean_catalog(subject_code):
    df = load_or_scrape_catalog(subject_code)
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


@st.cache_data(show_spinner=False)
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


def can_take_course(course_code, completed_courses, df):
    row = df[df["Course Code"] == course_code]
    if row.empty:
        return f"{course_code} not found in catalog."

    prereq_text = row.iloc[0]["Prerequisites"]
    if not prereq_text:
        return f"You can take {course_code} - no prerequisites."

    prereq_codes = extract_codes(prereq_text)
    if not prereq_codes:
        return f"You can take {course_code} - no specific course prerequisites"

    unmet = [c for c in prereq_codes if c not in completed_courses]

    if unmet:
        return f"You need to complete {','.join(unmet)} before taking {course_code}."
    else:
        return f"You meet the prerequisites for {course_code}."


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
    df = get_clean_catalog(subject_code)
    df = df[df["Course Code"].str.startswith(subject_code.upper())]

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

       
        prereq_result = parse_prereq_structure(prereq_text)
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
    # Normalize 
    course_code = normalize_course_code(course_code)
    completed = {normalize_course_code(c) for c in completed_courses}

    prefix = get_subject_prefix(course_code)
    if not prefix:
        return "I could not determine the department for that course."

    df = get_clean_catalog(prefix)

    # Pull course information
    row = df[df["Course Code"].str.upper() == course_code]
    if row.empty:
        return f"I couldn't find {course_code} in the catalog."

    title = row.iloc[0].get("Title", "").strip()
    prereq_text = str(row.iloc[0].get("Prerequisites", "")).strip()


    parsed = parse_prereq_structure(prereq_text)
    groups = parsed["course_groups"]          
    special_flags = parsed["special_flags"]   


    if not groups and not special_flags:
        return f"Yes — you can take **{course_code} ({title})**. This course has no prerequisites."

    unmet = []


    for group in groups:  
        if not any(req in completed for req in group):
            unmet.append(group)

    #special cases 
    if "consent" in special_flags:
        unmet.append(["Consent of instructor"])

    if "senior" in special_flags:
        unmet.append(["Upper-division/senior standing"])

    if "major_restriction" in special_flags:
        unmet.append(["Restricted to certain majors"])

    if "restricted_enrollment" in special_flags:
        unmet.append(["Pass One / Pass Two enrollment restriction"])

    #Eligible
    if not unmet:
        return f"Yes, you meet **all requirements** for **{course_code} ({title})**."


    formatted_missing = [" OR ".join(g) for g in unmet]
    missing_str = "\n".join(f"- {m}" for m in formatted_missing)

    return (
        f"No, you cannot take **{course_code} ({title})** yet.\n\n"
        f"You're missing:\n"
        f"{missing_str}"
    )


def classify_intent(user_text):
    text = user_text.lower()

    if "prerequisite" in text or "prereq" in text or "requirements" in text:
        return "prereq_info"

    if "can i take" in text or "eligible" in text or "am i allowed" in text:
        return "prerequisite_check"

    if "recommend" in text or "next class" in text or "what should i take" in text:
        return "recommendation"

    if "info" in text or "information" in text or "description" in text:
        return "course_info"

    return "small_talk"


def chatbot_course_info(course_code):
    prefix = get_subject_prefix(course_code)
    if not prefix:
        return "I couldn't identify the subject for that course."

    df = get_clean_catalog(prefix)

    row = df[df["Course Code"] == course_code.upper()]
    if row.empty:
        return f"No info found for {course_code.upper()}."

    title = row.iloc[0]["Title"]
    desc = row.iloc[0]["Description"]

    return f"**{course_code.upper()} — {title}**\n\n{desc}"


def chatbot_list_prereqs(course_code):
    code = normalize_course_code(course_code)
    prefix = get_subject_prefix(code)
    df = get_clean_catalog(prefix)

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


def chatbot_engine(message, completed_courses):
    intent = classify_intent(message)
    codes = [normalize_course_code(c) for c in extract_codes(message)]
    codes = [c for c in codes if c]

    if intent in {"prerequisite_check", "prereq_info", "course_info"} and not codes:
        return "Which course are you asking about?"

    if intent == "prereq_info":
        return chatbot_list_prereqs(codes[0])

    if intent == "prerequisite_check":
        return advisor_can_take(codes[0], completed_courses)

    if intent == "course_info":
        return chatbot_course_info(codes[0])

    if intent == "recommendation":
        if not completed_courses:
            return "Tell me at least one course you've taken first."

        prefix = get_subject_prefix(completed_courses[-1])
        eligible, blocked = suggest_eligible_courses(prefix, completed_courses)

        if eligible.empty:
            return "You are not eligible for any new courses right now."

        return "You are eligible for: " + ", ".join(
            list(eligible["Course Code"])[:10]
        )

    return "I can help with prerequisites, course info, or recommendations!"



def llm_extract_intent(user_text: str) -> dict:
    """
    Uses DeepSeek to extract:
      - intent: prereq_check | course_info | eligibility | recommendation | other
      - course_codes: list like ['STA 013', 'MAT 021B']
    """

    # ---- HARD RULE FALLBACKS BEFORE LLM ----
    t = user_text.lower()

    if any(x in t for x in [
        "what am i eligible",
        "what classes am i eligible",
        "what can i take",
        "what classes can i take",
        "eligible for",
        "eligible classes",
        "what courses can i take"
    ]):
        return {
            "intent": "eligibility",
            "course_codes": [normalize_course_code(c) for c in extract_codes(user_text)]
        }

    
    system_prompt = """
You are an intent parser for a UC Davis advising chatbot.

Return ONLY this JSON structure:
{
  "intent": "...",
  "course_codes": [...]
}

INTENTS:
- "eligibility": questions like "what can I take", "what am I eligible for"
- "prereq_check": "can I take X", "am I allowed for X"
- "course_info": "what is X", "tell me about X"
- "recommendation": "what should I take next"
- "other": anything else
"""

    raw = ask_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.1
    )

    try:
        data = json.loads(raw)
        raw_codes = data.get("course_codes", [])
        codes = [normalize_course_code(c) for c in raw_codes if normalize_course_code(c)]
        return {"intent": data.get("intent", "other"), "course_codes": codes}
    except:
        # fallback to "other"
        return {
            "intent": "other",
            "course_codes": [normalize_course_code(c) for c in extract_codes(user_text)]
        }
    



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

        eligible_df, blocked_df = suggest_eligible_courses(prefix, completed_norm)

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

    

def advisor_chat_llm(user_text: str, completed_courses: list[str], declared_majors=None):
    """
    Handles:
    - detecting completed courses
    - intent parsing
    - declared majors memory (multi-turn)
    - multi-major degree evaluation
    """

    # Initialize major memory
    if declared_majors is None:
        declared_majors = []

    # Detect newly declared majors from user text
    new_majors = extract_majors_from_text(user_text)
    if new_majors:
        declared_majors = list(set(declared_majors + new_majors))
        major_note = f"\n\nI updated your declared majors: {declared_majors}"
    else:
        major_note = ""

    # Detect completed courses from natural language
    explicit_completed = extract_completed_from_text(user_text)

    normalized_inbox = [
        normalize_course_code(c) for c in completed_courses if normalize_course_code(c)
    ]

    merged_completed = set(normalized_inbox + explicit_completed)

    # Intent parsing step
    parsed = llm_extract_intent(user_text)
    intent = parsed["intent"]
    codes = parsed["course_codes"]

    # Treat eligibility questions as implicit completed courses
    if intent == "eligibility" and codes:
        merged_completed.update(codes)

    # Note for chatbot output
    update_note = ""
    if explicit_completed or (intent == "eligibility" and codes):
        update_note = f" I updated your completed courses to: {sorted(merged_completed)}."

    # --------------------------------------------------
    # DEGREE PROGRESS SECTION (MULTI-MAJOR SUPPORT)
    # --------------------------------------------------
    degree_evaluation_text = ""

    if declared_majors:
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

    # --------------------------------------------------
    # COURSE-LEVEL RULE ENGINE
    # --------------------------------------------------
    base_facts = rule_engine_response(
        intent=intent,
        course_codes=codes,
        user_text=user_text,
        completed_courses=list(merged_completed),
    )

    # --------------------------------------------------
    # BUILD PROMPT
    # --------------------------------------------------
    system_prompt = """
You are a friendly UC Davis academic advisor.
Use only the provided facts. Do not invent courses or prerequisites.
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

FACTS:
{base_facts}

{degree_evaluation_text}

Please answer the student clearly and helpfully.{update_note}{major_note}
"""
    final_answer = ask_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )

    return final_answer, list(merged_completed), declared_majors



def extract_completed_from_text(text: str):

    text_lower = text.lower()

    # Keywords that imply course completion
    completion_keywords = [
        "i took",
        "i have taken",
        "i've taken",
        "i completed",
        "i have completed",
        "i passed",
        "i finished",
        "i've done",
        "i already did",
        "i already took",
        "i already completed",
        "i have credit for",
    ]

    if not any(kw in text_lower for kw in completion_keywords):
        return []

    # Otherwise extract codes normally
    codes = extract_codes(text)
    normalized = [normalize_course_code(c) for c in codes if normalize_course_code(c)]
    return normalized

def extract_majors_from_text(text: str) -> list[str]:

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

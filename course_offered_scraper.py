import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path
import time


def scrape_ucdavis_offerings(subject_code="STA", quarter=None):
    if quarter is None:
        quarter = {
            "202510": "Fall 2025",
            "202601": "Winter 2026",
            "202602": "Spring 2026",
            "202610": "Summer 2026",
            "202701": "Winter 2027",
            "202702": "Spring 2027"
        }

    url = "https://registrar-apps.ucdavis.edu/courses/search/course_search_results.cfm"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://registrar-apps.ucdavis.edu",
        "Referer": "https://registrar-apps.ucdavis.edu/courses/search/index.cfm"
    }

    all_data = []

    for code, name in quarter.items():
        print(f"\nScraping {subject_code.upper()} for {name} ({code})...")

        data = {
            "termCode": code,
            "course_number": "",
            "multiCourse": "",
            "course_title": "",
            "instructor": "",
            "subject": subject_code.upper(),
            "course_start_eval": "-",
            "course_start_time": "-",
            "course_end_eval": "-",
            "course_end_time": "-",
            "course_status": "-",
            "course_level": "-",
            "course_units": "-",
            "virtual": "-",   
            "runMe": "1",
            "clearMe": "1",
            "reorder": "",
            "gettingResults": "0",
            "formSearch": "Search",
            "submitButton": "Search"
        }

        response = requests.post(url, headers=headers, data=data, timeout=30)
        if response.status_code != 200:
            print(f" Failed for {name}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")

        if not table:
            print(f"No table found for {name}")
            continue

        rows = table.find_all("tr")
        print(f"Found {len(rows)} rows for {name}")

        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 2:
                continue


            text = " | ".join(cols)
            parts = text.split(" | ")


            if len(parts) >= 4:
                course_code = parts[0].strip()
                title = parts[2].replace("QLSE", "").strip()
                instructor = parts[3].split(",")[0].strip()
                units = parts[3].split(",")[-1].replace("4.0", "4 Units").strip()
            else:
                course_code, title, instructor, units = "", "", "", ""

            all_data.append({
                "Term": name,
                "Course Code": course_code,
                "Title": title,
                "Instructor": instructor,
                "Units": units
            })

        print(f"Scraped {len(rows)} rows for {name}")
        time.sleep(1)

    df = pd.DataFrame(all_data).drop_duplicates()
    datasets_dir = Path("backend/datasets")
    datasets_dir.mkdir(exist_ok=True)
    output = datasets_dir / f"{subject_code}_all_offerings.csv"
    df.to_csv(output, index=False)
    return df


if __name__ == "__main__":
    scrape_ucdavis_offerings("STA")

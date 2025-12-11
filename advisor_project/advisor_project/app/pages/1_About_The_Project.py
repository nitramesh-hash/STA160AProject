import streamlit as st

st.set_page_config(
    page_title="About the Project",
    page_icon="👥",
    layout="wide"
)

st.title("About the Academic Advisor Project")

tab1, tab2, tab3, tab4 = st.tabs(["Purpose", "Approach", "Outcomes", "Team Members"])

with tab1:
    st.header("Project Purpose")
    st.write("""
    Advisor appointments are prone to getting backed up as the need for appointments spikes every registration period.
    UC Davis has around 30,000 undergraduates.
    This volume, combined with a developing and changing class catalog, can lead to an insufficient amount of time with your department advisor, especially if your meeting time is your first look and understanding of what courses are available to you and what they mean for your degree.
    In response to this, we created a website to have a preliminary look at your available courses before meeting with an advisor to have a more efficient meeting. While our website is not intended to be a replacement for an advisor, we hope that it is a helpful resource to ensure preparedness for a discussion with an advisor about your degree status and course map.
    On the other hand, advisors can benefit from a pre-screening resource for students, letting appointments and meetings begin at a more advanced point.
    Our objective is to create a tool that reliably displays what relevant courses are available for a student to take based on their course history, which is provided either by text or through a PDF transcript, in an easily interpretable format.
    We also incorporated an AI chatbot that handles advising questions and a degree tracking system. 
    """)
    st.markdown("---") 
    

with tab2:
    st.header("Project Approach")
    st.markdown("---") 
    st.subheader("Main Data Source: UC Davis General Catalog 🐮")
    

    st.write("""
    The catalog is regularly updated and is not uniformly formatted across departments.
    Our scraper gathers course codes (ex., MAT 021A), titles and units, descriptions, explicit prerequisite requirement text, and updated “Effective From” versions of courses that are replacing outdated versions of courses.
    The catalog was also used to gather the B.S and B.A major requirements for statistics, mathematics, computer science, economics, chemistry, and physics.
    """)

    st.markdown("---") 
    st.subheader("1. Web Scraping and Data Cleaning of Course Catalog 📚")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Auto Web Scraper 🤖")
        st.write("""
        We started with a web scraper that we had to manually specify which page to get data from for each department, then turned it into a more automated version that could find and extract data from department pages on its own.
        - Scraper.py: Initial manual scraper for specific departments
        - autoscraper.py: Automated version that finds department pages on its own (uses BeautifulSoup and Requests libraries)
        """)
        st.write("""
        As the HTML structure is not standardized across departments, the scraper has flexible tag matching, regular expressions, and fallback extraction rules.
        We use a generalized regex for “Prerequisites:” across varying tag structures
        - Course blocks are identified using department-specific <div class=”courseblock”> elements. 
        Each scrape outputs subject-specific CSV files of course data. 
        """)
    with col2:
        st.markdown("#### Data Cleaning Functions 🧹")
        st.write("""
        **cleanCSV.py**:
        - Strips titles of HTML artifacts and leading punctuation
        - Units are parsed into integer values
        - Extracts learning activities, grade mode (P/F, graded), and General Education classification
        """)
        st.write("""
        **postcleancheck.py**:
        - Identifies classes with the term “Effective From” included in their description
        - Creates a timestamp based upon the quarter in the description
        - Keeps the newest valid version and removes outdated versions of courses by updating the CSV files
        """)
    st.markdown("---") 

    st.subheader("2. Transcript Reading 📜")
    st.markdown("#### readTranscript.py")
    st.write("""
    - Uses pypdf library to read UC Davis unofficial transcript PDFs.
    - The transcript is processed to extract course codes, titles, grades, and units completed.
    - The text is split into left and right columns and then stacked on top of each other to maintain the correct order of courses taken.
    - Regular expressions are used to identify course lines and extract relevant information such as:
        - [Year | Quarter | Course | Title | Grade | Units]
    - Output is used for eligibility checking and degree tracking.
    """)
    st.markdown("---")

    st.subheader("3. Degree Requirements Scraping and Parsing 🎓")
    st.write("""
    Major requirements for selected departments (Chemistry, Computer Science, Economics, Mathematics, Physics, Statistics) were scraped from the UC Davis catalog using R.
    - Used xml2 library to parse HTML structure and extract class code for required courses.
    - Extracted degree type, major name, tracks (if applicable), course subjects, and required course codes.
        - General functions to get degree type, major titles, and all the course codes were used for all selected majors.
        - Custom functions were created for each major to handle unique requirement structures.
    Parsed requirements were stored in a dataframe then turned into CSV files for use in degree progress tracking.
    """)
    st.markdown("---")

    st.subheader("4. Integrating Python Backend with Streamlit Frontend 🌐")
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("#### Python Backend 🐍")
        st.write("""
        The backend handles all core logic including:
        - Catalog Scraping
        - Prerequisite Parsing
        - Course-code Normalization
        - The Rule Engine that determines course eligibility
        - Also powers the DeepSeek AI chatbot by extracting course information from user messages, updating the completed-courses memory, and generating responses grounded in the catalog data rather than relying on LLM assumptions.
        """)
        st.write("All backend functions operate as modular components, ensuring consistent behavior whether the user asks the chatbot a question or uses the structured Courses Eligibility Checker")
    with col4:
        st.markdown("#### Streamlit Frontend 👑")
        st.write("""
         Streamlit provides a simple and intuitive interface consisting of three main tabs: a form-based eligibility checker, a conversational chatbot, and a basic degree progress tracker.
        """)
        st.write("""
        User messages and inputs are passed to the backend through Streamlit’s session_state, which maintains conversation history, stores completed courses, and advisor context across multiple turns.
        - Allows the system to combine deterministic prerequisite logic with flexible natural-language interaction for a responsive and reliable advising tool.
        """)
        st.write("The design is modular and scalable, enabling future features such as transcript OCR, multi-major support, or personalized degree planning to be integrated with minimal changes to the UI.")
    st.markdown("---")

    st.subheader("5. Fine-tuning the AI Chatbot and UI of the frontend 🤖")
    st.write("""
    - Fine tuned the AI chatbot to better understand and respond to student inquiries regarding course recommendations, prerequisites, and degree requirements.
    - Improved the user interface of the Streamlit frontend to enhance user experience, making it more intuitive and visually appealing.
    """)

    st.markdown("---")
    st.subheader("6. AWS Deployment ☁️")
    st.write("""
    - Deployed the Streamlit application on AWS using EC2 instances to ensure scalability and reliability
    """)
    st.markdown("---")
    

with tab3:
    st.header("Project Outcomes") 

    st.subheader("Current Features ✅")
    col6, col7, col8 = st.columns(3)
    with col6:
        st.markdown("#### Course Eligibility Checker")
        st.write("""
        - Upload your UC Davis transcript (PDF) or manually enter completed courses.
        - Select desired course code to check eligibility based on prerequisites.
        """)
    with col7:
        st.markdown("#### AI Chatbot Advisor")
        st.write("""
        - Conversational interface to ask course and degree-related questions.
        - Provides course recommendations based on completed courses.
        - Can recommend courses based on interests.
        """)
    with col8:
        st.markdown("#### Degree Progress Tracker")
        st.write("""
        - Visualize completed and remaining requirements in tables based on completed courses.
        - Supports multiple majors (Statistics, Mathematics, Computer Science, Economics, Chemistry, Physics).
        - **Note:** This is a basic version and cannot distinguish between "OR" requirements or "Choose X out of Y" requirements yet.
        """)
    st.markdown("---")

    st.header("Future Improvements")
    st.write("""
    - Expand major requirement scraping to include more departments by using a more generalized scraping approach.
        - Use a json format to store major requirements for easier parsing, updating, and usability in components.
        - Provides a more accurate degree tracking system.
    - Improve the AI chatbot's ability to handle complex advising questions.
    - Enhance the course eligibility checker to account for co-requisites and more nuanced prerequisite structures.
    - Optimize the web scraper to handle changes in the UC Davis catalog structure more robustly.
    """)
    st.markdown("---")
    
    st.header("Project Reflections")
    st.subheader("Challenges Faced")
    st.write("""
    - Extracting and cleaning data from the UC Davis course catalog due to unstandardized formats.
        - Examples: Nested OR conditions, minimum grade requirements (“C- or better”), series-based prerequisites (“one of MAT 21A or MAT 21AH”), or prerequisite chains involving multiple departments
        - Single cleaning method was not sufficient for all departments.
        - **Fallback:** Narrowed our scope and focus on specific course codes where we could ensure accurate parsing and consistent data quality
    - Handling the variability in the UC Davis catalog's HTML structure during major requirement web scraping.
        - Limited scope to a few majors and build custom parsers for each.
    - Ensuring the AI chatbot provides accurate and relevant responses without hallucinating information.
    - Ensuring the Streamlit frontend runs efficiently without taking too long to load.
    """)
    st.markdown("---")

    st.subheader("Lessons Learned")
    st.write("""
    - The process of our project highlight the importance of modular design, data validation, and rigorous testing methods
    - By creating our system in modular layers, split into scrapers, cleaning, parsing, rule engine, etc., we were able to modify individual components without breaking the entire pipeline.
    - Adding data validation steps and post-cleaning correction scripts improved system reliability.
    """)
    st.write("""
    In an ideal world, these mistakes would not be so costly, but in practice, even well-maintained academic catalogs can contain irregularities. This project reinforced that real-world data rarely fit idealized assumptions and require tailored solutions, cleaning, and interpretation. 
    """)
    st.markdown("---")

    st.header("Tools and Acknowledgements")
    st.write("""
    - DeepSeek API: AI chatbot framework that allows integration of custom knowledge bases with large language models.
    - Streamlit: Frontend framework for building interactive web applications in Python.
    - BeautifulSoup and Requests: Libraries used for web scraping the UC Davis course catalog.
    - Pandas: Data manipulation and analysis library used extensively in data cleaning and processing.
    - pypdf: Library used for reading and extracting text from PDF transcripts.
    - AWS EC2: Cloud platform used for deploying the Streamlit application.
    - ChatGPT: Helped crush bugs and unexpected errors in code.
    """)
    st.write("""
    We would like to acknowledge the support and guidance of our course instructor, Lingfei Cui, throughout this project.
    """)
    st.markdown("---")
    
with tab4:
    st.header("Team Members")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div style="border:1px solid #ccc; padding:15px; border-radius:10px;">
            <h4 style="text-align:center;">Bimi Amao</h4>
            <p style="text-align:center;">4th Year Statistics B.S Major, Statistical Data Science Track</p>
            <p style="text-align:center;">Minor in Computer Science</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="border:1px solid #ccc; padding:15px; border-radius:10px;">
            <h4 style="text-align:center;">Nitin Ramesh</h4>
            <p style="text-align:center;">3rd Year Data Science Major</p>
            <p style="text-align:center;">Minor in Computational Biology and Theatre and Dance</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="border:1px solid #ccc; padding:15px; border-radius:10px;">
            <h4 style="text-align:center;">Vivian Wong</h4>
            <p style="text-align:center;">4th year Statistics B.S Major, Machine Learning Track</p>
            <p style="text-align:center;">Minor in Japanese</p>
        </div>
        """, unsafe_allow_html=True)


    st.write("")
    st.write("")

    s, col4, col5, ss = st.columns([1, 3, 3, 1])

    with col4:
        st.markdown("""
        <div style="border:1px solid #ccc; padding:15px; border-radius:10px;">
            <h4 style="text-align:center;">Ian Dang</h4>
            <p style="text-align:center;">4th Year Statistical Data Science Major</p>
            <p style="text-align:center;"></p>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown("""
        <div style="border:1px solid #ccc; padding:15px; border-radius:10px;">
            <h4 style="text-align:center;">Tyler Le</h4>
            <p style="text-align:center;">5th Year Statistics B.S Major, Data Science Track</p>
            <p style="text-align:center;">(Additional Notes)</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("Visit our GitHub Repository!")
    st.link_button(
    "🔗 View Project on GitHub",
    "https://github.com/nitramesh-hash/STA160AProject"
    )
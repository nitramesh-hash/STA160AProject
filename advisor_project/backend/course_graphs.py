import re
import matplotlib.pyplot as plt
import networkx as nx
import streamlit as st
import matplotlib.patches as mpatches
import matplotlib.lines as mlines

# FIXED — import from the correct module
from backend.a_backend import extract_courses_codes


def load_advisor_backend():
    from backend.a_backend import load_or_scrape_catalog
    return load_or_scrape_catalog


@st.cache_data
def load_undergrad_catalog(subject_code):
    load_or_scrape_catalog = load_advisor_backend()
    df = load_or_scrape_catalog(subject_code)

    # Filter only this subject code
    df = df[df["Course Code"].str.startswith(subject_code.upper())]

    # Keep only undergrad courses (course numbers 1–199)
    def is_undergrad(code):
        m = re.search(r"(\d+)", code)
        return m and 1 <= int(m.group(1)) <= 199

    return df[df["Course Code"].apply(is_undergrad)]


def plot_course_dependency_graph(subject_code, completed_courses):

    subject_code = subject_code.upper()
    completed_courses = [re.sub(r"\s+", "", c.upper()) for c in completed_courses]

    df = load_undergrad_catalog(subject_code)
    G = nx.DiGraph()

    # Build graph
    for _, row in df.iterrows():
        course = re.sub(r"\s+", "", row["Course Code"].upper())

        # FIXED — extract prereqs using correct function
        prereqs = [
            re.sub(r"\s+", "", p.upper())
            for p in extract_courses_codes(str(row.get("Prerequisites", "")))
            if p.startswith(subject_code.upper())
        ]

        for p in prereqs:
            G.add_edge(p, course)

    # -------- Depth-limited expansion --------
    def expand(node, max_depth=3):
        if node not in G:
            return set()
        visited = {node}
        frontier = {node}

        for _ in range(max_depth):
            new = set()
            for n in frontier:
                new |= set(G.predecessors(n))
                new |= set(G.successors(n))
            new -= visited
            if not new:
                break
            visited |= new
            frontier = new
        return visited

    related = set()
    for c in completed_courses:
        related |= expand(c)

    G = G.subgraph(related).copy()

    # Compute eligibility
    eligible, blocked = [], []
    for course in G.nodes:
        prereqs = list(G.predecessors(course))
        unmet = [p for p in prereqs if p not in completed_courses]

        if course in completed_courses:
            continue
        if not prereqs or not unmet:
            eligible.append(course)
        else:
            blocked.append(course)

    node_colors = [
        "lightgreen" if n in completed_courses
        else "khaki" if n in eligible
        else "lightcoral"
        for n in G.nodes
    ]

    edge_colors = [
        "mediumseagreen" if u in completed_courses else "lightgray"
        for u, v in G.edges()
    ]

    # -------- FAST LAYOUT --------
    pos = nx.spring_layout(G, k=1.5, iterations=80)

    fig, ax = plt.subplots(figsize=(16, 10))
    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color=node_colors,
        edge_color=edge_colors,
        node_size=1500,
        font_size=9,
        arrowsize=12,
        width=1.2,
        ax=ax
    )

    plt.title(f"{subject_code} Undergraduate Prerequisite Paths", fontsize=18)

    # Legend
    completed_patch = mpatches.Patch(color="lightgreen", label="Completed Courses")
    eligible_patch = mpatches.Patch(color="khaki", label="Eligible Courses")
    unavailable_patch = mpatches.Patch(color="lightcoral", label="Unavailable Courses")
    completed_edge = mlines.Line2D([], [], color="mediumseagreen", label="Prereq Edge from Completed")
    normal_edge = mlines.Line2D([], [], color="lightgray", label="Prereq Edge")

    ax.legend(
        handles=[completed_patch, eligible_patch, unavailable_patch, completed_edge, normal_edge],
        title="Legend",
        loc="upper left",
        bbox_to_anchor=(0.01, 1.15),
        frameon=True,
        framealpha=0.9
    )

    st.pyplot(fig)

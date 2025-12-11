from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import networkx as nx
import os

ROOT = Path(__file__).resolve().parents[1]
DEGREE_DIR = ROOT / "degree_requirements"

DATASET_DIR = Path(__file__).resolve().parent / "datasets"

def load_prereqs():
    """
    Load the unified prereqs.json (B1 flat format):
    {
        "ECS 036C": { "and": ["ECS 020"], "or": [["ECS 040", "ECS 036B"]] },
        ...
    }
    """
    path = DATASET_DIR / "prereqs.json"
    with open(path, "r") as f:
        return json.load(f)


def build_graph_from_prereqs(pr):
    G = nx.DiGraph()
    for course, rules in pr.items():
        course_norm = course  # already normalized (no spaces) in PREREQS keys
        G.add_node(course_norm)

        # AND prereqs
        for p in rules["and"]:
            G.add_edge(p.replace(" ", "").upper(), course_norm)

        # OR prereqs (every option unlocks the course)
        for group in rules["or"]:
            for p in group:
                G.add_edge(p.replace(" ", "").upper(), course_norm)

    return G


# 🚨 NEW: normalize keys when loading
_raw_prereqs = load_prereqs()

PREREQS = {}

for code, rules in _raw_prereqs.items():
    norm_code = code.replace(" ", "").upper()

    # Normalize AND prereqs
    and_list = [
        p.replace(" ", "").upper()
        for p in rules.get("and", [])
    ]

    # Normalize OR prereqs (list of lists)
    or_list = []
    for group in rules.get("or", []):
        or_list.append([
            p.replace(" ", "").upper()
            for p in group
        ])

    PREREQS[norm_code] = {
        "and": and_list,
        "or": or_list
    }

PREREQ_GRAPH = build_graph_from_prereqs(PREREQS)



# ============================================================
# BACKEND PREREQUISITE LOGIC (PURE LOGIC — NO TEXT)
# ============================================================
def missing_prereqs_backend(course: str, completed: list[str]) -> list[str]:
    c = course.replace(" ", "").upper()
    completed_norm = {x.replace(" ", "").upper() for x in completed}

    if c not in PREREQS:
        return []

    rules = PREREQS[c]
    missing = []

    # AND prereqs
    for req in rules["and"]:
        if req.replace(" ", "").upper() not in completed_norm:
            missing.append(req)

    # OR groups
    for group in rules["or"]:
        group_norm = [g.replace(" ", "").upper() for g in group]
        if not any(g in completed_norm for g in group_norm):
            missing.append("(" + " or ".join(group) + ")")

    return missing


def can_take_course_backend(course: str, completed: list[str]) -> bool:
    c = course.replace(" ", "").upper()
    completed_norm = {x.replace(" ", "").upper() for x in completed}

    if c not in PREREQS:
        return True   # no prereq data → assume ok

    rules = PREREQS[c]

    # AND prereqs
    for req in rules["and"]:
        if req.replace(" ", "").upper() not in completed_norm:
            return False

    # OR groups
    for group in rules["or"]:
        if not any(g.replace(" ", "").upper() in completed_norm for g in group):
            return False

    return True


def find_eligible_courses_backend(completed: List[str]) -> List[str]:
    """Return all courses for which prereqs are satisfied."""
    completed_norm = {c.replace(" ", "").upper() for c in completed}
    return [
        course
        for course in PREREQ_GRAPH.nodes
        if course not in completed_norm and can_take_course_backend(course, completed)
    ]


def count_future_unlocks(course: str, G=PREREQ_GRAPH):
    """Return number of courses this course unlocks (direct successors)."""
    return len(list(G.successors(course)))

def get_course_unlocks(course: str) -> List[str]:
    """
    Return a list of courses that this course unlocks
    (direct successors in the prereq graph).
    """
    course_norm = course.replace(" ", "").upper()
    if course_norm not in PREREQ_GRAPH.nodes:
        return []

    return sorted(list(PREREQ_GRAPH.successors(course_norm)))

def get_unlock_chain(course: str) -> List[str]:
    """
    Return ALL courses unlocked by this course, including indirect unlocks.
    Uses DFS on the master prereq graph.
    """
    course_norm = course.replace(" ", "").upper()

    if course_norm not in PREREQ_GRAPH.nodes:
        return []

    visited = set()
    stack = [course_norm]

    while stack:
        node = stack.pop()
        for successor in PREREQ_GRAPH.successors(node):
            if successor not in visited:
                visited.add(successor)
                stack.append(successor)

    # Remove the starting course itself if present
    visited.discard(course_norm)

    return sorted(list(visited))

def get_reverse_prereq_chain(course: str) -> List[str]:
    """
    Return ALL prerequisite courses required for this course,
    including indirect prerequisites (reverse DFS).
    """
    course_norm = course.replace(" ", "").upper()

    if course_norm not in PREREQ_GRAPH.nodes:
        return []

    visited = set()
    stack = [course_norm]

    while stack:
        node = stack.pop()
        for prereq in PREREQ_GRAPH.predecessors(node):
            if prereq not in visited:
                visited.add(prereq)
                stack.append(prereq)

    # Remove the starting course
    visited.discard(course_norm)

    return sorted(list(visited))



def _normalize_course(code: str) -> str:
    return code.replace(" ", "").upper()

def _normalize_course_list(courses: List[str]) -> List[str]:
    return [_normalize_course(c) for c in courses]


def load_major_json(filename: str) -> Dict[str, Any]:
    
    path = DEGREE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Requirement file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_available_degrees() -> List[str]:
    
    return [p.name for p in DEGREE_DIR.glob("*.json")]



def merge_requirement_blocks(blockA: Dict[str, Any], blockB: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two requirement blocks from two different majors.
    Handles:
        - requirements lists
        - choose-N blocks
        - advisor-required blocks
    """

    merged = blockA.copy()

    # -------------------------------------------------------
    # CASE 1: Both blocks have "requirements" (PLURAL)
    # -------------------------------------------------------
    if "requirements" in blockA and "requirements" in blockB:
        req_map = {req["label"]: req for req in blockA["requirements"]}

        for req in blockB.get("requirements", []):  # <== FIXED
            label = req["label"]

            if label in req_map:
                # Merge course lists if both blocks have same label
                if "courses" in req_map[label] and "courses" in req:
                    req_map[label]["courses"] = sorted(
                        list(set(req_map[label]["courses"] + req["courses"]))
                    )
            else:
                req_map[label] = req

        merged["requirements"] = list(req_map.values())
        return merged

    # -------------------------------------------------------
    # CASE 2: Both choose-N blocks
    # -------------------------------------------------------
    if blockA.get("type") == "choose" and blockB.get("type") == "choose":
        merged["courses"] = sorted(list(set(blockA.get("courses", []) + blockB.get("courses", []))))
        merged["choose"] = max(blockA.get("choose", 0), blockB.get("choose", 0))
        return merged

    # -------------------------------------------------------
    # CASE 3: Both advisor_required blocks
    # -------------------------------------------------------
    if blockA.get("type") == "advisor_required" and blockB.get("type") == "advisor_required":
        examplesA = set(blockA.get("eligible_examples", []))
        examplesB = set(blockB.get("eligible_examples", []))
        merged["eligible_examples"] = sorted(list(examplesA.union(examplesB)))
        return merged

    # -------------------------------------------------------
    # DEFAULT CASE:
    # Blocks do not match; keep both
    # -------------------------------------------------------
    return {"blockA": blockA, "blockB": blockB}






def merge_majors(major_files: List[str]) -> Dict[str, Any]:
    

    merged = {
        "degree": "Combined Majors",
        "tracks": [],
        "catalog_years": [],
        "blocks": {}
    }

    for filename in major_files:
        major = load_major_json(filename)

        merged["tracks"].append(major.get("track"))
        merged["catalog_years"].append(major.get("catalog_year"))

        for block_key, block_data in major["blocks"].items():
            if block_key not in merged["blocks"]:
                merged["blocks"][block_key] = block_data
            else:
                merged["blocks"][block_key] = merge_requirement_blocks(
                    merged["blocks"][block_key],
                    block_data
                )

    return merged




def evaluate_multi_major_progress(
        completed_courses: List[str],
        major_files: List[str]
) -> Dict[str, Any]:

    merged_reqs = merge_majors(major_files)

    return evaluate_major_progress(
        completed_courses=completed_courses,
        preloaded_requirements=merged_reqs
    )




def evaluate_major_progress(
    completed_courses: List[str],
    major_code: str = None,
    catalog_year: str = None,
    preloaded_requirements: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    

    if preloaded_requirements:
        reqs = preloaded_requirements
    else:
        fname = f"{major_code}_{catalog_year.replace('-', '_')}.json"
        reqs = load_major_json(fname)


    blocks = reqs.get("blocks", {})
    completed_norm = {_normalize_course(c) for c in completed_courses if c.strip()}

    audit = {
        "degree": reqs.get("degree"),
        "track": reqs.get("track"),
        "catalog_year": reqs.get("catalog_year"),
        "completed_blocks": {},
        "missing_blocks": {},
        "recommendations": [],
        "summary": {}
    }

    total_blocks_count = 0
    completed_blocks_count = 0

    for block_key, block_data in blocks.items():
        block_name = block_data.get("description", block_key.replace("_", " ").title())
        total_blocks_count += 1

        comp, miss, rec = _evaluate_generic_block(
            block_name=block_name,
            block_key=block_key,
            block=block_data,
            completed_norm=completed_norm,
        )

        if comp: audit["completed_blocks"][block_name] = comp
        if miss: audit["missing_blocks"][block_name] = miss
        if comp and not miss: completed_blocks_count += 1
        audit["recommendations"].extend(rec)

    ratio = completed_blocks_count / total_blocks_count if total_blocks_count else 0

    audit["summary"] = {
        "block_completion_ratio": ratio,
        "total_blocks": total_blocks_count,
        "completed_blocks": completed_blocks_count,
    }

    return audit



def _evaluate_generic_block(block_name, block_key, block, completed_norm):
    if "requirements" in block:
        return _evaluate_requirements_block(block_name, block, completed_norm)
    elif block.get("type") == "choose":
        return _evaluate_choose_block(block_name, block, completed_norm)
    elif block.get("type") == "advisor_required":
        return _evaluate_cluster_block(block_name, block, completed_norm)
    else:
        return {}, {"info": "Unknown block structure"}, [
            f"[{block_name}] Unrecognized requirement block. Confirm with advisor."
        ]



def _evaluate_requirements_block(block_name, block, completed_norm):
    completed_info = {}
    missing_info = {}
    recommendations = []

    for req in block.get("requirements", []):
        label = req.get("label", "Unnamed requirement")
        rtype = req.get("type", "all")
        courses = req.get("courses", [])
        norm = _normalize_course_list(courses)

        if rtype == "advisor_input":
            missing_info[label] = {"type": "advisor_input", "description": req.get("description", "")}
            recommendations.append(f"[{block_name}] Meet with advisor about: {label}.")
            continue

        if rtype == "all":
            missing = [orig for orig, n in zip(courses, norm) if n not in completed_norm]
            if missing:
                missing_info[label] = missing
                for m in missing:
                    recommendations.append(f"[{block_name}] You still need {m}.")
            else:
                completed_info[label] = courses

        elif rtype == "one_of":
            taken = [orig for orig, n in zip(courses, norm) if n in completed_norm]
            if taken:
                completed_info[label] = taken
            else:
                missing_info[label] = courses
                recommendations.append(
                    f"[{block_name}] Complete ONE of: {', '.join(courses)}."
                )

        elif rtype == "choose":
            comp, miss, rec = _evaluate_choose_requirement(block_name, label, req, completed_norm)
            if comp: completed_info[label] = comp
            if miss: missing_info[label] = miss
            recommendations.extend(rec)

    return completed_info, missing_info, recommendations



def _evaluate_choose_requirement(block_name, label, req, completed_norm):
    choose_n = req.get("choose", 0)
    courses = req.get("courses", [])
    norm = _normalize_course_list(courses)

    taken = [o for o, n in zip(courses, norm) if n in completed_norm]
    recommendations = []

    if len(taken) >= choose_n:
        return {"chosen_courses": taken}, None, recommendations
    else:
        need = choose_n - len(taken)
        missing = {
            "choose": choose_n,
            "already_have": taken,
            "still_need_count": need,
            "available_options": courses,
        }
        recommendations.append(
            f"[{block_name}] Need {need} more course(s) from: {', '.join(courses)}."
        )
        return None, missing, recommendations



def _evaluate_choose_block(block_name, block, completed_norm):
    completed_info = {}
    missing_info = {}
    recommendations = []

    choose_n = block.get("choose", 0)
    courses = block.get("courses", [])
    norm = _normalize_course_list(courses)

    taken = [o for o, n in zip(courses, norm) if n in completed_norm]

    if len(taken) >= choose_n:
        completed_info["chosen_courses"] = taken
    else:
        need = choose_n - len(taken)
        missing_info["needed"] = {
            "choose": choose_n,
            "already_have": taken,
            "still_need_count": need,
            "available_options": courses
        }
        recommendations.append(
            f"[{block_name}] Need {need} more upper-division course(s)."
        )

    return completed_info, missing_info, recommendations



def _evaluate_cluster_block(block_name, block, completed_norm):
    examples = block.get("eligible_examples", [])
    norm = _normalize_course_list(examples)

    taken = [orig for orig, n in zip(examples, norm) if n in completed_norm]

    assumed_required = 4  # typical cluster requirement
    still_need = max(0, assumed_required - len(taken))

    completed_info = {"recognized_cluster_courses": taken}
    missing_info = {
        "approx_cluster_status": {
            "assumed_required_count": assumed_required,
            "recognized_completed": taken,
            "approx_still_needed": still_need,
        }
    }

    recommendations = [
        f"[{block_name}] You have {len(taken)} cluster courses. Likely need {still_need} more. Confirm with advisor."
    ]

    return completed_info, missing_info, recommendations

                    
import streamlit as st
from collections import deque
from itertools import combinations

#python -m streamlit run main.py

# AI Course Planner + Graduation Path Finder
# Halfway milestone: sample catalog, prerequisite graph, BFS planner,
# bottleneck ranking, and a basic what-if delay analysis.
# UCS, A*, availability, transfer equivalency, and richer UI are future work.

COURSES = {
    "CMPSC 131": {"name":"Programming and Computation I", "credits":3, "prerequisites":[], "difficulty":2},
    "CMPSC 132": {"name":"Programming and Computation II", "credits":3, "prerequisites":["CMPSC 131"], "difficulty":2},
    "CMPSC 360": {"name":"Discrete Mathematics", "credits":3, "prerequisites":["CMPSC 132"], "difficulty":3},
    "CMPSC 465": {"name":"Algorithms", "credits":3, "prerequisites":["CMPSC 360"], "difficulty":3},
    "CMPSC 473": {"name":"Operating Systems", "credits":3, "prerequisites":["CMPSC 360"], "difficulty":3},
    "MATH 140": {"name":"Calculus I", "credits":4, "prerequisites":[], "difficulty":3},
    "MATH 141": {"name":"Calculus II", "credits":4, "prerequisites":["MATH 140"], "difficulty":3},
    "STAT 200": {"name":"Elementary Statistics", "credits":3, "prerequisites":[], "difficulty":2},
    "ENGL 15": {"name":"Rhetoric and Composition", "credits":3, "prerequisites":[], "difficulty":1},
    "CMPSC 311": {"name":"Systems Programming", "credits":3, "prerequisites":["CMPSC 132"], "difficulty":3},
}
DEFAULT_REQUIRED = list(COURSES.keys())

def prerequisites_met(course_id, completed):
    return all(p in completed for p in COURSES[course_id]["prerequisites"])

def eligible_courses(completed, required):
    return [c for c in required if c not in completed and prerequisites_met(c, completed)]

def semester_combinations(eligible, max_credits):
    """Generate nonempty sets of currently eligible courses within credit limit."""
    choices = []
    # Keep combinations manageable for this small sample dataset.
    for size in range(1, min(len(eligible), 5) + 1):
        for combo in combinations(eligible, size):
            credits = sum(COURSES[c]["credits"] for c in combo)
            if credits <= max_credits:
                choices.append(combo)
    # Favor fuller semesters to keep BFS practical, but each is still a valid expansion.
    choices.sort(key=lambda combo: sum(COURSES[c]["credits"] for c in combo), reverse=True)
    return choices[:35]

def bfs_plan(completed_start, required, max_credits, max_states=12000):
    """BFS over semester-level states; returns a valid schedule or None."""
    start = frozenset(completed_start)
    queue = deque([(start, [])])
    visited = {start}
    explored = 0

    while queue and explored < max_states:
        completed, schedule = queue.popleft()
        explored += 1
        if set(required).issubset(completed):
            return schedule, explored

        eligible = eligible_courses(completed, required)
        if not eligible:
            continue

        for combo in semester_combinations(eligible, max_credits):
            next_completed = frozenset(set(completed).union(combo))
            if next_completed in visited:
                continue
            visited.add(next_completed)
            queue.append((next_completed, schedule + [list(combo)]))

    return None, explored

def bottleneck_scores(required):
    """Count how many required courses depend directly/indirectly on each course."""
    scores = {}
    for course in required:
        descendants = set()
        frontier = [course]
        while frontier:
            current = frontier.pop()
            for candidate in required:
                if current in COURSES[candidate]["prerequisites"] and candidate not in descendants:
                    descendants.add(candidate)
                    frontier.append(candidate)
        scores[course] = len(descendants)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def what_if_delay(course_to_delay, completed, required):
    """Simple impact analysis: remove a course from current completed set (if any),
    then report its downstream prerequisite courses. This is an estimate, not a
    guaranteed graduation-date prediction."""
    affected = []
    frontier = [course_to_delay]
    seen = {course_to_delay}
    while frontier:
        current = frontier.pop()
        for candidate in required:
            if current in COURSES[candidate]["prerequisites"] and candidate not in seen:
                seen.add(candidate)
                affected.append(candidate)
                frontier.append(candidate)
    return affected

st.set_page_config(page_title="AI Course Planner", page_icon="🎓", layout="wide")
st.title("🎓 AI Course Planner + Graduation Path Finder")
st.caption("Halfway project prototype — sample catalog and BFS semester planner")

with st.sidebar:
    st.header("Student planning inputs")
    completed = st.multiselect("Courses already completed", options=list(COURSES.keys()))
    max_credits = st.slider("Maximum credits per semester", min_value=6, max_value=18, value=15, step=1)
    required = st.multiselect("Courses required in this sample plan", options=DEFAULT_REQUIRED, default=DEFAULT_REQUIRED)

tab1, tab2, tab3, tab4 = st.tabs(["Semester Planner", "Course Catalog", "Bottleneck Finder", "What-if Analysis"])

with tab1:
    st.subheader("Generate a prerequisite-valid semester plan")
    if st.button("Generate plan with BFS", type="primary"):
        if not required:
            st.warning("Select at least one course to plan.")
        elif not set(completed).intersection(required) and not required:
            st.warning("Choose required courses.")
        else:
            plan, explored = bfs_plan(completed, required, max_credits)
            st.session_state["bfs_plan"] = plan
            st.session_state["explored"] = explored
    if "bfs_plan" in st.session_state:
        plan = st.session_state["bfs_plan"]
        st.write(f"BFS states explored: **{st.session_state.get('explored', 0)}**")
        if plan is None:
            st.error("No plan found within the search limit. Try a higher credit limit or a smaller course set.")
        elif len(plan) == 0:
            st.success("All selected required courses are already completed.")
        else:
            st.success(f"Plan generated: {len(plan)} semester(s) in this sample.")
            for idx, semester in enumerate(plan, start=1):
                credits = sum(COURSES[c]["credits"] for c in semester)
                with st.container(border=True):
                    st.markdown(f"### Semester {idx} · {credits} credits")
                    for course in semester:
                        st.write(f"**{course}** — {COURSES[course]['name']} ({COURSES[course]['credits']} credits)")
                        prereqs = COURSES[course]["prerequisites"]
                        st.caption("Prerequisites: " + (", ".join(prereqs) if prereqs else "None"))

with tab2:
    st.subheader("Sample course catalog")
    rows = []
    for cid, info in COURSES.items():
        rows.append({"Course ID":cid, "Course name":info["name"], "Credits":info["credits"],
                     "Prerequisites":", ".join(info["prerequisites"]) or "None",
                     "Difficulty (1–3)":info["difficulty"]})
    st.dataframe(rows, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Courses that unlock other courses")
    st.write("Higher scores mean more required courses depend directly or indirectly on that course.")
    scores = bottleneck_scores(required)
    st.dataframe([{"Course":c, "Downstream required courses":score} for c,score in scores],
                 use_container_width=True, hide_index=True)
    if scores:
        top = scores[0]
        st.info(f"Priority candidate: **{top[0]}** — it unlocks {top[1]} course(s) in this selected set.")

with tab4:
    st.subheader("What if a course is postponed or failed?")
    target = st.selectbox("Course to delay", options=required or DEFAULT_REQUIRED)
    affected = what_if_delay(target, completed, required or DEFAULT_REQUIRED)
    st.write(f"**Courses downstream of {target}:**")
    if affected:
        st.write(", ".join(affected))
        st.warning("These courses may need to move to a later semester if the prerequisite is delayed.")
    else:
        st.success("No downstream prerequisite courses were found in the selected sample.")
    st.caption("This is a prerequisite-impact estimate. A precise graduation-date prediction requires semester offerings and university-specific rules.")

st.divider()
st.markdown("**Development status:** BFS planner, sample catalog, bottleneck finder, and basic what-if analysis are implemented. UCS/A*, course offering calendar, transfer-credit matching, and comprehensive testing are planned next.")

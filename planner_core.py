import json
from pathlib import Path
from collections import deque


# Load the course catalog
def load_catalog(path=None):
    if path is None:
        path = Path(__file__).with_name("courses.json")

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    catalog = {course["code"]: course for course in data}

    if len(catalog) != len(data):
        raise ValueError("Duplicate course codes found in courses.json.")

    # Check that every prerequisite exists in the catalog
    for code, course in catalog.items():
        for prerequisite in course.get("prerequisites", []):
            if prerequisite not in catalog:
                raise ValueError(
                    f"{code} has an unknown prerequisite: {prerequisite}"
                )

    return catalog


# Validate course codes selected by the student
def validate_courses(catalog, courses):
    unknown = set(courses) - set(catalog.keys())

    if unknown:
        raise ValueError(
            "Unknown course codes: " + ", ".join(sorted(unknown))
        )


# Find all prerequisites needed for the selected courses
def get_required_courses(catalog, required, completed):
    needed = set()
    stack = list(required)

    while stack:
        code = stack.pop()

        if code in completed or code in needed:
            continue

        needed.add(code)

        for prerequisite in catalog[code]["prerequisites"]:
            if prerequisite not in completed:
                stack.append(prerequisite)

    return needed


# Count how many later courses each course unlocks using BFS
def count_unlocked_courses(catalog):
    reverse_graph = {
        code: [] for code in catalog
    }

    # Build a graph showing which courses depend on each course
    for code, course in catalog.items():
        for prerequisite in course["prerequisites"]:
            reverse_graph[prerequisite].append(code)

    unlock_counts = {}

    for start in catalog:
        queue = deque(reverse_graph[start])
        visited = set()

        # BFS traversal
        while queue:
            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)

            for dependent in reverse_graph[current]:
                if dependent not in visited:
                    queue.append(dependent)

        unlock_counts[start] = len(visited)

    return unlock_counts


# Rank courses by how many future courses they unlock
def get_priority_rows(catalog):
    unlock_counts = count_unlocked_courses(catalog)

    rows = []

    for code, course in catalog.items():
        rows.append({
            "Course": code,
            "Name": course["name"],
            "Credits": course["credits"],
            "Prerequisites": ", ".join(
                course["prerequisites"]
            ) or "None",
            "Courses Unlocked": unlock_counts[code]
        })

    return sorted(
        rows,
        key=lambda row: row["Courses Unlocked"],
        reverse=True
    )


# Move to the next academic semester
def next_term(term, year, include_summer):
    terms = (
        ["Fall", "Spring", "Summer"]
        if include_summer
        else ["Fall", "Spring"]
    )

    if term not in terms:
        raise ValueError("Invalid starting semester.")

    index = terms.index(term)

    if index == len(terms) - 1:
        return terms[0], year + 1

    return terms[index + 1], year


# Generate a semester-by-semester plan
def build_plan(
    catalog,
    completed,
    required,
    max_credits=15,
    start_term="Fall",
    start_year=2027,
    include_summer=False,
    delay_course=None,
    delay_semesters=0
):
    completed = set(completed)
    required = set(required)

    validate_courses(catalog, completed)
    validate_courses(catalog, required)

    if max_credits <= 0:
        raise ValueError("Maximum credits must be greater than zero.")

    if delay_semesters < 0:
        raise ValueError("Delay cannot be negative.")

    if delay_course and delay_course not in required:
        raise ValueError(
            "The delayed course must be included in your required courses."
        )

    needed = get_required_courses(
        catalog,
        required,
        completed
    )

    remaining = set(needed)

    unlock_counts = count_unlocked_courses(catalog)

    schedule = []

    current_term = start_term
    current_year = start_year
    semester_index = 0

    # Continue until all selected courses are scheduled
    while remaining:

        if semester_index >= 30:
            raise ValueError(
                "The plan is too long. Check the prerequisites and course data."
            )

        eligible = []

        # Find courses whose prerequisites have been completed
        for code in remaining:

            prerequisites = set(
                catalog[code]["prerequisites"]
            )

            if not prerequisites.issubset(completed):
                continue

            # Hold a selected course for the what-if analysis
            if (
                code == delay_course
                and semester_index < delay_semesters
            ):
                continue

            eligible.append(code)

        # Prioritize courses that unlock more future courses
        eligible.sort(
            key=lambda code: (
                -unlock_counts[code],
                catalog[code]["credits"],
                code
            )
        )

        semester_courses = []
        semester_credits = 0

        # Add eligible courses without exceeding the credit limit
        for code in eligible:

            credits = catalog[code]["credits"]

            if semester_credits + credits <= max_credits:
                semester_courses.append(code)
                semester_credits += credits

        # If no course can be scheduled, check whether it is
        # because of the intentional delay or a planning problem
        if not semester_courses:

            if (
                delay_course in remaining
                and semester_index < delay_semesters
            ):
                schedule.append({
                    "term": current_term,
                    "year": current_year,
                    "credits": 0,
                    "courses": []
                })

            else:
                raise ValueError(
                    "No courses can be scheduled. Check prerequisites "
                    "or increase the maximum credit limit."
                )

        else:

            course_details = []

            for code in semester_courses:

                course = catalog[code]
                remaining.remove(code)
                completed.add(code)

                if unlock_counts[code] > 0:
                    reason = (
                        f"Taking this course may unlock "
                        f"{unlock_counts[code]} future course(s)."
                    )
                else:
                    reason = "All prerequisites are satisfied."

                course_details.append({
                    "code": code,
                    "name": course["name"],
                    "credits": course["credits"],
                    "reason": reason
                })

            schedule.append({
                "term": current_term,
                "year": current_year,
                "credits": semester_credits,
                "courses": course_details
            })

        semester_index += 1

        current_term, current_year = next_term(
            current_term,
            current_year,
            include_summer
        )

    return schedule


# Compare the original plan with a delayed-course scenario
def compare_delay(
    catalog,
    completed,
    required,
    max_credits,
    start_term,
    start_year,
    include_summer,
    delay_course,
    delay_semesters=1
):
    original_plan = build_plan(
        catalog,
        completed,
        required,
        max_credits,
        start_term,
        start_year,
        include_summer
    )

    delayed_plan = build_plan(
        catalog,
        completed,
        required,
        max_credits,
        start_term,
        start_year,
        include_summer,
        delay_course=delay_course,
        delay_semesters=delay_semesters
    )

    semester_difference = max(
        0,
        len(delayed_plan) - len(original_plan)
    )

    return original_plan, delayed_plan, semester_difference
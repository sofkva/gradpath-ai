import streamlit as st
import pandas as pd

from planner_core import (
    load_catalog,
    build_plan,
    get_priority_rows,
    compare_delay
)


# Page setup
st.set_page_config(
    page_title="Course Planner",
    page_icon="📚",
    layout="wide"
)

st.title("Course Planner")

st.write(
    "Plan your upcoming semesters, check course prerequisites, "
    "and understand how delaying a course could affect your schedule."
)

st.caption(
    "This version uses sample course information. "
    "Verify requirements with your official academic department."
)


# Load catalog
try:
    catalog = load_catalog()
except Exception as error:
    st.error(f"Could not load course catalog: {error}")
    st.stop()


course_codes = list(catalog.keys())


# Sidebar: student information
st.sidebar.header("Your Academic Information")

default_completed = [
    "CMPSC 131",
    "MATH 140",
    "ENGL 15"
]

default_completed = [
    code for code in default_completed
    if code in catalog
]

completed = st.sidebar.multiselect(
    "Courses you have completed",
    options=course_codes,
    default=default_completed
)

required_options = [
    code for code in course_codes
    if code not in completed
]

default_required = [
    "CMPSC 132",
    "CMPSC 221",
    "CMPSC 311",
    "CMPSC 360",
    "CMPSC 461",
    "CMPSC 465",
    "MATH 141",
    "STAT 200"
]

default_required = [
    code for code in default_required
    if code in required_options
]

required = st.sidebar.multiselect(
    "Courses you still need",
    options=required_options,
    default=default_required
)

max_credits = st.sidebar.slider(
    "Maximum credits per semester",
    min_value=6,
    max_value=21,
    value=15
)

include_summer = st.sidebar.checkbox(
    "Include summer semesters",
    value=False
)

term_options = (
    ["Fall", "Spring", "Summer"]
    if include_summer
    else ["Fall", "Spring"]
)

start_term = st.sidebar.selectbox(
    "Starting semester",
    options=term_options
)

start_year = st.sidebar.number_input(
    "Starting year",
    min_value=2026,
    max_value=2100,
    value=2027
)


# Generate the initial plan
try:
    plan = build_plan(
        catalog=catalog,
        completed=completed,
        required=required,
        max_credits=max_credits,
        start_term=start_term,
        start_year=int(start_year),
        include_summer=include_summer
    )

    plan_error = None

except ValueError as error:
    plan = []
    plan_error = str(error)


# Main application tabs
plan_tab, catalog_tab, priority_tab, whatif_tab = st.tabs([
    "My Semester Plan",
    "Course Catalog",
    "Course Priorities",
    "What If I Delay a Course?"
])


# -------------------------------------------------
# TAB 1: SEMESTER PLAN
# -------------------------------------------------

with plan_tab:

    st.header("Your Suggested Semester Plan")

    if plan_error:

        st.error(plan_error)

    elif not plan:

        st.success(
            "All selected courses have already been completed!"
        )

    else:

        total_courses = sum(
            len(semester["courses"])
            for semester in plan
        )

        total_credits = sum(
            semester["credits"]
            for semester in plan
        )

        graduation_estimate = (
            f"{plan[-1]['term']} {plan[-1]['year']}"
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Courses to Complete",
            total_courses
        )

        col2.metric(
            "Estimated Semesters",
            len(plan)
        )

        col3.metric(
            "Estimated Finish",
            graduation_estimate
        )

        st.divider()

        # Display each semester
        for semester in plan:

            title = (
                f"{semester['term']} {semester['year']} "
                f"— {semester['credits']} credits"
            )

            with st.expander(title, expanded=True):

                if not semester["courses"]:

                    st.info(
                        "No courses scheduled during this semester "
                        "because of the selected delay."
                    )

                for course in semester["courses"]:

                    col1, col2 = st.columns([4, 1])

                    with col1:

                        st.markdown(
                            f"**{course['code']} — {course['name']}**"
                        )

                        st.caption(course["reason"])

                    with col2:

                        st.metric(
                            "Credits",
                            course["credits"]
                        )

        # Export schedule
        export_rows = []

        for semester in plan:

            for course in semester["courses"]:

                export_rows.append({
                    "Semester": (
                        f"{semester['term']} {semester['year']}"
                    ),
                    "Course": course["code"],
                    "Course Name": course["name"],
                    "Credits": course["credits"],
                    "Recommendation Reason": course["reason"]
                })

        if export_rows:

            csv_data = pd.DataFrame(
                export_rows
            ).to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download My Plan",
                data=csv_data,
                file_name="my_course_plan.csv",
                mime="text/csv"
            )


# -------------------------------------------------
# TAB 2: COURSE CATALOG
# -------------------------------------------------

with catalog_tab:

    st.header("Course Catalog")

    search = st.text_input(
        "Search by course code or course name"
    )

    catalog_rows = []

    for code, course in catalog.items():

        catalog_rows.append({
            "Course Code": code,
            "Course Name": course["name"],
            "Credits": course["credits"],
            "Prerequisites": ", ".join(
                course["prerequisites"]
            ) or "None"
        })

    catalog_df = pd.DataFrame(catalog_rows)

    if search:

        filtered_df = catalog_df[
            catalog_df.apply(
                lambda row: search.lower() in
                " ".join(row.astype(str)).lower(),
                axis=1
            )
        ]

    else:

        filtered_df = catalog_df

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Prerequisites must be completed before taking the listed course."
    )


# -------------------------------------------------
# TAB 3: COURSE PRIORITIES
# -------------------------------------------------

with priority_tab:

    st.header("Courses to Consider Taking Early")

    st.write(
        "Some courses are especially important because they "
        "unlock multiple courses later in your academic plan."
    )

    priority_rows = get_priority_rows(catalog)

    priority_df = pd.DataFrame(priority_rows)

    priority_df = priority_df.rename(columns={
        "Course": "Course Code",
        "Name": "Course Name"
    })

    st.dataframe(
        priority_df,
        use_container_width=True,
        hide_index=True
    )

    if priority_rows:

        highest_priority = priority_rows[0]

        st.info(
            f"**Priority suggestion:** "
            f"{highest_priority['Course']} — "
            f"{highest_priority['Name']} unlocks "
            f"{highest_priority['Courses Unlocked']} "
            f"future course(s) in this sample catalog."
        )


# -------------------------------------------------
# TAB 4: WHAT-IF ANALYSIS
# -------------------------------------------------

with whatif_tab:

    st.header("What If You Delay a Course?")

    st.write(
        "Choose a course to postpone and compare your original "
        "schedule with a schedule where that course is delayed."
    )

    if not required:

        st.info(
            "Select courses you still need in the sidebar first."
        )

    else:

        delayed_course = st.selectbox(
            "Which course do you want to delay?",
            options=sorted(required)
        )

        delay_semesters = st.selectbox(
            "How many semesters should it be delayed?",
            options=[1, 2],
            index=0
        )

        if st.button(
            "Calculate the Effect",
            type="primary"
        ):

            try:

                original, delayed, difference = compare_delay(
                    catalog=catalog,
                    completed=completed,
                    required=required,
                    max_credits=max_credits,
                    start_term=start_term,
                    start_year=int(start_year),
                    include_summer=include_summer,
                    delay_course=delayed_course,
                    delay_semesters=delay_semesters
                )

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Original Semesters",
                    len(original)
                )

                col2.metric(
                    "Delayed Semesters",
                    len(delayed)
                )

                col3.metric(
                    "Additional Semesters",
                    difference
                )

                if difference > 0:

                    st.warning(
                        f"Delaying {delayed_course} may add "
                        f"{difference} semester(s) to your plan."
                    )

                else:

                    st.success(
                        "The delay does not increase the total "
                        "number of planned semesters in this scenario."
                    )

                st.subheader("New Suggested Schedule")

                for semester in delayed:

                    course_names = [
                        course["code"]
                        for course in semester["courses"]
                    ]

                    st.write(
                        f"**{semester['term']} {semester['year']}**: "
                        + (
                            ", ".join(course_names)
                            if course_names
                            else "No courses scheduled"
                        )
                    )

                st.caption(
                    "This is a simplified estimate based on prerequisites "
                    "and credit limits. It does not yet account for actual "
                    "class availability or official graduation audits."
                )

            except ValueError as error:

                st.error(str(error))
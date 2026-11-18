# AI Course Planner + Graduation Path Finder

**CMPSC 441 — Streamlit classroom project**

The project plans a *selected set of sample course requirements*, not an official Penn State degree audit. No Penn State authentication, live seats, academic transcript, 120-credit graduation validation, advanced prerequisite alternatives, minimum grades, or actual transfer equivalencies are included.

## Run on your Mac (Python 3.12)

1. Unzip `AI_Course_Planner_Final.zip` into `~/Downloads/AI_Course_Planner_Final`.
2. Open **Terminal** (do not press the ordinary Run button in PyCharm).
3. Run:

```bash
cd ~/Downloads/AI_Course_Planner_Final
/usr/local/bin/python3.12 -m pip install -r requirements.txt
/usr/local/bin/python3.12 -m streamlit run main.py
```

4. If your browser does not open, go to **http://localhost:8501**.
5. Leave Terminal running while you use the application. Press **Control+C** to stop.

If your Python installation is elsewhere, replace `/usr/local/bin/python3.12` with `python3`.

## What's included

- **Semester Planner:** BFS and A* minimize the number of planned terms; UCS optimizes two explicit workload-cost functions.
- **Graduation target:** Select a target end term/year and see if sample plans finish in time. A deadline-constrained UCS alternative is available when a faster plan meets the target but the current workload plan does not.
- **Bottleneck Finder:** Shows required courses with the greatest direct/indirect prerequisite dependencies.
- **Graph:** Visual prerequisite edges; green for completed courses, yellow for bottlenecks.
- **Difficulty choices:** By course level (0–150: 1; 151–300: 2; 301+: 3) or by editable 1–3 manual estimates.
- **What-if:** Separate postpone, drop and fail simulations, dependent-course movement table, revised plans and *optional suggested* general-education replacement courses.
- **Credit notices:** Below 12 and above 19, with an additional reminder that summer can differ from fall/spring.
- **Ask a Question:** Simple rule-based course-code/name and intent detection, e.g., "Can I take CMPSC 465?".
- **Algorithm Comparison:** States explored, milliseconds, semesters, completed credits, workload concentration, overloaded terms and total balanced-cost scores.
- **Custom catalog:** Upload a JSON catalog with your verified course prerequisites (supported prerequisite logic is **AND-only**). It is validated for missing courses, cycles and invalid entries.
- **Exports:** Download plan CSV, what-if CSV and algorithm comparison CSV.
- **Testing:** Includes offline unit tests and a UI-flow smoke test. You can also run the unit tests in the app's Testing & Sources tab.

## Run tests (no Streamlit required)

```bash
cd ~/Downloads/AI_Course_Planner_Final
/usr/local/bin/python3.12 -m unittest -v test_planner.py
```

`smoke_test_ui.py` also exercises major UI code paths with a lightweight imitation of Streamlit; it cannot replace opening and clicking the real website.

## Editing the catalog

Open `courses.json`. Each entry takes this form:

```json
"CMPSC 132": {
  "name": "Programming and Computation II",
  "credits": 3,
  "prerequisites": ["CMPSC 131"],
  "difficulty": 2,
  "category": "Major",
  "offerings": ["Fall", "Spring"]
}
```

All course codes in `prerequisites` must also appear in the same catalog. `offerings` are demonstration seasons, not live sections. When changing course requirements, use the sidebar selector in the application. A catalog can include other courses, but large exact search problems are computationally expensive; the app reports search limitations rather than claiming no course plan exists.

## Data limitations and official sources

The default `courses.json` contains **simplified hypothetical prerequisite relationships and unverified offering seasons**. A few display titles match Penn State's current course names, but the relationships and default required-course list are not an official degree plan. The real Bulletin has conditions such as **OR-prerequisites**, **co-requisites**, **minimum grades**, **elective groups**, and **program requirements by entry year**. This teaching prototype cannot safely evaluate those from the sample schema, and it does not automatically access LionPATH or audit student records.

A course added as a what-if replacement is **not assumed to count toward the degree**. Consult your advisor before treating it as a valid substitution. Failed and dropped courses have different billing/aid consequences; an unsuccessful course's attempted credits should not automatically be treated as dropped credits.

Relevant references, checked for this project in November 2026:
- Computer Science B.S. (Abington): https://bulletins.psu.edu/undergraduate/colleges/abington/computer-science-bs/
- CMPSC course descriptions: https://bulletins.psu.edu/university-course-descriptions/undergraduate/cmpsc/
- Bulletin archive (select the student's *entry year*): https://bulletins.psu.edu/undergraduate/archive/
- 2026-27 Penn State Abington tuition: https://tuition.psu.edu/rates-effective-2026-fall-semester-abington

For undergraduate fall/spring tuition at Abington, published 2026–27 rates specify a **12–19 credit** flat-rate band, with additional charges beyond 19; individual aid and summer charges are separate concerns.

## Files

- `main.py` — Streamlit UI and reports
- `planner_core.py` — search algorithms and validation engine
- `courses.json` — editable **sample** course data
- `requirements.txt` — Streamlit and Graphviz Python dependencies
- `test_planner.py` — test suite
- `smoke_test_ui.py` — offline UI code-flow smoke test
- `REQUIREMENTS_CHECKLIST.md` — original proposal mapped to features and limitations

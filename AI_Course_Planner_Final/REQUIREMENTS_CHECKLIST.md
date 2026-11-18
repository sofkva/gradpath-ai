# Requirements check — AI Course Planner + Graduation Path Finder

Checked against `proposal ideas.pdf` (seven pages) and its "Notes that can be Added" section.

| Proposed feature | Implementation | Limits |
|---|---|---|
| Student supplies completed courses | Sidebar multi-select | Student-entered, not a real transcript |
| Required courses / remaining credits | Required-course selector, automatic AND-prerequisite closure | No official 120-credit degree audit or elective group constraints |
| Prerequisite graph | Graphviz tab | AND-dependencies from selected JSON |
| BFS | Semester-level exact BFS within search limits | 12 terms, 80k states, safety cap of 14 simultaneously eligible courses |
| UCS | Two additive semester workload costs | Defined academic workload score, not GPA |
| A* | Admissible lower bound using credits and longest prerequisite chain | Same sample planning constraints |
| Fastest, balanced, lowest-workload modes | Four views of three algorithms | Balanced and lowest may use extra terms |
| Difficulty scores | Course-level bands plus editable manual scores | Classroom estimates only |
| Intent-based NLP | Regex/keyword course questions | Simple rules; no conversational LLM or official academic record access |
| Explain course recommendations | Reason under every course | Selected-course requirements and dependency counts |
| What-if failed course | Replan and show course term changes | Estimated future retake; attempted credits remain in failed term |
| What-if dropped course | Replan after removal; optional sample gen-ed additions | No real enrollments or financial aid calculation |
| What-if postponement | Delayed earliest enrollment constraint | Academic advising required |
| Bottleneck finder | Downstream dependency ranking | Graph-only ranking |
| Algorithm comparison | States, time, term count, credits, concentration and workload | Execution times vary by computer |
| Prerequisite-aware valid plan | Independent `valid_plan` checks | Does not support co-req/OR/grade-based rules |
| Course offerings | Optional sample offering filter | NOT real registration data |
| Transfer equivalence | Manually mark university courses as fulfilled | No verification of transcripts/transfer equivalents |
| Term/year selector | Start term and year; summer option | 12-term search horizon |
| Graduation target | End-term/year feasibility and optional deadline-constrained UCS | For selected sample courses, not entire degree |
| Credit-load warning <12 or >19 | Semester notices and drop scenario warning | Actual tuition/aid depends on term, student, program |
| Class-level scoring idea | 0–150 / 151–300 / 301+ level categories | Not an evidence-based workload predictor |
| Add gen-ed after drop | Automatically suggested *optional* replacements, editable by user and inserted into revised plan | Must verify the course fulfills a real degree requirement |
| More informative messages | Credit/term explanations and limits throughout the UI | Kept concise in typical cases |
| Unit tests and presentation-ready outputs | 26+ automated tests, UI-flow smoke test, graphs/CSV | Browser clicks still require local Streamlit |
| Real Penn State requirements | Links to official Bulletins and JSON import for manually verified AND-type entries | **Not fully implemented.** Live catalog extraction, full degree audit, OR/co-requisites and authoritative enrollments require separate data integrations and more complex rules. |

## Data accuracy note

The default catalog is deliberately illustrative. For instance, Penn State's 2026-27 Bulletin lists concurrent-enrollment or alternate prerequisite requirements for some CMPSC courses that are not expressible using the simplified default schema. The official required curriculum can also depend on the student's entry year. The app clearly warns against treating example results as official registration or graduation approval.

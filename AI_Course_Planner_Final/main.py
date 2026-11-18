"""CMPSC 441 AI Course Planner + Graduation Path Finder.

Run from Terminal (not the ordinary Python Run button):
    python3 -m streamlit run main.py

Prerequisites, seasonal availability, and degree requirements in courses.json are
ILLUSTRATIVE. A real degree audit must use the student's official Bulletin year.
"""
import csv
from io import StringIO
import json
import unittest

import streamlit as st

from planner_core import (
    COURSES, DEFAULT_REQUIRED, PLANNING_MODES, MAX_TERMS, MAX_STATES,
    validate_catalog, required_closure, difficulty, term_label, term_name,
    term_offset, prerequisites_met, downstream, graph_dot, solve, plan_metrics,
    ask_question, valid_plan, replan_scenario, auto_replacements,
)

BULLETIN_URL = 'https://bulletins.psu.edu/undergraduate/colleges/abington/computer-science-bs/'
CMPSC_URL = 'https://bulletins.psu.edu/university-course-descriptions/undergraduate/cmpsc/'
TUITION_URL = 'https://tuition.psu.edu/rates-effective-2026-fall-semester-abington'
ARCHIVE_URL = 'https://bulletins.psu.edu/undergraduate/archive/'


def as_csv(rows):
    if not rows:
        return ''
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def plan_rows(plan, catalog, start_term, start_year, include_summer, explicit_required):
    rows = []
    for i, semester in enumerate(plan):
        for cid in semester:
            rows.append({
                'Semester': term_label(start_term, start_year, i, include_summer),
                'Course': cid,
                'Title': catalog[cid]['name'],
                'Credits': catalog[cid]['credits'],
                'Purpose': 'Required' if cid in explicit_required else 'Prerequisite / sample elective',
            })
    return rows


def credit_notice(credits, label='This term', season=None):
    if credits == 0:
        st.caption(f'{label}: no scheduled credits. Financial aid and enrollment consequences need individual review.')
    elif credits < 12:
        st.warning(f'{label}: **{credits:g} credits (below 12)**. Check with your academic advisor and the Office of Student Aid before dropping or changing enrollment.')
    elif credits > 19:
        st.warning(f'{label}: **{credits:g} credits (above 19)**. Extra-credit tuition and enrollment approval rules may apply; confirm with an advisor.')
    if season == 'Summer':
        st.caption('Summer tuition/aid rules can differ from fall and spring. Confirm current summer rates.')


def render_plan(plan, catalog, completed, required, cap, start_term,
                start_year, include_summer, difficulty_mode,
                show_reasons=True, added_extras=(), failure_note=None):
    if plan is None:
        st.error('No schedule found within the current search limits.')
        return
    if len(plan) == 0:
        st.success('Every selected sample course is already fulfilled.')
        return
    closure = required_closure(required, catalog)
    done = set(completed)
    for i, semester in enumerate(plan):
        label = term_label(start_term, start_year, i, include_summer)
        season = term_name(start_term, i, include_summer)
        credits = sum(catalog[c]['credits'] for c in semester)
        workload = sum(difficulty(c, catalog, difficulty_mode) for c in semester)
        hard = sum(difficulty(c, catalog, difficulty_mode) == 3 for c in semester)
        with st.container(border=True):
            st.markdown(f'#### {label} · {credits:g} credits · workload {workload}')
            if not semester:
                st.caption('No courses planned this semester; waiting for future availability/prerequisites.')
            for cid in semester:
                info = catalog[cid]
                st.write(f'**{cid} — {info["name"]}** · {info["credits"]:g} credits')
                if show_reasons:
                    reasons = []
                    if cid in added_extras:
                        reasons.append('optional replacement; advisor must confirm degree applicability')
                    elif cid not in required:
                        reasons.append('required prerequisite for a selected course')
                    else:
                        reasons.append('part of your selected requirements')
                    unlocked = len(downstream(cid, closure, catalog))
                    if unlocked:
                        reasons.append(f'unlocks {unlocked} later selected course(s)')
                    previous = info['prerequisites']
                    if previous:
                        reasons.append('prerequisites already completed: ' + ', '.join(previous))
                    st.caption('Why: ' + '; '.join(reasons) + '.')
            if hard >= 3:
                st.warning('Workload warning: three or more level-3 courses in this term.')
            if failure_note and failure_note[0] == i:
                st.info(f'{failure_note[1]} was attempted but failed. The card lists successfully completed course credits ({credits:g}); attempted credits for the term were {failure_note[2]:g}.')
                credit_notice(failure_note[2], label + ' (attempted load)', season)
            else:
                credit_notice(credits, label, season)
        done.update(semester)


def render_deadline(plan, fastest, start_term, start_year, include_summer, deadline_offset):
    if deadline_offset is None:
        return
    if plan is not None:
        finish = (term_label(start_term, start_year, len(plan) - 1, include_summer)
                  if plan else 'Already completed')
        if len(plan) <= deadline_offset + 1:
            st.success(f'This schedule meets the selected target. Estimated last term: **{finish}**.')
        else:
            st.warning(f'This schedule ends in **{finish}**, {len(plan) - (deadline_offset + 1)} planned term(s) after your target.')
    if fastest is not None and len(fastest) > deadline_offset + 1:
        st.error('Even the minimum-term plan exceeds your target in this sample model. Consider changing course selections, term offerings, summer enrollment, or the deadline.')
    elif fastest is not None:
        st.caption('A path within the deadline exists under the *sample* constraints (not a university graduation guarantee).')


def main():
    st.set_page_config(page_title='AI Course Planner', page_icon='🎓', layout='wide')
    st.title('🎓 AI Course Planner + Graduation Path Finder')
    st.caption('CMPSC 441 · Search-based graduation planning · BFS · Uniform Cost Search · A*')
    st.info('**Classroom demonstration, not a Penn State degree audit.** Course prerequisites, sample offerings and the default required-course list are simplified. For actual registration/graduation decisions, verify your Bulletin year, advising report, transfer evaluations and section availability.')

    with st.sidebar:
        st.header('Student information')
        uploaded = st.file_uploader('Optional: upload your verified course catalog (JSON)', type=['json'],
                                    help='Use the same format as courses.json. No server or university login required.')
        catalog = COURSES
        if uploaded is not None:
            try:
                raw = json.loads(uploaded.getvalue().decode('utf-8'))
                validate_catalog(raw)
                catalog = raw
                st.success(f'Custom catalog loaded: {len(catalog)} courses.')
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                st.error(f'Catalog upload error: {exc}')
                st.stop()

        key_suffix = str(hash(json.dumps(catalog, sort_keys=True)))
        options = list(catalog)
        done_input = st.multiselect('Courses already completed', options, key=f'done_{key_suffix}')
        transfer_input = st.multiselect('Verified transfer-equivalent courses',
                                        [c for c in options if c not in done_input],
                                        help='Select courses only after confirming equivalencies with Penn State.',
                                        key=f'transfer_{key_suffix}')
        done = set(done_input) | set(transfer_input)
        default = [c for c in DEFAULT_REQUIRED if c in catalog]
        required = st.multiselect('Courses to complete (sample requirements)', options,
                                  default=default, key=f'required_{key_suffix}')
        cap = st.slider('Maximum credits per semester', 6, 24, 15)
        diff_mode = st.selectbox('Difficulty scoring', ['Course level', 'Manual estimates'],
                                 help='Course level: 0–150 = 1, 151–300 = 2, 301+ = 3. Manual: difficulty field in your JSON.')
        st.markdown('**Term and graduation target**')
        summer = st.checkbox('Include summer semesters', value=False)
        seasons = ['Spring', 'Summer', 'Fall'] if summer else ['Spring', 'Fall']
        start_term = st.selectbox('Plan starts in', seasons, index=0)
        start_year = st.selectbox('Starting year', list(range(2026, 2042)), index=1)
        offerings = st.checkbox('Use sample course offering seasons', value=False,
                                help='Offerings are examples and are not pulled from live Penn State registration.')
        deadline_on = st.checkbox('I have a graduation target', value=False)
        deadline_offset = None
        if deadline_on:
            target_term = st.selectbox('Graduate by the end of', seasons, index=len(seasons) - 1)
            target_year = st.selectbox('Graduation year', list(range(2026, 2045)), index=2)
            deadline_offset = term_offset(start_term, start_year, target_term, target_year, summer)
            if deadline_offset < 0:
                st.error('Your target must be at or after the starting term.')
                deadline_offset = None
            elif deadline_offset >= MAX_TERMS:
                st.caption('Deadline is beyond the 12-term demo horizon; the planner can only evaluate the first 12 terms.')
        st.caption('Fall/Spring: Penn State Abington generally applies the published 12–19-credit full-time tuition band. Summer is different. Financial aid depends on individual circumstances.')

    closure = required_closure(required, catalog)
    signature = (key_suffix, tuple(sorted(done)), tuple(sorted(required)), cap, diff_mode,
                 summer, start_term, start_year, offerings, deadline_on, deadline_offset)
    if st.session_state.get('planner_signature') != signature:
        st.session_state.pop('planner_results', None)
        st.session_state.pop('planner_signature', None)
        st.session_state.pop('deadline_result', None)

    tabs = st.tabs(['Semester Planner', 'Course Catalog', 'Prerequisite Graph', 'Bottleneck Finder',
                    'What-if Analysis', 'Ask a Question', 'Algorithm Comparison', 'Testing & Sources'])
    with tabs[0]:
        st.subheader('Generate a semester-by-semester plan')
        st.write('The planner automatically adds prerequisite courses within the selected catalog. It checks the previous term before allowing dependent courses.')
        auto_needed = sorted(closure - set(required) - done)
        if auto_needed:
            st.caption('Extra prerequisites that must be completed: ' + ', '.join(auto_needed))
        goal = st.selectbox('Planning goal', list(PLANNING_MODES),
                            help='Fastest minimizes the number of semesters. Balanced spreads hard classes while penalizing extra terms. Lowest workload prefers less concentrated difficulty.')
        if st.button('Generate and compare plans', type='primary'):
            if not required:
                st.warning('Choose at least one required course.')
            else:
                with st.spinner('Searching the semester plan possibilities...'):
                    results = {}
                    for label, (alg, preference) in PLANNING_MODES.items():
                        results[label] = solve(alg, done, required, cap, start_term,
                                               summer, offerings, workload_mode=preference,
                                               catalog=catalog, difficulty_mode=diff_mode)
                    st.session_state['planner_results'] = results
                    st.session_state['planner_signature'] = signature
        results = st.session_state.get('planner_results')
        if results:
            selected = results[goal]
            baseline = results['Fastest (BFS)']['plan']
            if selected['plan'] is None:
                st.error('No plan was found within 12 terms and 80,000 explored states. This is not proof that graduation is impossible.')
                if selected['limited']:
                    st.warning(selected.get('reason', 'The search-state limit was reached; smaller course selections or different assumptions may help.'))
            else:
                plan = selected['plan']
                metrics = plan_metrics(plan, catalog, diff_mode)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric('Planned semesters', metrics['semesters'])
                c2.metric('Required credits scheduled', f'{metrics["credits"]:g}')
                c3.metric('Peak workload', metrics['peak_difficulty'])
                c4.metric('Workload concentration', metrics['concentration'])
                st.success(f'{goal}: {selected["explored"]:,} states explored in {selected["ms"]:.1f} ms; schedule validity: {"PASS" if selected["valid"] else "FAIL"}.')
                render_deadline(plan, baseline, start_term, start_year, summer, deadline_offset)
                render_plan(plan, catalog, done, set(required), cap, start_term,
                            start_year, summer, diff_mode)
                st.download_button('Download semester plan (CSV)',
                                   as_csv(plan_rows(plan, catalog, start_term, start_year, summer, required)),
                                   'semester_plan.csv', 'text/csv')
                if deadline_offset is not None and 0 <= deadline_offset < MAX_TERMS and len(plan) > deadline_offset + 1:
                    if goal.startswith(('Balanced', 'Lowest')) and baseline is not None and len(baseline) <= deadline_offset + 1:
                        st.warning('The fastest plan meets your deadline, but this workload preference does not. Try the deadline-constrained option below.')
                        if st.button('Find a workload-friendly plan within the target'):
                            alg, pref = PLANNING_MODES[goal]
                            constrained = solve(alg, done, required, cap, start_term, summer, offerings,
                                                max_terms=deadline_offset + 1, workload_mode=pref,
                                                catalog=catalog, difficulty_mode=diff_mode)
                            st.session_state['deadline_result'] = constrained
                        constrained = st.session_state.get('deadline_result')
                        if constrained:
                            if constrained['plan'] is not None:
                                st.success('Found a plan within the target. This is an alternate deadline-constrained solution.')
                                render_plan(constrained['plan'], catalog, done, set(required), cap,
                                            start_term, start_year, summer, diff_mode)
                            else:
                                st.error('No deadline-constrained plan was found within the search limits.')
        else:
            st.caption('Choose student information in the sidebar and click **Generate and compare plans**.')

    with tabs[1]:
        st.subheader('Course catalog and difficulty levels')
        st.dataframe([{
            'Course': cid, 'Course title': info['name'], 'Credits': info['credits'],
            'Prerequisites (AND)': ', '.join(info['prerequisites']) or 'None',
            'Course-level score': difficulty(cid, catalog, 'Course level'),
            'Manual estimate': info['difficulty'], 'Category': info['category'],
            'Example offerings': ', '.join(info['offerings'])
        } for cid, info in catalog.items()], hide_index=True, width='stretch')
        st.caption('This demo catalog supports **AND-type prerequisites**. Official requirements may also include alternatives, concurrent courses, grades and placement conditions. Confirm those separately before treating a plan as accurate.')
        with st.expander('Update your courses and degree requirements'):
            st.write('Download the JSON file, modify names, credits, AND-prerequisites, categories and offerings, then upload it using the sidebar. Each prerequisite must also appear in the JSON. To change degree requirements, use the sidebar selector.')
            st.download_button('Download editable catalog (JSON)',
                               json.dumps(catalog, indent=2), 'courses_editable.json', 'application/json')
            st.write('The program validates missing prerequisite courses and circular requirements before planning. Complex official rules are **not** automatically scraped or audited.')

    with tabs[2]:
        st.subheader('Prerequisite dependency graph')
        if closure:
            st.caption('Green: already fulfilled · Yellow: high-dependency course · Blue: other course. Arrows point to dependent courses.')
            try:
                st.graphviz_chart(graph_dot(closure, done, catalog), width='stretch')
            except Exception as exc:
                st.error(f'Graph cannot render: {exc}. Install requirements.txt and confirm Graphviz support.')
            edges = [{'Prerequisite': prereq, 'Needed for': cid}
                     for cid in sorted(closure) for prereq in catalog[cid]['prerequisites']]
            st.dataframe(edges, hide_index=True, width='stretch')
        else:
            st.info('Choose some required courses to see a graph.')

    with tabs[3]:
        st.subheader('Bottleneck Finder')
        st.write('A larger count means this course unlocks more other selected courses directly or indirectly. These are important classes to discuss taking early.')
        ranked = sorted(((cid, len(downstream(cid, closure, catalog))) for cid in closure),
                        key=lambda pair: (-pair[1], pair[0]))
        st.dataframe([{'Course': cid, 'Downstream courses': score,
                       'Fulfilled': 'Yes' if cid in done else 'No',
                       'Difficulty': difficulty(cid, catalog, diff_mode)} for cid, score in ranked],
                     hide_index=True, width='stretch')
        top = next(((cid, count_) for cid, count_ in ranked if cid not in done and count_ > 0), None)
        if top:
            st.info(f'**{top[0]}** is a priority candidate because {top[1]} selected courses depend on it.')
        st.caption('Bottleneck counts are graph measurements, not proof of registration eligibility or an official degree critical path.')

    with tabs[4]:
        st.subheader('What if I drop, fail, or postpone a course?')
        results = st.session_state.get('planner_results')
        if not results or not any(r['plan'] is not None and r['plan'] for r in results.values()):
            st.info('Generate a nonempty plan first in Semester Planner.')
        else:
            possible = [label for label, r in results.items() if r['plan']]
            basis = st.selectbox('Plan to change', possible, key='whatif_basis')
            original = results[basis]['plan']
            alg, preference = PLANNING_MODES[basis]
            target = st.selectbox('Affected course', [cid for term in original for cid in term], key='whatif_target')
            scenario = st.radio('What happened?', ['Postpone', 'Drop', 'Fail'], horizontal=True)
            base = replan_scenario(original, target, scenario, done, required, cap,
                                   start_term, start_year, summer, offerings,
                                   algorithm=alg, workload_mode=preference,
                                   catalog=catalog, difficulty_mode=diff_mode)
            added = ()
            if base['plan'] is not None and scenario in ('Postpone', 'Drop'):
                remaining = sum(catalog[c]['credits'] for c in base['plan'][base['target_term']])
                st.write(f'After {"postponing" if scenario == "Postpone" else "dropping"} {target}, the affected term has **{remaining:g} planned credits** before replacements.')
                if base['candidates']:
                    st.caption('Optional sample general-education/elective candidates not currently scheduled: ' + ', '.join(base['candidates']))
                    added = tuple(st.multiselect('Automatically suggested replacements (editable)',
                                                 base['candidates'], default=list(base['auto']),
                                                 key=f'replacements_{hash(signature)}_{basis}_{target}_{scenario}',
                                                 help='These are sample catalog suggestions; confirm with an advisor whether each satisfies degree requirements.'))
                    if sum(catalog[c]['credits'] for c in added) + remaining > cap:
                        st.error('Replacement choices exceed the maximum credit limit. Remove one to continue.')
                        added = ()
                elif remaining < 12:
                    st.warning('No eligible, unplanned sample general-education replacement is available. Ask your advisor for a class that counts toward your actual degree.')
            elif scenario == 'Fail':
                st.info('A failed class normally remains an attempted/enrolled course for that semester; it does not count as successfully completed. Replanning assumes a future retake and does not retroactively remove its attempted credits.')
            try:
                response = replan_scenario(original, target, scenario, done, required, cap,
                                           start_term, start_year, summer, offerings,
                                           algorithm=alg, workload_mode=preference,
                                           catalog=catalog, difficulty_mode=diff_mode,
                                           extra_courses=added)
            except ValueError as exc:
                st.error(str(exc))
                response = {'plan': None}
            revised = response['plan']
            impacted = sorted(downstream(target, closure, catalog))
            st.write(f'**Courses that depend on {target}:** {", ".join(impacted) if impacted else "None"}')
            st.caption(f'Affected original term: {term_label(start_term, start_year, base["target_term"], summer)}')
            if revised is None:
                st.error('No revised plan found within 12 terms and the search-state limit. This does not prove there is no valid future plan.')
            else:
                delta = len(revised) - len(original)
                a, b, c = st.columns(3)
                a.metric('Original semesters', len(original))
                b.metric('Revised semesters', len(revised))
                c.metric('Estimated term change', f'{delta:+d}')
                original_offsets = {cid: i for i, term in enumerate(original) for cid in term}
                updated_offsets = {cid: i for i, term in enumerate(revised) for cid in term}
                changes = [
                    {'Course': cid,
                     'Original': term_label(start_term, start_year, offset, summer),
                     'Revised': term_label(start_term, start_year, updated_offsets[cid], summer),
                     'Term change': f'{updated_offsets[cid]-offset:+d}'}
                    for cid, offset in original_offsets.items()
                    if cid in updated_offsets and updated_offsets[cid] != offset
                ]
                if changes:
                    st.write('**Courses whose terms changed:**')
                    st.dataframe(changes, hide_index=True, width='stretch')
                else:
                    st.caption('Other scheduled course terms are unchanged in this simulation.')
                if scenario == 'Fail':
                    attempted = sum(catalog[c]['credits'] for c in original[base['target_term']])
                    earned = attempted - catalog[target]['credits']
                    st.write(f'In the failed term: **{attempted:g} attempted credits**, of which **{earned:g}** are represented as successfully completed in this scenario.')
                else:
                    new_credits = sum(catalog[c]['credits'] for c in revised[base['target_term']])
                    st.write(f'After the proposed replacement(s), that term contains **{new_credits:g} credits**.')
                    credit_notice(new_credits, 'Affected term', term_name(start_term, base['target_term'], summer))
                if added:
                    st.warning('The added classes are sample suggestions, **not verified degree substitutions**. Ask an advisor to confirm they count before registration.')
                if deadline_offset is not None:
                    render_deadline(revised, results['Fastest (BFS)']['plan'], start_term, start_year, summer, deadline_offset)
                with st.expander('View updated semester plan', expanded=True):
                    render_plan(revised, catalog, done, set(required), cap,
                                start_term, start_year, summer, diff_mode,
                                added_extras=set(added),
                                failure_note=(base['target_term'], target, sum(catalog[c]['credits'] for c in original[base['target_term']])) if scenario == 'Fail' else None)
                st.download_button('Download what-if plan (CSV)',
                                   as_csv(plan_rows(revised, catalog, start_term, start_year, summer, required)),
                                   'what_if_schedule.csv', 'text/csv')
                st.caption('What-if predictions assume all unaffected classes are passed. Dropping, failing, and withdrawing have different actual transcript/aid consequences. Confirm them with advising.')

    with tabs[5]:
        st.subheader('Ask a course question')
        st.caption('Basic NLP uses course-name/code detection and keyword intent matching. It is not a language model or a live advising chatbot.')
        question = st.text_input('Question', placeholder='Can I take CMPSC 465?')
        if st.button('Get course answer'):
            if not question.strip():
                st.warning('Type a question with a course code.')
            else:
                st.info(ask_question(question, done, closure, start_term,
                                    summer, offerings, catalog, diff_mode))
        st.caption('Examples: “What does CMPSC 132 unlock?” · “What are the prerequisites for CMPSC 473?” · “How many credits is MATH 141?”')

    with tabs[6]:
        st.subheader('BFS, UCS, and A* algorithm comparison')
        results = st.session_state.get('planner_results')
        if not results:
            st.info('Click Generate and compare plans in the first tab.')
        else:
            rows = []
            for label, result in results.items():
                stats = plan_metrics(result['plan'], catalog, diff_mode)
                rows.append({
                    'Algorithm / Goal': label, 'Valid plan': 'Yes' if result['valid'] else 'No',
                    'Search limit hit': 'Yes' if result['limited'] else 'No',
                    'States explored': result['explored'], 'Execution (ms)': round(result['ms'], 2),
                    'Semesters': stats.get('semesters', '—'),
                    'Total course credits': stats.get('credits', '—'),
                    'Peak difficulty': stats.get('peak_difficulty', '—'),
                    '3+ hard courses together': stats.get('overloaded_terms', '—'),
                    'Concentration score': stats.get('concentration', '—'),
                    'Total balanced-cost score': stats.get('workload_cost', '—')
                })
            st.dataframe(rows, hide_index=True, width='stretch')
            st.download_button('Download comparison results (CSV)',
                               as_csv(rows), 'algorithm_comparison.csv', 'text/csv')
            st.write('**BFS and A*** seek the fewest terms. **UCS** minimizes an additive workload cost. The two UCS runs have different per-term penalties. Scores are invented for the project; lower workload scores do not predict GPA.')
            st.caption('Measured time varies by computer and run. Searches are exact within the modeled AND-prerequisites, sample offerings, stated term cap and finite search-state limit.')
            bf = results['Fastest (BFS)']['plan']
            af = results['Fastest (A*)']['plan']
            if bf is not None and af is not None:
                if len(bf) == len(af):
                    st.success(f'Sanity check: BFS and A* agree on a minimum of {len(bf)} term(s).')
                else:
                    st.error('Mismatch between BFS and A*: review the model or search limits.')

    with tabs[7]:
        st.subheader('Testing and official resources')
        st.write('Run automated tests that check prerequisite order, credit caps, BFS/A* optimality on the demo sample, workload balancing, catalog validation, deadlines, transfers, and what-if replacements.')
        if st.button('Run automated planner tests'):
            from importlib import import_module
            test_mod = import_module('test_planner')
            suite = unittest.defaultTestLoader.loadTestsFromModule(test_mod)
            log = StringIO()
            runner = unittest.TextTestRunner(stream=log, verbosity=2)
            outcome = runner.run(suite)
            if outcome.wasSuccessful():
                st.success(f'All {outcome.testsRun} tests passed.')
            else:
                st.error(f'{len(outcome.failures)} failures, {len(outcome.errors)} errors in {outcome.testsRun} tests.')
            with st.expander('See individual test results'):
                st.code(log.getvalue(), language='text')
        st.write('**Use these official sources to build and verify a real catalog:**')
        st.markdown(f'- [Penn State Abington Computer Science B.S. Bulletin]({BULLETIN_URL})\n'
                    f'- [Penn State CMPSC course descriptions]({CMPSC_URL})\n'
                    f'- [Penn State archived Bulletins (use your entry year)]({ARCHIVE_URL})\n'
                    f'- [Abington fall 2026 tuition and credit-load policy]({TUITION_URL})')
        st.caption('Important limitation: this project does not automatically retrieve the Bulletin, LionPATH schedules, alternatives such as “CMPSC 132 OR CMPSC 122,” co-requisites, minimum grades, 120-credit program totals, or official transfer evaluations. Enter verified AND-prerequisites in a custom JSON file and ask an advisor to check any omitted rules.')

    st.divider()
    st.caption('Project status: implemented BFS, UCS, A*, planning preferences, deadline feasibility, graph, bottlenecks, estimated course-level difficulty, course questions, scenario-based what-if replanning, sample gen-ed replacement, comparisons, exports and tests. Not an official university degree audit.')


if __name__ == '__main__':
    main()

"""Pure-Python scheduling engine for the AI Course Planner demonstration.

No Streamlit dependency: run the unit tests or import these functions directly.
Course/prerequisite data is illustrative until the student verifies a catalog.
"""
from collections import deque
from heapq import heappop, heappush
from itertools import combinations, count
from math import ceil
from pathlib import Path
from time import perf_counter
import json
import re

CATALOG_FILE = Path(__file__).with_name('courses.json')
COURSES = json.loads(CATALOG_FILE.read_text(encoding='utf-8'))
DEFAULT_REQUIRED = [
    'CMPSC 131', 'CMPSC 132', 'CMPSC 360', 'CMPSC 465', 'CMPSC 473',
    'CMPSC 311', 'MATH 140', 'MATH 141', 'STAT 200', 'ENGL 15'
]
ALGORITHMS = ('BFS', 'UCS', 'A*')
PLANNING_MODES = {
    'Fastest (BFS)': ('BFS', 'Balanced'),
    'Balanced (UCS)': ('UCS', 'Balanced'),
    'Lowest workload (UCS)': ('UCS', 'Lowest'),
    'Fastest (A*)': ('A*', 'Balanced'),
}
MAX_TERMS = 12
MAX_STATES = 80000
TERMS = ('Spring', 'Summer', 'Fall')


def validate_catalog(catalog):
    """Check edit/upload errors before running the algorithms."""
    if not isinstance(catalog, dict) or not catalog:
        raise ValueError('Catalog must be a nonempty JSON object of course codes.')
    if len(catalog) > 40:
        raise ValueError('For this classroom prototype, use 40 or fewer courses.')
    for cid, info in catalog.items():
        if not isinstance(cid, str) or not re.fullmatch(r'[A-Z][A-Z0-9&-]*\s+\d{1,3}[A-Z]?', cid):
            raise ValueError(f'Invalid course code: {cid!r}. Use a code such as CMPSC 132.')
        if not isinstance(info, dict):
            raise ValueError(f'{cid}: expected a course information object.')
        if not isinstance(info.get('name'), str) or not info['name'].strip():
            raise ValueError(f'{cid}: name is missing.')
        if type(info.get('credits')) not in (int, float) or not (0 < info['credits'] <= 20):
            raise ValueError(f'{cid}: credits must be a positive number not exceeding 20.')
        if type(info.get('difficulty')) is not int or info['difficulty'] not in (1, 2, 3):
            raise ValueError(f'{cid}: difficulty must be an integer from 1 to 3.')
        if not isinstance(info.get('category'), str) or not info['category'].strip():
            raise ValueError(f'{cid}: category is missing.')
        offerings = info.get('offerings')
        if not isinstance(offerings, list) or not offerings or any(x not in TERMS for x in offerings):
            raise ValueError(f'{cid}: offerings must list Spring, Summer, and/or Fall.')
        prereqs = info.get('prerequisites')
        if not isinstance(prereqs, list) or not all(isinstance(p, str) for p in prereqs) or len(prereqs) != len(set(prereqs)):
            raise ValueError(f'{cid}: prerequisites must be a list without duplicates.')
        for p in prereqs:
            if p not in catalog:
                raise ValueError(f'{cid}: prerequisite {p!r} is missing from the catalog.')
            if p == cid:
                raise ValueError(f'{cid}: cannot be its own prerequisite.')
    visited, active = set(), set()

    def check(cid):
        if cid in active:
            raise ValueError(f'Prerequisite cycle detected involving {cid}.')
        if cid in visited:
            return
        active.add(cid)
        for p in catalog[cid]['prerequisites']:
            check(p)
        active.remove(cid)
        visited.add(cid)

    for cid in catalog:
        check(cid)
    return True


validate_catalog(COURSES)


def course_level_difficulty(cid):
    """Project rule: numbers 0–150 -> 1, 151–300 -> 2, 301+ -> 3."""
    match = re.search(r'\b(\d{1,3})[A-Z]?$', cid)
    if not match:
        raise ValueError(f'Course number missing from: {cid}')
    number = int(match.group(1))
    return 1 if number <= 150 else 2 if number <= 300 else 3


def difficulty(cid, catalog=COURSES, mode='Course level'):
    if mode == 'Course level':
        return course_level_difficulty(cid)
    if mode == 'Manual estimates':
        return catalog[cid]['difficulty']
    raise ValueError('Unknown difficulty mode')


def required_closure(required, catalog=COURSES):
    """All explicit requirements and their recursively required AND-prerequisites."""
    out = set()

    def visit(cid):
        if cid not in catalog:
            raise ValueError(f'Course not found in catalog: {cid}')
        if cid not in out:
            out.add(cid)
            for p in catalog[cid]['prerequisites']:
                visit(p)

    for cid in required:
        visit(cid)
    return out


def terms_sequence(include_summer):
    return TERMS if include_summer else ('Spring', 'Fall')


def term_pair(start_term, start_year, offset, include_summer=False):
    terms = terms_sequence(include_summer)
    if start_term not in terms or int(start_year) < 2000 or offset < 0:
        raise ValueError('Invalid term/year or offset.')
    i = terms.index(start_term) + offset
    return terms[i % len(terms)], int(start_year) + i // len(terms)


def term_name(start_term, offset, include_summer=False):
    return term_pair(start_term, 2026, offset, include_summer)[0]


def term_label(start_term, start_year, offset, include_summer=False):
    term, year = term_pair(start_term, start_year, offset, include_summer)
    return f'{term} {year}'


def term_offset(start_term, start_year, target_term, target_year, include_summer=False):
    """0-based offset for a deadline; -1 for dates before the starting term."""
    terms = terms_sequence(include_summer)
    if target_term not in terms or start_term not in terms:
        raise ValueError('Select terms that are included in the plan.')
    return (int(target_year) - int(start_year)) * len(terms) + terms.index(target_term) - terms.index(start_term)


def prerequisites_met(cid, completed, catalog=COURSES):
    return set(catalog[cid]['prerequisites']).issubset(completed)


def downstream(course, required, catalog=COURSES):
    descendants, frontier = set(), [course]
    while frontier:
        current = frontier.pop()
        for candidate in required:
            if current in catalog[candidate]['prerequisites'] and candidate not in descendants:
                descendants.add(candidate)
                frontier.append(candidate)
    descendants.discard(course)
    return descendants


def eligible_courses(completed, needed, offset, start_term, include_summer,
                     use_offerings, earliest=None, catalog=COURSES):
    earliest = earliest or {}
    season = term_name(start_term, offset, include_summer)
    return [cid for cid in sorted(needed - set(completed))
            if prerequisites_met(cid, completed, catalog)
            and offset >= earliest.get(cid, 0)
            and (not use_offerings or season in catalog[cid]['offerings'])]


def semester_combinations(eligible, max_credits, catalog=COURSES, allow_wait=False):
    """Exact subsets: never truncate the BFS search in a way that breaks optimality."""
    out = []
    for size in range(1, len(eligible) + 1):
        for combo in combinations(eligible, size):
            if sum(catalog[c]['credits'] for c in combo) <= max_credits:
                out.append(combo)
    out.sort(key=lambda combo: (-sum(catalog[c]['credits'] for c in combo), combo))
    if allow_wait:
        out.append(())
    return out


def semester_cost(semester, mode='Balanced', catalog=COURSES, difficulty_mode='Course level'):
    """Nonnegative per-term objective. Costs are scores, not GPA predictions.

    Raw sum of course difficulty is constant across schedules; squared loads penalize
    bunching classes together. A positive per-term cost prevents unlimited waiting.
    """
    load = sum(difficulty(cid, catalog, difficulty_mode) for cid in semester)
    hard = sum(difficulty(cid, catalog, difficulty_mode) == 3 for cid in semester)
    credits = sum(catalog[c]['credits'] for c in semester)
    if mode == 'Balanced':
        return 50 + load ** 2 + 55 * max(0, hard - 2) ** 2 + 2 * max(0, 12 - credits)
    if mode == 'Lowest':
        return 10 + load ** 2 + 90 * max(0, hard - 2) ** 2
    raise ValueError('Unknown workload preference')


def semesters_remaining_lower_bound(completed, needed, max_credits, catalog=COURSES):
    """Admissible minimum-term bound: max(credit packing, longest dependency chain)."""
    remaining = needed - set(completed)
    if not remaining:
        return 0
    credits_bound = ceil(sum(catalog[c]['credits'] for c in remaining) / max_credits)
    cache = {}

    def depth(cid):
        if cid not in remaining:
            return 0
        if cid not in cache:
            cache[cid] = 1 + max((depth(p) for p in catalog[cid]['prerequisites']), default=0)
        return cache[cid]

    return max(credits_bound, max(depth(cid) for cid in remaining))


def valid_plan(schedule, initial_completed, required, max_credits, start_term,
               include_summer=False, use_offerings=False, earliest=None,
               catalog=COURSES, allowed_extras=None):
    if schedule is None:
        return False
    needed = required_closure(required, catalog)
    allowed = needed | set(allowed_extras or ())
    done = set(initial_completed)
    earliest = earliest or {}
    for i, semester in enumerate(schedule):
        if len(semester) != len(set(semester)):
            return False
        if sum(catalog[c]['credits'] for c in semester if c in catalog) > max_credits:
            return False
        before = done.copy()  # Prerequisites must be met BEFORE the semester.
        for cid in semester:
            if cid not in catalog or cid not in allowed or cid in before:
                return False
            if not prerequisites_met(cid, before, catalog):
                return False
            if i < earliest.get(cid, 0):
                return False
            if use_offerings and term_name(start_term, i, include_summer) not in catalog[cid]['offerings']:
                return False
        done.update(semester)
    return needed.issubset(done)


def solve(algorithm, initial_completed, required, max_credits, start_term='Spring',
          include_summer=False, use_offerings=False, earliest=None, max_terms=MAX_TERMS,
          max_states=MAX_STATES, workload_mode='Balanced', catalog=COURSES,
          difficulty_mode='Course level'):
    """BFS/A* find minimum semester count; UCS minimizes the chosen additive cost."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f'Unknown algorithm: {algorithm}')
    if max_terms < 0 or max_states < 1 or max_credits <= 0:
        raise ValueError('Invalid search limits / credit cap')
    needed = required_closure(required, catalog)
    earliest = earliest or {}
    completed0 = frozenset(set(initial_completed) & needed)
    initial = (completed0, 0)
    parents = {initial: None}
    explored = 0
    serial = count()
    started = perf_counter()

    if algorithm == 'BFS':
        queue = deque([initial])
        seen = {initial}
    else:
        queue = []
        heappush(queue, (semesters_remaining_lower_bound(completed0, needed, max_credits, catalog)
                         if algorithm == 'A*' else 0, next(serial), 0., initial))
        best_g = {initial: 0.}

    goal = None
    while queue and explored < max_states:
        if algorithm == 'BFS':
            state = queue.popleft()
            g = state[1]
        else:
            _, _, g, state = heappop(queue)
            if g > best_g.get(state, float('inf')) + 1e-8:
                continue
        completed, offset = state
        explored += 1
        if needed.issubset(completed):
            goal = state
            break
        if offset >= max_terms:
            continue
        choices = eligible_courses(completed, needed, offset, start_term,
                                   include_summer, use_offerings, earliest, catalog)
        can_wait = use_offerings or any(earliest.get(cid, 0) > offset for cid in needed - set(completed))
        if len(choices) > 14:
            # Avoid building up to millions of possible course combinations.
            # Report a search-limit result rather than silently returning a nonoptimal plan.
            return {'plan': None, 'explored': explored,
                    'ms': (perf_counter() - started) * 1000,
                    'valid': False, 'limited': True,
                    'reason': 'Over 14 courses are simultaneously eligible; select a smaller course set for exact search.'}
        for combo in semester_combinations(choices, max_credits, catalog, can_wait):
            child = (completed.union(combo), offset + 1)
            if algorithm == 'BFS':
                if child not in seen:
                    seen.add(child)
                    parents[child] = (state, combo)
                    queue.append(child)
            else:
                edge = (semester_cost(combo, workload_mode, catalog, difficulty_mode)
                        if algorithm == 'UCS' else 1)
                score = g + edge
                if score + 1e-8 < best_g.get(child, float('inf')):
                    best_g[child] = score
                    parents[child] = (state, combo)
                    h = (semesters_remaining_lower_bound(child[0], needed, max_credits, catalog)
                         if algorithm == 'A*' else 0)
                    heappush(queue, (score + h, next(serial), score, child))

    ms = (perf_counter() - started) * 1000
    if goal is None:
        return {'plan': None, 'explored': explored, 'ms': ms, 'valid': False,
                'limited': explored >= max_states}
    plan = []
    state = goal
    while parents[state] is not None:
        parent, combo = parents[state]
        plan.append(tuple(combo))
        state = parent
    plan.reverse()
    return {'plan': plan, 'explored': explored, 'ms': ms,
            'valid': valid_plan(plan, initial_completed, required, max_credits,
                                start_term, include_summer, use_offerings,
                                earliest, catalog), 'limited': False}


def plan_metrics(plan, catalog=COURSES, difficulty_mode='Course level'):
    if plan is None:
        return {}
    loads = [sum(difficulty(c, catalog, difficulty_mode) for c in term) for term in plan]
    hard = [sum(difficulty(c, catalog, difficulty_mode) == 3 for c in term) for term in plan]
    return {
        'semesters': len(plan),
        'credits': sum(catalog[c]['credits'] for term in plan for c in term),
        'peak_difficulty': max(loads, default=0),
        'overloaded_terms': sum(n >= 3 for n in hard),
        'workload_cost': sum(semester_cost(term, 'Balanced', catalog, difficulty_mode) for term in plan),
        'concentration': sum(v**2 + 55 * max(0, n-2)**2 for v, n in zip(loads, hard)),
    }


def suggested_replacements(completed_before, original_plan, required, season,
                           use_offerings=False, catalog=COURSES):
    """Extra *sample* gen-eds not already completed/planned/required."""
    all_planned = {cid for term in original_plan for cid in term}
    return [cid for cid, info in catalog.items()
            if info['category'].lower() in ('general education', 'elective')
            and cid not in completed_before and cid not in all_planned
            and cid not in required and prerequisites_met(cid, completed_before, catalog)
            and (not use_offerings or season in info['offerings'])]


def auto_replacements(remaining, candidates, credit_cap, catalog=COURSES):
    """Recommend a few feasible sample gen-eds, preferring a 12-19 credit load.

    Outside the 12-19 band if impossible, choose greatest attainable credits <= cap.
    Only works for catalog-level prerequisites; cannot establish degree applicability.
    """
    if remaining >= 12:
        return ()
    combos = [()]
    for size in (1, 2, 3):
        for group in combinations(candidates, size):
            credits = sum(catalog[c]['credits'] for c in group)
            if remaining + credits <= credit_cap:
                combos.append(group)
    if not combos:
        return ()
    # 1) Meet >=12 if possible 2) fewest added courses 3) closest to 12.
    return min(combos, key=lambda group: (
        (remaining + sum(catalog[c]['credits'] for c in group) < 12),
        max(0, 12 - remaining - sum(catalog[c]['credits'] for c in group)),
        len(group),
        max(0, remaining + sum(catalog[c]['credits'] for c in group) - 12)
    ))


def replan_scenario(baseline, target, scenario, initial_completed, required, max_credits,
                    start_term, start_year, include_summer=False, use_offerings=False,
                    algorithm='BFS', workload_mode='Balanced', catalog=COURSES,
                    difficulty_mode='Course level', extra_courses=()):
    """Return baseline-fixed replanning and optional *extra* sample gen-ed replacement.

    Postpone: hypothetical before the term; entire future can be recomputed.
    Drop: remove from current term, preserve earlier passed courses, then replan.
    Fail: enrollment credits remain attempted; course must be retaken in future.
    """
    if baseline is None or target not in [cid for term in baseline for cid in term]:
        raise ValueError('Choose a course that is in the current plan.')
    if scenario not in ('Postpone', 'Drop', 'Fail'):
        raise ValueError('Unknown what-if scenario.')
    index = next(i for i, term in enumerate(baseline) if target in term)
    if scenario == 'Postpone':
        result = solve(algorithm, initial_completed, required, max_credits, start_term,
                       include_summer, use_offerings, earliest={target: index + 1},
                       catalog=catalog, workload_mode=workload_mode,
                       difficulty_mode=difficulty_mode)
        plan = result['plan']
        replacement_index = index
    else:
        prefix = [tuple(cid for cid in term if cid != target) for term in baseline[:index + 1]]
        passed = set(initial_completed)
        for semester in prefix:
            passed.update(semester)
        next_term = term_name(start_term, index + 1, include_summer)
        result = solve(algorithm, passed, required, max_credits, next_term,
                       include_summer, use_offerings, max_terms=max(0, MAX_TERMS - index - 1),
                       catalog=catalog, workload_mode=workload_mode,
                       difficulty_mode=difficulty_mode)
        plan = None if result['plan'] is None else prefix + result['plan']
        replacement_index = index

    candidates = []
    auto = ()
    if plan is not None and scenario in ('Postpone', 'Drop'):
        season = term_name(start_term, replacement_index, include_summer)
        before = set(initial_completed)
        for semester in plan[:replacement_index]:
            before.update(semester)
        needed = required_closure(required, catalog)
        candidates = suggested_replacements(before, baseline, needed, season, use_offerings, catalog)
        existing = sum(catalog[c]['credits'] for c in plan[replacement_index]) if replacement_index < len(plan) else 0
        candidates = [c for c in candidates if c not in {x for t in plan for x in t}]
        auto = auto_replacements(existing, candidates, max_credits, catalog)
        if extra_courses:
            chosen = tuple(extra_courses)
            if not set(chosen).issubset(candidates) or len(set(chosen)) != len(chosen):
                raise ValueError('Only available, unplanned gen-ed suggestions can be added.')
            if existing + sum(catalog[c]['credits'] for c in chosen) > max_credits:
                raise ValueError('The replacement would exceed the credit cap.')
            if replacement_index >= len(plan):
                # Postponement of the only remaining course can leave an empty term; add it.
                plan = plan + [tuple(chosen)]
            else:
                plan = [tuple(term) + chosen if i == replacement_index else tuple(term)
                        for i, term in enumerate(plan)]
        # No automatic mutation by the engine; UI can apply 'auto' explicitly.

    return {'plan': plan, 'replan_result': result, 'target_term': index,
            'candidates': candidates, 'auto': auto,
            'allowed_extras': tuple(extra_courses)}


def ask_question(question, completed, required, start_term, include_summer=False,
                 use_offerings=False, catalog=COURSES, difficulty_mode='Course level'):
    """Simple NLP: explicit course identification plus keyword intent matching."""
    q = question.lower().strip()
    found = None
    for cid, info in catalog.items():
        normalized = re.escape(cid.lower()).replace(r'\ ', r'\s*')
        if re.search(r'(?<!\w)' + normalized + r'(?!\w)', q) or info['name'].lower() in q:
            found = cid
            break
    if not found:
        return 'Please include a course code, such as “Can I take CMPSC 465?” or “What does CMPSC 132 unlock?”'
    data = catalog[found]
    missing = [p for p in data['prerequisites'] if p not in completed]
    if any(word in q for word in ('unlock', 'depend', 'blocked', 'after this')):
        unlocked = sorted(downstream(found, required, catalog))
        return f'{found} unlocks {len(unlocked)} selected course(s): ' + ', '.join(unlocked) if unlocked else f'No selected course depends on {found}.'
    if any(word in q for word in ('credit', 'difficulty', 'hard', 'workload')):
        return (f'{found} carries {data["credits"]} credits. Its difficulty score is '
                f'{difficulty(found, catalog, difficulty_mode)}/3 under the chosen project rule.')
    if any(word in q for word in ('prereq', 'require', 'before')):
        listed = ', '.join(data['prerequisites']) or 'none'
        return f'{found} has these prerequisites in the selected catalog: {listed}. ' + (f'You are missing {", ".join(missing)}.' if missing else 'They are satisfied.')
    if found in completed:
        return f'{found} is marked as already completed or fulfilled.'
    if missing:
        return f'Not yet: finish {", ".join(missing)} before enrolling in {found}.'
    if use_offerings and start_term not in data['offerings']:
        return f'Prerequisites are satisfied, but {found} is not in the example {start_term} offerings.'
    return f'{found} is eligible under this sample prerequisite model for {start_term}, subject to official registration rules.'


def graph_dot(needed, completed, catalog=COURSES):
    lines = ['digraph prerequisites {', 'rankdir="LR";',
             'graph [bgcolor="transparent", ranksep="0.65", nodesep="0.3"];',
             'node [shape="box", style="rounded,filled", fontname="Arial", fontsize="10", color="#8893a1"];',
             'edge [color="#8b97a6", arrowsize="0.7"];']
    for cid in sorted(needed):
        fill = '#dcfce7' if cid in completed else ('#fef3c7' if len(downstream(cid, needed, catalog)) >= 2 else '#e8f1fd')
        lines.append(f'{json.dumps(cid)} [fillcolor={json.dumps(fill)}];')
    for cid in sorted(needed):
        for p in catalog[cid]['prerequisites']:
            if p in needed:
                lines.append(f'{json.dumps(p)} -> {json.dumps(cid)};')
    return '\n'.join(lines + ['}'])

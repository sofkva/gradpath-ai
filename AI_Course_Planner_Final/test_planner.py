"""Run: python3 -m unittest -v test_planner.py (no Streamlit required)."""
import unittest
from copy import deepcopy

import planner_core as p


class PlannerTests(unittest.TestCase):
    def test_catalog_valid(self):
        self.assertTrue(p.validate_catalog(p.COURSES))

    def test_bad_catalog_missing_prerequisite(self):
        catalog = deepcopy(p.COURSES)
        catalog['CMPSC 132']['prerequisites'] = ['NOT PRESENT']
        with self.assertRaises(ValueError):
            p.validate_catalog(catalog)

    def test_bad_catalog_cycle(self):
        catalog = deepcopy(p.COURSES)
        catalog['CMPSC 131']['prerequisites'] = ['CMPSC 132']
        with self.assertRaisesRegex(ValueError, 'cycle'):
            p.validate_catalog(catalog)

    def test_bad_catalog_credit(self):
        catalog = deepcopy(p.COURSES)
        catalog['CMPSC 131']['credits'] = -2
        with self.assertRaises(ValueError):
            p.validate_catalog(catalog)

    def test_prerequisite_closure(self):
        self.assertEqual(p.required_closure(['CMPSC 465']),
                         {'CMPSC 131', 'CMPSC 132', 'CMPSC 360', 'CMPSC 465'})

    def test_course_level_difficulty_boundaries(self):
        for course, score in [('ENGL 15', 1), ('CAS 100A', 1), ('CMPSC 131', 1),
                              ('STAT 200', 2), ('CMPSC 465', 3)]:
            self.assertEqual(p.course_level_difficulty(course), score)

    def test_manual_difficulty_option(self):
        self.assertEqual(p.difficulty('CMPSC 131', mode='Manual estimates'), 2)
        self.assertEqual(p.difficulty('CMPSC 131', mode='Course level'), 1)

    def test_calendar_rollover(self):
        self.assertEqual(p.term_label('Fall', 2027, 1), 'Spring 2028')
        self.assertEqual(p.term_label('Spring', 2027, 1, True), 'Summer 2027')
        self.assertEqual(p.term_label('Fall', 2027, 1, True), 'Spring 2028')
        self.assertEqual(p.term_label('Summer', 2027, 1, True), 'Fall 2027')

    def test_deadline_offset(self):
        self.assertEqual(p.term_offset('Spring', 2027, 'Fall', 2028), 3)
        self.assertEqual(p.term_offset('Spring', 2027, 'Fall', 2028, True), 5)
        self.assertEqual(p.term_offset('Fall', 2027, 'Spring', 2027), -1)

    def test_bfs_and_astar_agree_for_caps_and_offerings(self):
        for cap in (6, 12, 15, 19, 24):
            for offerings in (False, True):
                with self.subTest(credit_cap=cap, offerings=offerings):
                    bfs = p.solve('BFS', [], p.DEFAULT_REQUIRED, cap, 'Spring', use_offerings=offerings)
                    astar = p.solve('A*', [], p.DEFAULT_REQUIRED, cap, 'Spring', use_offerings=offerings)
                    self.assertIsNotNone(bfs['plan'])
                    self.assertTrue(bfs['valid'] and astar['valid'])
                    self.assertEqual(len(bfs['plan']), len(astar['plan']))

    def test_every_algorithm_valid(self):
        for label, (alg, preference) in p.PLANNING_MODES.items():
            with self.subTest(algorithm=label):
                result = p.solve(alg, {'CMPSC 131'}, p.DEFAULT_REQUIRED, 12, 'Fall',
                                 use_offerings=True, workload_mode=preference)
                self.assertTrue(result['valid'])
                self.assertLessEqual(max(sum(p.COURSES[c]['credits'] for c in s)
                                         for s in result['plan']), 12)

    def test_difficulty_balancing_reduces_concentration(self):
        balanced = p.solve('UCS', [], p.DEFAULT_REQUIRED, 15, workload_mode='Balanced')
        lower = p.solve('UCS', [], p.DEFAULT_REQUIRED, 15, workload_mode='Lowest')
        self.assertTrue(balanced['valid'] and lower['valid'])
        self.assertLess(p.plan_metrics(lower['plan'])['concentration'],
                        p.plan_metrics(balanced['plan'])['concentration'])

    def test_postpone_causes_delay_on_prereq_chain(self):
        normal = p.solve('BFS', [], ['CMPSC 465'], 15)['plan']
        postponed = p.solve('BFS', [], ['CMPSC 465'], 15, earliest={'CMPSC 131': 1})
        self.assertEqual(len(normal), 4)
        self.assertEqual(len(postponed['plan']), 5)
        self.assertTrue(postponed['valid'])

    def test_deadline_capped_solution(self):
        impossible_in_three = p.solve('BFS', [], ['CMPSC 465'], 15, max_terms=3)
        possible_in_four = p.solve('BFS', [], ['CMPSC 465'], 15, max_terms=4)
        self.assertIsNone(impossible_in_three['plan'])
        self.assertTrue(possible_in_four['valid'])

    def test_completion_and_transfer(self):
        done = {'CMPSC 131', 'CMPSC 132', 'CMPSC 360', 'CMPSC 465'}
        result = p.solve('BFS', done, ['CMPSC 465'], 15)
        self.assertEqual(result['plan'], [])
        self.assertTrue(result['valid'])

    def test_eligibility_does_not_ignore_same_semester_prerequisites(self):
        self.assertFalse(p.valid_plan([('CMPSC 131', 'CMPSC 132')], set(),
                                      ['CMPSC 132'], 15, 'Spring'))
        self.assertTrue(p.valid_plan([('CMPSC 131',), ('CMPSC 132',)], set(),
                                     ['CMPSC 132'], 15, 'Spring'))

    def test_offerings_must_match(self):
        answer = p.solve('BFS', [], p.DEFAULT_REQUIRED, 15, 'Fall', use_offerings=True)
        self.assertTrue(answer['valid'])
        for i, semester in enumerate(answer['plan']):
            season = p.term_name('Fall', i)
            self.assertTrue(all(season in p.COURSES[c]['offerings'] for c in semester))

    def test_graph_and_bottleneck(self):
        required = p.required_closure(['CMPSC 465'])
        self.assertEqual(p.downstream('CMPSC 131', required),
                         {'CMPSC 132', 'CMPSC 360', 'CMPSC 465'})
        self.assertIn('digraph prerequisites', p.graph_dot(required, []))

    def test_question_answers(self):
        closure = p.required_closure(['CMPSC 465'])
        answer = p.ask_question('Can I take CMPSC131?', set(), closure, 'Spring')
        self.assertIn('eligible', answer)
        answer = p.ask_question('Can I take CMPSC 132?', set(), closure, 'Spring')
        self.assertIn('CMPSC 131', answer)
        answer = p.ask_question('What does CMPSC 132 unlock?', set(), closure, 'Spring')
        self.assertIn('CMPSC 465', answer)

    def test_no_plan_below_single_course_credit(self):
        answer = p.solve('BFS', [], ['MATH 140'], 3)
        self.assertIsNone(answer['plan'])

    def test_no_plan_when_max_terms_too_short(self):
        answer = p.solve('BFS', [], ['CMPSC 465'], 15, max_terms=2)
        self.assertIsNone(answer['plan'])

    def test_auto_replacement_respects_cap(self):
        options = ['CAS 100A', 'PSYCH 100']
        auto = p.auto_replacements(9, options, 12)
        self.assertEqual(len(auto), 1)
        self.assertEqual(sum(p.COURSES[c]['credits'] for c in auto) + 9, 12)
        self.assertEqual(p.auto_replacements(12, options, 15), ())

    def test_drop_replan_retakes_and_adds_gened(self):
        original = p.solve('BFS', [], p.DEFAULT_REQUIRED, 15)['plan']
        affected = 'CMPSC 131'
        before = p.replan_scenario(original, affected, 'Drop', [], p.DEFAULT_REQUIRED,
                                   15, 'Spring', 2027)
        self.assertIsNotNone(before['plan'])
        self.assertTrue(any(affected in term for term in before['plan'][1:]))
        self.assertNotIn(affected, before['plan'][0])
        self.assertTrue(before['candidates'])
        automatic = before['auto']
        if automatic:
            after = p.replan_scenario(original, affected, 'Drop', [], p.DEFAULT_REQUIRED,
                                      15, 'Spring', 2027, extra_courses=automatic)
            self.assertTrue(p.valid_plan(after['plan'], [], p.DEFAULT_REQUIRED, 15,
                                         'Spring', allowed_extras=set(automatic)))
            self.assertTrue(all(c in after['plan'][0] for c in automatic))

    def test_failed_course_is_retaken_later(self):
        original = p.solve('BFS', [], p.DEFAULT_REQUIRED, 15)['plan']
        response = p.replan_scenario(original, 'CMPSC 132', 'Fail', [],
                                     p.DEFAULT_REQUIRED, 15, 'Spring', 2027)
        self.assertIsNotNone(response['plan'])
        self.assertTrue(p.valid_plan(response['plan'], [], p.DEFAULT_REQUIRED, 15, 'Spring'))
        self.assertEqual(sum('CMPSC 132' in term for term in response['plan']), 1)
        self.assertGreaterEqual(len(response['plan']), len(original))

    def test_postpone_replan_still_fulfills_prerequisites(self):
        original = p.solve('BFS', [], ['CMPSC 465'], 15)['plan']
        response = p.replan_scenario(original, 'CMPSC 131', 'Postpone', [],
                                     ['CMPSC 465'], 15, 'Spring', 2027)
        self.assertTrue(p.valid_plan(response['plan'], [], ['CMPSC 465'], 15,
                                     'Spring', earliest={'CMPSC 131': 1}))

    def test_search_complexity_limit_is_explicit(self):
        catalog = deepcopy(p.COURSES)
        for i in range(15):
            catalog[f'TEST {200+i}'] = {
                'name': f'Independent {i}', 'credits': 3, 'prerequisites': [],
                'difficulty': 2, 'category': 'Major', 'offerings': ['Spring']
            }
        self.assertTrue(p.validate_catalog(catalog))
        required = [f'TEST {200+i}' for i in range(15)]
        result = p.solve('BFS', [], required, 24, catalog=catalog)
        self.assertIsNone(result['plan'])
        self.assertTrue(result['limited'])
        self.assertIn('14 courses', result['reason'])

    def test_bad_replacement_rejected(self):
        original = p.solve('BFS', [], p.DEFAULT_REQUIRED, 15)['plan']
        with self.assertRaises(ValueError):
            p.replan_scenario(original, 'CMPSC 131', 'Drop', [], p.DEFAULT_REQUIRED,
                              15, 'Spring', 2027, extra_courses=('CMPSC 465',))


if __name__ == '__main__':
    unittest.main(verbosity=2)

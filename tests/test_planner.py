import unittest

from planner_core import (
    COURSES,
    answer_question,
    approved_transfer_courses,
    bottleneck_scores,
    credit_advice,
    replacement_options,
    required_closure,
    scenario_replan,
    search_plan,
    term_at,
    transfer_candidates,
    validate_schedule,
)


class CoursePlannerTests(unittest.TestCase):

    def planning(self, method="BFS", required=None,
                 completed=(), max_credits=15,
                 start="Spring", summer=False):

        return search_plan(
            method,
            completed,
            required if required is not None else COURSES,
            max_credits,
            start,
            2027,
            summer
        )

    def test_all_algorithms(self):

        for method in ("BFS", "UCS", "A*"):

            result = self.planning(method)

            self.assertIsNotNone(result["schedule"])

            valid, problems = validate_schedule(
                result["schedule"],
                (),
                COURSES,
                15,
                "Spring",
                2027,
                False
            )

            self.assertTrue(valid, problems)

    def test_ucs_and_astar_cost(self):

        ucs = self.planning("UCS")
        astar = self.planning("A*")

        self.assertAlmostEqual(
            ucs["workload_cost"],
            astar["workload_cost"]
        )

    def test_prerequisite_closure(self):

        result = required_closure(
            ["CMPSC 465"],
            set(),
            COURSES
        )

        self.assertEqual(
            result,
            {
                "CMPSC 131",
                "CMPSC 132",
                "CMPSC 360",
                "CMPSC 465"
            }
        )

    def test_prerequisite_order(self):

        result = self.planning(
            required=["CMPSC 132"]
        )

        self.assertGreaterEqual(
            len(result["schedule"]),
            2
        )

        self.assertIn(
            "CMPSC 131",
            result["schedule"][0]
        )

    def test_course_availability(self):

        from planner_core import eligible_courses

        self.assertNotIn(
            "CMPSC 465",
            eligible_courses(
                {"CMPSC 360"},
                {"CMPSC 465"},
                "Spring"
            )
        )

        self.assertIn(
            "CMPSC 465",
            eligible_courses(
                {"CMPSC 360"},
                {"CMPSC 465"},
                "Fall"
            )
        )

    def test_semester_sequence(self):

        self.assertEqual(
            term_at("Fall", 2027, 1, False),
            ("Spring", 2028)
        )

        self.assertEqual(
            term_at("Spring", 2027, 1, True),
            ("Summer", 2027)
        )

    def test_bottleneck_scores(self):

        scores = dict(
            bottleneck_scores(COURSES)
        )

        self.assertGreater(
            scores["CMPSC 131"],
            scores["CMPSC 465"]
        )

    def test_drop_scenario(self):

        base = self.planning()

        i = next(
            i for i, semester in enumerate(base["schedule"])
            if "CMPSC 465" in semester
        )

        result = scenario_replan(
            base["schedule"],
            i,
            "CMPSC 465",
            "Drop",
            None,
            "BFS",
            (),
            COURSES,
            15,
            "Spring",
            2027,
            False
        )

        self.assertIsNotNone(result["schedule"])

        self.assertGreater(
            result["delta_semesters"],
            0
        )

    def test_failed_course(self):

        base = self.planning()

        i = next(
            i for i, semester in enumerate(base["schedule"])
            if "CMPSC 465" in semester
        )

        result = scenario_replan(
            base["schedule"],
            i,
            "CMPSC 465",
            "Fail",
            None,
            "BFS",
            (),
            COURSES,
            15,
            "Spring",
            2027,
            False
        )

        self.assertNotIn(
            "CMPSC 465",
            result["schedule"][i]
        )

        self.assertIn(
            "CMPSC 465",
            [
                c
                for semester in result["schedule"][i + 1:]
                for c in semester
            ]
        )

    def test_replacement_suggestions(self):

        alternatives = replacement_options(
            "CMPSC 131",
            set(),
            [],
            "Fall",
            6
        )

        self.assertIn("ENGL 15", alternatives)

    def test_transfer_matching(self):

        candidates = transfer_candidates(
            "Calculus II"
        )

        self.assertEqual(
            candidates[0],
            "MATH 141"
        )

    def test_only_confirmed_transfers_count(self):

        mappings = [
            {
                "equivalent": "MATH 141",
                "confirmed": False
            },
            {
                "equivalent": "CMPSC 131",
                "confirmed": True
            }
        ]

        self.assertEqual(
            approved_transfer_courses(mappings),
            {"CMPSC 131"}
        )

    def test_credit_advice(self):

        self.assertIn(
            "Below 12",
            credit_advice(9)
        )

        self.assertIn(
            "Above 19",
            credit_advice(21)
        )

    def test_question_answering(self):

        answer = answer_question(
            "When is CMPSC 465 offered?",
            set(),
            COURSES,
            "Spring",
            COURSES
        )

        self.assertIn("Fall", answer)


if __name__ == "__main__":
    unittest.main()
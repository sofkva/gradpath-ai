"""Optional offline smoke test for main.py UI control flow, no Streamlit needed.

The real browser interface must also be checked locally with Streamlit installed.
"""
import sys
import types
import unittest

class Widget(types.ModuleType):
    def __init__(self, scenario='Postpone'):
        super().__init__('streamlit')
        self.scenario = scenario
        self.session_state = {}
        self.sidebar = self
        self.errors = []
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def __getattr__(self, name):
        if name in ('container', 'expander', 'spinner'):
            return lambda *args, **kwargs: self
        if name in ('columns', 'tabs'):
            return lambda spec, **kwargs: [self for _ in (range(spec) if isinstance(spec,int) else spec)]
        if name == 'selectbox':
            return lambda label, options, index=0, **kw: list(options)[index]
        if name == 'multiselect':
            return lambda label, options, default=None, **kw: list(default or ())
        if name == 'radio':
            return lambda label, options, **kw: self.scenario
        if name == 'checkbox':
            return lambda label, value=False, **kw: value
        if name == 'slider':
            return lambda label, low, high, value=15, **kw: value
        if name == 'file_uploader':
            return lambda *a, **k: None
        if name == 'text_input':
            return lambda *a, **k: ''
        if name == 'button':
            return lambda label, **kw: label == 'Generate and compare plans'
        if name == 'error':
            return lambda msg, **kw: self.errors.append(str(msg))
        if name == 'metric':
            return lambda *a, **k: None
        return lambda *a, **k: None


class UISmokeTests(unittest.TestCase):
    def test_all_scenarios_render(self):
        for case in ('Postpone', 'Drop', 'Fail'):
            with self.subTest(case=case):
                mock = Widget(case)
                sys.modules['streamlit'] = mock
                import main
                main.st = mock
                main.main()
                self.assertFalse(mock.errors, mock.errors)
                self.assertIn('planner_results', mock.session_state)
                self.assertTrue(mock.session_state['planner_results']['Fastest (BFS)']['valid'])

if __name__ == '__main__':
    unittest.main(verbosity=2)

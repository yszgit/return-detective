from streamlit.testing.v1 import AppTest
from pathlib import Path
from rd import store
from tests.support import FixtureTest

class UIWorkflowTests(FixtureTest):
    def test_evidence_preview_renders_without_cloud_or_model_calls(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
        self.assertEqual(len(app.exception),0)
        next(button for button in app.button if button.label=="Preview evidence").click().run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertTrue(app.dataframe)
        self.assertEqual(store.snapshot()["cases"],{})

    def test_reject_button_updates_case_without_execution(self):
        case=store.open_case("Glindafied","Quality","2024-11-23","test","evidence")
        store.request_approval(case["case_id"],4,"Hold stock",{},"Quality")
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
        app.checkbox[0].check().run(timeout=30)
        next(button for button in app.button if button.label=="Reject proposal").click().run(timeout=30)
        self.assertEqual(len(app.exception),0)
        self.assertEqual(store.get_case(case["case_id"])["status"],"REJECTED")
        self.assertEqual(store.snapshot()["actions"],[])

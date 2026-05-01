import os
import unittest

try:
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover
    TestClient = None  # type: ignore[misc,assignment]


class TestComputerUseGuards(unittest.TestCase):
    def setUp(self) -> None:
        if TestClient is None:
            self.skipTest("fastapi non installé dans cet environnement")
        # Import ici pour que les tests manipulent env vars avant utilisation.
        from main import app  # type: ignore

        self.client = TestClient(app)

    def _invoke(self, action: dict, context_extra: dict | None = None) -> dict:
        ctx = {"desktop_action": action}
        if context_extra:
            ctx.update(context_extra)
        r = self.client.post("/invoke", json={"actor_id": "test", "text": "t", "context": ctx})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_disabled_by_default(self) -> None:
        os.environ.pop("LBG_DESKTOP_COMPUTER_USE_ENABLED", None)
        j = self._invoke({"kind": "click_xy", "x": 10, "y": 20})
        self.assertFalse(j.get("ok"))
        self.assertEqual(j.get("outcome"), "feature_disabled")

    def test_dry_run_does_not_require_pyautogui(self) -> None:
        os.environ["LBG_DESKTOP_COMPUTER_USE_ENABLED"] = "1"
        os.environ["LBG_DESKTOP_DRY_RUN"] = "1"
        j = self._invoke({"kind": "type_text", "text": "hello"})
        self.assertTrue(j.get("ok"))
        self.assertEqual(j.get("outcome"), "dry_run")

    def test_observe_requires_approval_when_configured(self) -> None:
        os.environ["LBG_DESKTOP_COMPUTER_USE_ENABLED"] = "1"
        os.environ["LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL"] = "1"
        os.environ["LBG_DESKTOP_APPROVAL_TOKEN"] = "SECRET"
        # même en dry-run, observe_screen est refusé sans token (confidentialité)
        os.environ["LBG_DESKTOP_DRY_RUN"] = "1"
        j = self._invoke({"kind": "observe_screen"})
        self.assertFalse(j.get("ok"))
        self.assertEqual(j.get("outcome"), "approval_denied")


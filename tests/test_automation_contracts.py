from __future__ import annotations

import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from actions.open_app import _normalize
from actions.game_updater import _find_game_executable
from core.guardrails import resolve_safe_path
from core.guardrails import validate_command
from main import _append_transcript
from actions.screen_processor import OCRText, wait_for_text
from actions.browser_control import _normalize_url
from actions.send_message import _smart_click_element
from core.intent_router import classify_target, route_tool
from core.prompt_router import PROMPT_REPOSITORY_URL, PromptRouter
from actions.file_controller import _file_memory_key, _resolve_file_target, read_file
from actions.computer_control import _screen_find
from actions.youtube_video import _handle_play
from core.accessibility import AccessibilityController


class AutomationContracts(unittest.TestCase):
    def test_accessibility_screen_reader_uses_injected_speech_backend(self):
        spoken = []
        controller = AccessibilityController(
            speech=type("Speech", (), {"speak": lambda self, text: spoken.append(text)})(),
            ocr=lambda **kwargs: "Testo visibile",
        )
        self.assertEqual(controller.read_screen(), "Testo visibile")
        self.assertEqual(spoken, ["Analisi dello schermo in corso.", "Testo visibile"])

    def test_accessibility_empty_screen_is_reported(self):
        spoken = []
        controller = AccessibilityController(
            speech=type("Speech", (), {"speak": lambda self, text: spoken.append(text)})(),
            ocr=lambda **kwargs: "",
        )
        self.assertEqual(controller.read_screen(), "")
        self.assertEqual(spoken[-1], "Nessun testo rilevato sullo schermo.")

    def test_accessibility_hotkeys_are_opt_in_and_removable(self):
        class FakeKeyboard:
            def __init__(self):
                self.added = []
                self.removed = []

            def add_hotkey(self, combination, callback):
                self.added.append((combination, callback))

            def remove_hotkey(self, combination):
                self.removed.append(combination)

        fake = FakeKeyboard()
        controller = AccessibilityController()
        with patch.dict("sys.modules", {"keyboard": fake}):
            self.assertIsNone(controller._keyboard)
            controller.start_hotkeys()
            controller.stop_hotkeys()
        self.assertEqual([item[0] for item in fake.added], ["ctrl+alt+r", "ctrl+alt+s"])
        self.assertEqual(fake.removed, ["ctrl+alt+r", "ctrl+alt+s"])

    @patch("pyautogui.write")
    @patch("pyautogui.click")
    @patch("actions.screen_processor.find_text")
    def test_accessibility_click_and_type_requires_ocr_match(self, find_text, click, write):
        find_text.return_value = type("Match", (), {"center": (120, 240)})()
        controller = AccessibilityController(ocr=lambda **kwargs: "unused")
        self.assertTrue(controller.click_and_type("Search", "hello"))
        click.assert_called_once_with(120, 240)
        write.assert_called_once_with("hello")

    @patch("actions.screen_processor.find_text", return_value=None)
    @patch("pyautogui.click")
    def test_accessibility_click_and_type_does_not_click_without_match(self, click, find_text):
        controller = AccessibilityController(ocr=lambda **kwargs: "unused")
        self.assertFalse(controller.click_and_type("Missing", "hello"))
        click.assert_not_called()

    def test_credential_trigger_is_safe_and_explicit(self):
        root = Path(__file__).resolve().parents[1]
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")
        rules = (root / "regole e vincoli" / "regole e vincoli.md").read_text(encoding="utf-8")
        for trigger in ("duusuu", "dusu", "dusuu"):
            self.assertIn(trigger, prompt)
            self.assertIn(trigger, rules)
        self.assertIn("must NEVER authorize storing passwords", prompt)
        self.assertIn("Non autorizzano mai il salvataggio", rules)

    @patch("actions.youtube_video._open_url", return_value=True)
    @patch("actions.youtube_video._scrape_first_video_url", return_value="https://www.youtube.com/watch?v=abcdefghijk")
    def test_youtube_play_opens_first_result(self, scrape, open_url):
        result = _handle_play({"query": "jazz anni 40 retro"}, None)
        self.assertIn("https://www.youtube.com/watch?v=abcdefghijk", result)
        open_url.assert_called_once_with("https://www.youtube.com/watch?v=abcdefghijk")

    @patch("actions.youtube_video._open_url", return_value=True)
    @patch("actions.youtube_video._scrape_first_video_url", return_value=None)
    def test_youtube_failure_returns_targeted_search_url(self, scrape, open_url):
        result = _handle_play({"query": "jazz anni 40 retro"}, None)
        self.assertIn("youtube.com/results?search_query=jazz+anni+40+retro", result)
        self.assertNotIn("youtube.com\"", result)

    def test_security_guard_allows_launcher_commands(self):
        validate_command(["steam.exe"])
        validate_command(["netsh", "advfirewall"])
        validate_command(["schtasks", "/Query"])
        validate_command(["xdg-open", "https://example.com"])
        with self.assertRaises(PermissionError):
            validate_command(["powershell", "-Command", "Remove-Item", "-Recurse", "C:\\temp"])

    def test_security_guard_allows_only_game_library_executables(self):
        validate_command([r"C:\Program Files (x86)\Steam\steamapps\common\Victoria 3\binaries\win64\v3.exe"])
        with self.assertRaises(PermissionError):
            validate_command([r"C:\Users\Public\Downloads\unknown.exe"])

    def test_dynamic_prompt_modes(self):
        router = PromptRouter()
        self.assertEqual(router.classify("debug python script error"), "developer_mode")
        self.assertEqual(router.classify("analizza la strategia del gioco"), "strategic_mode")
        self.assertEqual(router.classify("apri Steam"), "quick_command")
        self.assertEqual(router.classify("spiegami come funziona questo sistema"), "standard_assistant")

    def test_prompt_repository_reference_is_configured(self):
        self.assertEqual(PROMPT_REPOSITORY_URL, "https://github.com/ilfenomeno-gif/repo-prompt")

    def test_repository_framework_is_in_system_prompt(self):
        root = Path(__file__).resolve().parents[1]
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("[UNIVERSAL AI FRAMEWORK]", prompt)
        self.assertIn("TOOL SELECTION", prompt)
        self.assertIn("VERIFICATION", prompt)
        self.assertIn("Do not reveal private chain-of-thought", prompt)

    def test_global_execution_directive_requires_end_to_end_feedback(self):
        root = Path(__file__).resolve().parents[1]
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("[GLOBAL EXECUTION DIRECTIVE]", prompt)
        self.assertIn("Complete the user's requested action end-to-end", prompt)
        self.assertIn("Never report success for a partial action", prompt)
        self.assertIn("closest functional fallback", prompt)

    def test_dynamic_prompt_file_fallback(self):
        router = PromptRouter(Path("C:/path/that/does/not/exist"))
        instruction = router.instruction_for("debug python")
        self.assertIn("mode=developer_mode", instruction)
        self.assertIn("Do not expose hidden chain-of-thought", instruction)

    @patch("actions.screen_processor.find_text")
    def test_screen_find_prefers_local_ocr(self, find_text):
        find_text.return_value = type("Match", (), {"center": (321, 222)})()
        with patch("actions.computer_control._get_api_key") as api_key:
            self.assertEqual(_screen_find("Play button"), (321, 222))
            api_key.assert_not_called()

    @patch("actions.game_updater.update_memory")
    def test_steam_manifest_resolves_local_executable(self, remember):
        with tempfile.TemporaryDirectory() as folder:
            steam = Path(folder)
            manifest_dir = steam / "steamapps"
            game_root = steam / "common" / "Victoria 3"
            executable = game_root / "binaries" / "win64" / "v3.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"test")
            manifest_dir.mkdir(exist_ok=True)
            (manifest_dir / "appmanifest_529340.acf").write_text(
                '"appid" "529340"\n"name" "Victoria 3"\n"installdir" "Victoria 3"',
                encoding="utf-8",
            )
            self.assertEqual(_find_game_executable("Victoria 3", steam), executable.resolve())
            remember.assert_called_once()

    def test_file_discovery_indexes_and_reuses_exact_path(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "report.txt"
            source.write_text("indexed", encoding="utf-8")
            memory = {"notes": {}}
            with patch("actions.file_controller.load_memory", return_value=memory), \
                    patch("actions.file_controller.update_memory") as save:
                self.assertEqual(read_file(str(source)), "indexed")
                save.assert_called_once()
                save_args = save.call_args.args[0]
                self.assertEqual(
                    save_args["notes"][_file_memory_key("report.txt")]["value"],
                    str(source.resolve()),
                )

            remembered = {"notes": {_file_memory_key("report.txt"): {"value": str(source)}}}
            with patch("actions.file_controller.load_memory", return_value=remembered):
                self.assertEqual(_resolve_file_target("report.txt"), source.resolve())

    def test_ambiguous_game_or_file_is_blocked(self):
        decision = classify_target("Victoria", "apri Victoria")
        self.assertTrue(decision.blocked)
        self.assertIn("gioco", decision.clarification)
        self.assertIn("file", decision.clarification)

    @patch("core.intent_router._save_association")
    def test_explicit_game_routes_to_launcher(self, save_association):
        decision = route_tool("open_app", {"app_name": "Victoria 3"}, "apri il gioco Victoria 3")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.category, "game")
        self.assertEqual(decision.launcher, "steam")
        save_association.assert_called_once_with("Victoria 3", "game", "launcher")

    @patch("core.intent_router._save_association")
    def test_game_query_cannot_fall_through_to_web_search(self, save_association):
        decision = route_tool("web_search", {"query": "Victoria 3"}, "cerca il gioco Victoria 3")
        self.assertTrue(decision.blocked)

    @patch("core.intent_router._save_association")
    def test_explicit_steam_command_prioritizes_launcher_over_files(self, save_association):
        request = "Apri Victoria 3 su Steam"
        open_decision = route_tool("game_updater", {"game_name": "Victoria 3"}, request)
        file_decision = route_tool("file_processor", {"file_path": "Victoria 3"}, request)
        self.assertEqual(open_decision.category, "game")
        self.assertEqual(open_decision.launcher, "steam")
        self.assertTrue(file_decision.blocked)

    @patch("core.intent_router._save_association")
    def test_file_controller_name_cannot_bypass_game_block(self, save_association):
        decision = route_tool(
            "file_controller",
            {"path": "home", "name": "Victoria"},
            "apri Victoria",
        )
        self.assertTrue(decision.blocked)
    def test_windows_environment_paths_are_expanded(self):
        with patch.dict("os.environ", {"JARVIS_TEST_HOME": "C:\\Users\\Test User"}):
            self.assertEqual(
                str(resolve_safe_path(r"%JARVIS_TEST_HOME%\\file.txt")),
                r"C:\Users\Test User\file.txt",
            )

    def test_transcription_updates_are_merged_without_echo(self):
        buffer = []
        for fragment in ("Buongiorno", "Buongiorno Signore", "Buongiorno Signore"):
            _append_transcript(buffer, fragment)
        self.assertEqual(buffer, ["Buongiorno Signore"])

    def test_opinion_policy_is_explicit(self):
        root = Path(__file__).resolve().parents[1]
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")
        rules = (root / "regole e vincoli" / "regole e vincoli.md").read_text(encoding="utf-8")
        self.assertIn("Opinions:", prompt)
        self.assertIn("Opinioni:", rules)

    def test_formal_language_contract_is_consistent(self):
        root = Path(__file__).resolve().parents[1]
        prompt = (root / "core" / "prompt.txt").read_text(encoding="utf-8")
        rules = (root / "regole e vincoli" / "regole e vincoli.md").read_text(encoding="utf-8")
        main = (root / "main.py").read_text(encoding="utf-8")
        self.assertIn("Always address the user formally", prompt)
        self.assertIn("usare sempre forma formale", rules)
        self.assertIn("formal service greeting", main)
        self.assertNotIn("Never use formal language", prompt)
        self.assertNotIn("mai formale", rules)

    def test_known_games_use_interactive_steam_library_flow(self):
        self.assertEqual(_normalize("Victoria 3"), "steam://local/victoria%203")
        self.assertEqual(_normalize("GeoGuessr"), "steam://local/GeoGuessr")
        self.assertEqual(_normalize("Gio Gasser"), "steam://local/GeoGuessr")

    def test_unknown_app_is_not_redirected_to_steam(self):
        self.assertEqual(_normalize("Some Unknown App"), "Some Unknown App")

    def test_ocr_box_returns_absolute_center(self):
        item = OCRText("Play", 96.0, (100, 200, 80, 40))
        self.assertEqual(item.center, (140, 220))

    def test_ocr_wait_is_fast_when_backend_is_unavailable(self):
        started = time.perf_counter()
        with patch("actions.screen_processor._TESSERACT", False):
            self.assertIsNone(wait_for_text("Play", timeout=2.0))
        self.assertLess(time.perf_counter() - started, 0.25)

    def test_message_flow_does_not_claim_click_without_grounding(self):
        with patch("actions.send_message._VISUAL_GROUNDING", False):
            self.assertFalse(_smart_click_element("message input field"))

    def test_message_fallback_is_explicit_when_supplied(self):
        fallback_called = []
        with patch("actions.send_message._VISUAL_GROUNDING", False):
            self.assertTrue(
                _smart_click_element(
                    "search bar", fallback_fn=lambda: fallback_called.append(True)
                )
            )
        self.assertEqual(fallback_called, [True])

    def test_browser_url_normalization(self):
        self.assertEqual(_normalize_url("example.com"), "https://example.com")
        self.assertEqual(_normalize_url("https://example.com/path"), "https://example.com/path")


if __name__ == "__main__":
    unittest.main()

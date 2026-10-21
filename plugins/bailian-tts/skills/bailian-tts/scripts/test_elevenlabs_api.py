"""ElevenLabs 密钥、音色分页、收藏隔离及生成请求的离线测试。"""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import base64
import sys
import elevenlabs_api as eleven


class ElevenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.keys = patch.object(eleven, "KEY_PATH", self.tmp.name + "/key")
        self.favs = patch.object(eleven, "FAV_PATH", self.tmp.name + "/favs.json")
        self.env = patch.dict(os.environ, {}, clear=True)
        for p in (self.keys, self.favs, self.env):
            p.start()
            self.addCleanup(p.stop)

    def test_key_validation_preserves_previous_and_masks_key(self):
        old = "old-key-1234567890123456"
        eleven.atomic_write(eleven.KEY_PATH, old)
        with patch.object(eleven, "list_voices", side_effect=ValueError("无权限")):
            with self.assertRaises(ValueError):
                eleven.save_key("new-key-1234567890123456")
        self.assertEqual(eleven.read_key(), old)
        self.assertNotIn(old, json.dumps(eleven.key_status()))
        self.assertEqual(os.stat(eleven.KEY_PATH).st_mode & 0o777, 0o600)
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "env-key-1234567890123456"}):
            with self.assertRaisesRegex(ValueError, "环境变量"):
                eleven.save_key("new-key-1234567890123456")

    def test_voices_pagination_and_favorites(self):
        pages = [{"voices": [{"voice_id": "a", "name": eleven.PREFERRED[0], "labels": {"gender": "male"}, "description": "温暖旁白"}], "has_more": True, "next_page_token": "page2"},
                 {"voices": [{"voice_id": "b", "name": eleven.PREFERRED[1]}, {"voice_id": "c", "name": "Other"}], "has_more": False}]
        with patch.object(eleven, "request", side_effect=pages) as request:
            voices = eleven.list_voices()
            self.assertIn("next_page_token=page2", request.call_args.args[0])
        self.assertEqual(voices[0]["gender"], "male")
        self.assertEqual(voices[0]["description"], "温暖旁白")
        self.assertEqual(voices[1]["gender"], "")
        self.assertEqual([v["voice"] for v in eleven.seed_favorites(voices)], ["a", "b"])
        eleven.update_favorite("b", eleven.PREFERRED[1], "default")
        self.assertEqual(eleven.favorites()[0]["voice"], "b")
        eleven.update_favorite("a", "", "rm")
        self.assertEqual(eleven.seed_favorites(voices), [voices[1]])

    def test_v4_contract_returns_audio_without_bailian_credentials(self):
        with patch.object(eleven, "read_key", return_value="eleven-test-key"), patch("urllib.request.urlopen", return_value=io.BytesIO(b"mp3-audio")) as call:
            self.assertEqual(eleven.synth("你好", "voice123"), b"mp3-audio")
            request = call.call_args.args[0]
            self.assertEqual(request.get_header("Xi-api-key"), "eleven-test-key")
            self.assertIsNone(request.get_header("Authorization"))
            data = json.loads(request.data)
            self.assertEqual(data, {"model_id": "eleven_v4", "inputs": [{"text": "你好", "voice_id": "voice123"}]})
            self.assertIn("/v1/text-to-dialogue?", request.full_url)
        for voice, text in (("../bad", "你好"), ("voice123", "字" * 2001), ("", "你好")):
            with self.assertRaises(ValueError):
                eleven.synth(text, voice)

    def test_free_plan_api_eligibility(self):
        cases = [
            ({"category": "premade"}, "free_plan"),
            ({"category": "professional", "sharing": {"free_users_allowed": True}, "is_owner": False}, "paid_plan"),
            ({"category": "premade", "available_for_tiers": ["creator"]}, "paid_plan"),
            ({"category": "premade", "available_for_tiers": ["free", "creator"]}, "free_plan"),
            ({"category": "generated"}, "unknown"),
            ({"category": "professional", "sharing": {"free_users_allowed": True}, "is_owner": True}, "unknown"),
            ({}, "unknown"),
        ]
        for voice, expected in cases:
            with self.subTest(voice=voice):
                self.assertEqual(eleven.api_access(voice), expected)

    def test_existing_favorite_metadata_refreshes_without_restoring_removed_voices(self):
        eleven.save_favorites([{"voice": "roger", "name": "Roger"}])
        voices = [{"voice": "roger", "name": "Roger", "api_access": "free_plan"},
                  {"voice": "other", "name": eleven.PREFERRED[0], "api_access": "paid_plan"}]
        self.assertEqual(eleven.seed_favorites(voices), [voices[0]])
        self.assertEqual(eleven.favorites(), [dict(voices[0], trait_zh="暂无中文描述")])

    def test_chinese_traits_preserve_voice_names(self):
        self.assertEqual(eleven.trait_zh("Alice - Clear, Engaging Educator"), "清晰、生动的教学声线")
        self.assertEqual(eleven.trait_zh("Roger - Laid-Back, Casual, Resonant"), "松弛、自然、浑厚")
        self.assertEqual(eleven.trait_zh("未知音色 - 温柔女声"), "温柔女声")
        self.assertEqual(eleven.trait_zh("New voice - Unknown traits"), "暂无中文描述")
        eleven.save_favorites([{"voice": "roger", "name": "Roger - Laid-Back, Casual, Resonant"}])
        self.assertEqual(eleven.favorites()[0]["trait_zh"], "松弛、自然、浑厚")
        self.assertEqual(eleven.favorites()[0]["name"], "Roger - Laid-Back, Casual, Resonant")

    def test_turbo_websocket_contract_and_audio_assembly(self):
        ws = MagicMock()
        ws.recv.side_effect = [json.dumps({"audio": base64.b64encode(b"part1").decode()}),
                               json.dumps({"is_final_audio_for_turn": True}),
                               json.dumps({"audio": base64.b64encode(b"part2").decode()}),
                               json.dumps({"is_final": True})]
        connect = MagicMock(return_value=ws)
        with patch.dict(sys.modules, {"websocket": SimpleNamespace(create_connection=connect)}), patch.object(eleven, "read_key", return_value="test-key"), patch.object(eleven, "request") as http:
            self.assertEqual(eleven.synth("你好", "voice123", eleven.TURBO_MODEL), b"part1part2")
            self.assertIn("model_id=eleven_v4_turbo", connect.call_args.args[0])
            self.assertEqual(connect.call_args.kwargs["header"], {"xi-api-key": "test-key"})
            sent = [json.loads(call.args[0]) for call in ws.send.call_args_list]
            self.assertEqual(sent, [{"voices": ["voice123"]}, {"inputs": [{"text": "你好", "voice_id": "voice123"}]}, {"close_socket": True}])
            ws.close.assert_called_once()
            http.assert_not_called()

    def test_turbo_errors_do_not_retry_or_return_partial_audio(self):
        for messages in ([json.dumps({"audio": "cGFydA=="}), ""], [json.dumps({"error": "denied", "message": "test-key"})], [json.dumps({"is_final": True})]):
            with self.subTest(messages=messages):
                ws=MagicMock(); ws.recv.side_effect=messages
                connect=MagicMock(return_value=ws)
                with patch.dict(sys.modules, {"websocket": SimpleNamespace(create_connection=connect)}), patch.object(eleven, "read_key", return_value="test-key"):
                    with self.assertRaises(ValueError) as raised:
                        eleven.synth("你好", "voice123", eleven.TURBO_MODEL)
                    self.assertNotIn("test-key", str(raised.exception))
                    connect.assert_called_once()
                    ws.close.assert_called_once()

    def test_http_errors_redact_key(self):
        from urllib.error import HTTPError
        error = HTTPError("https://api.elevenlabs.io", 401, "Unauthorized", None,
                          io.BytesIO(json.dumps({"detail": {"message": "invalid secret-key"}}).encode()))
        with patch.object(eleven, "read_key", return_value="secret-key"), patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(ValueError, "HTTP 401") as raised:
                eleven.request("/v2/voices")
            self.assertNotIn("secret-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

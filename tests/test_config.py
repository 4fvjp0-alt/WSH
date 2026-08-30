"""장부 저장 위치 설정.

OneDrive·iCloud 같은 동기화 폴더로 장부를 옮겨 두고 매번 --data 를 치지 않게 하는 기능.
"""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from helpers import *  # noqa: F401,F403
from settle import store
from settle.cli import main


class ConfigCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.home = root / "home" / ".travel-settle"
        self.home.mkdir(parents=True)
        self.cloud = root / "OneDrive" / "여행"
        # 실제 홈 디렉터리를 건드리지 않도록 갈아끼운다
        self._saved = (store.HOME_DIR, store.DEFAULT_PATH, store.CONFIG_PATH)
        store.HOME_DIR = self.home
        store.DEFAULT_PATH = self.home / "data.json"
        store.CONFIG_PATH = self.home / "config.json"
        self._env = os.environ.pop(store.ENV_PATH, None)

    def tearDown(self):
        store.HOME_DIR, store.DEFAULT_PATH, store.CONFIG_PATH = self._saved
        if self._env is not None:
            os.environ[store.ENV_PATH] = self._env
        self.dir.cleanup()

    def run_cli(self, *args, expect: int = 0) -> str:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        self.assertEqual(code, expect, err.getvalue() or out.getvalue())
        return out.getvalue() + err.getvalue()

    def seed(self, path: Path):
        self.run_cli("--data", str(path), "trip", "new", "제주")
        self.run_cli("--data", str(path), "member", "add", "민수", "지영")
        self.run_cli("--data", str(path), "expense", "add",
                     "--title", "밥", "--amount", "30000", "--payer", "민수")


class TestResolution(ConfigCase):
    def test_default_when_nothing_set(self):
        self.assertEqual(store.default_path(), self.home / "data.json")

    def test_config_file_wins_over_default(self):
        store.save_config({"data_path": str(self.cloud / "data.json")})
        self.assertEqual(store.default_path(), self.cloud / "data.json")

    def test_env_wins_over_config(self):
        store.save_config({"data_path": str(self.cloud / "data.json")})
        os.environ[store.ENV_PATH] = str(self.home / "override.json")
        try:
            self.assertEqual(store.default_path(), self.home / "override.json")
        finally:
            os.environ.pop(store.ENV_PATH)

    def test_broken_config_does_not_break_startup(self):
        store.CONFIG_PATH.write_text("{ 망가진 json", encoding="utf-8")
        self.assertEqual(store.load_config(), {})
        self.assertEqual(store.default_path(), self.home / "data.json")

    def test_user_expansion(self):
        store.save_config({"data_path": "~/somewhere/data.json"})
        self.assertEqual(store.default_path(), Path.home() / "somewhere" / "data.json")


class TestMove(ConfigCase):
    def test_move_ledger_and_images_to_cloud_folder(self):
        source = self.home / "data.json"
        self.seed(source)
        images = self.home / "images"
        images.mkdir()
        (images / "capture.png").write_bytes(b"fake")

        output = self.run_cli("config", str(self.cloud), "--move")
        self.assertIn("data.json", output)
        target = self.cloud / "data.json"
        self.assertTrue(target.exists())
        self.assertFalse(source.exists())
        self.assertTrue((self.cloud / "images" / "capture.png").exists())
        self.assertFalse(images.exists(), "옮긴 뒤 빈 images 폴더가 남았습니다")

        # 이제 경로를 주지 않아도 옮긴 장부를 쓴다
        self.assertEqual(store.default_path(), target)
        self.assertIn("30,000원", self.run_cli("settle", "--brief"))

    def test_folder_argument_gets_a_data_json(self):
        self.run_cli("config", str(self.cloud))
        self.assertEqual(store.default_path(), self.cloud / "data.json")

    def test_explicit_filename_is_kept(self):
        target = self.cloud / "제주정산.json"
        self.run_cli("config", str(target))
        self.assertEqual(store.default_path(), target)

    def test_move_refuses_to_overwrite_without_force(self):
        self.seed(self.home / "data.json")
        self.cloud.mkdir(parents=True)
        (self.cloud / "data.json").write_text('{"version":1,"trips":[]}', encoding="utf-8")
        output = self.run_cli("config", str(self.cloud), "--move", expect=1)
        self.assertIn("이미 장부가 있습니다", output)
        self.assertTrue((self.home / "data.json").exists())    # 원본은 그대로

    def test_move_with_force_overwrites(self):
        self.seed(self.home / "data.json")
        self.cloud.mkdir(parents=True)
        (self.cloud / "data.json").write_text('{"version":1,"trips":[]}', encoding="utf-8")
        self.run_cli("config", str(self.cloud), "--move", "--force")
        self.assertIn("30,000원", self.run_cli("settle", "--brief"))

    def test_setting_location_without_move_leaves_files_alone(self):
        self.seed(self.home / "data.json")
        self.run_cli("config", str(self.cloud))
        self.assertTrue((self.home / "data.json").exists())
        self.assertFalse((self.cloud / "data.json").exists())

    def test_reset_returns_to_home(self):
        self.run_cli("config", str(self.cloud))
        self.run_cli("config", "--reset")
        self.assertEqual(store.default_path(), self.home / "data.json")


class TestShow(ConfigCase):
    def test_shows_active_path_and_priority(self):
        output = self.run_cli("config")
        self.assertIn(str(self.home / "data.json"), output)
        self.assertIn("우선순위", output)

    def test_warns_when_env_var_overrides_the_setting(self):
        os.environ[store.ENV_PATH] = str(self.home / "override.json")
        try:
            output = self.run_cli("config", str(self.cloud))
            self.assertIn("환경변수", output)
        finally:
            os.environ.pop(store.ENV_PATH)

    def test_config_does_not_write_a_ledger(self):
        self.run_cli("config")
        self.assertFalse((self.home / "data.json").exists())


class TestImagesFollowTheLedger(ConfigCase):
    def test_images_dir_sits_next_to_the_ledger(self):
        self.run_cli("config", str(self.cloud))
        self.assertEqual(store.images_dir(), self.cloud / "images")


if __name__ == "__main__":
    unittest.main()

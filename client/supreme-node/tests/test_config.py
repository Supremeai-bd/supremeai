"""
Tests for config loading + validation (daemon.load_config).
MESH-3 #941 — Phase A
"""
import os
import sys
import tempfile
import unittest

# Make client/supreme-node importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daemon import (  # noqa: E402
    load_config,
    ConfigError,
    REQUIRED_KEYS,
    VALID_NODE_TYPES,
    VALID_ROLES,
)


VALID_CONFIG_YAML = """
node_id: pc-1-dev-rig
node_type: local_pc
role: coder
capabilities:
  - file_edit
  - pytest
  - git_push
tower_url: https://supremeai-mcp-tower.onrender.com
tower_ws_url: wss://supremeai-mcp-tower.onrender.com/ws/node
"""


class _BaseConfigTest(unittest.TestCase):
    def _write_config(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".yaml", text=True)
        with os.fdopen(fd, "w") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path


class TestValidConfig(_BaseConfigTest):
    def test_loads_valid_config(self):
        path = self._write_config(VALID_CONFIG_YAML)
        cfg = load_config(path)
        self.assertEqual(cfg["node_id"], "pc-1-dev-rig")
        self.assertEqual(cfg["node_type"], "local_pc")
        self.assertEqual(cfg["role"], "coder")
        self.assertEqual(cfg["capabilities"], ["file_edit", "pytest", "git_push"])
        self.assertEqual(cfg["tower_url"], "https://supremeai-mcp-tower.onrender.com")

    def test_defaults_populated(self):
        path = self._write_config(VALID_CONFIG_YAML)
        cfg = load_config(path)
        # defaults set by load_config
        self.assertEqual(cfg["heartbeat_path"], "/api/v1/nodes/heartbeat")
        self.assertEqual(cfg["heartbeat_interval"], 60)
        self.assertEqual(cfg["reconnect_backoff_base"], 2)
        self.assertEqual(cfg["reconnect_backoff_max"], 300)
        self.assertEqual(cfg["task_timeout_seconds"], 600)
        self.assertEqual(cfg["log_level"], "INFO")

    def test_workspace_dir_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = os.path.join(tmpdir, "new_ws")
            content = VALID_CONFIG_YAML + f"workspace_dir: {ws}\n"
            path = self._write_config(content)
            cfg = load_config(path)
            self.assertTrue(os.path.isdir(cfg["workspace_dir"]))


class TestConfigValidation(_BaseConfigTest):
    def test_missing_required_key_raises(self):
        # missing node_id
        bad = "\n".join(
            line for line in VALID_CONFIG_YAML.splitlines()
            if not line.startswith("node_id:")
        )
        path = self._write_config(bad)
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_invalid_node_type_raises(self):
        bad = VALID_CONFIG_YAML.replace("local_pc", "rocket")
        path = self._write_config(bad)
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_invalid_role_raises(self):
        bad = VALID_CONFIG_YAML.replace("coder", "magician")
        path = self._write_config(bad)
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_missing_file_raises(self):
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/path/to/config.yaml")

    def test_non_dict_yaml_raises(self):
        path = self._write_config("- just\n- a\n- list\n")
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_empty_yaml_raises(self):
        path = self._write_config("")
        with self.assertRaises(ConfigError):
            load_config(path)


class TestEnvOverride(_BaseConfigTest):
    def test_env_tower_auth_token_overrides_config(self):
        path = self._write_config(
            VALID_CONFIG_YAML + 'tower_auth_token: "from-config"\n'
        )
        old = os.environ.get("TOWER_AUTH_TOKEN")
        os.environ["TOWER_AUTH_TOKEN"] = "from-env"
        try:
            cfg = load_config(path)
            self.assertEqual(cfg["tower_auth_token"], "from-env")
        finally:
            if old is None:
                os.environ.pop("TOWER_AUTH_TOKEN", None)
            else:
                os.environ["TOWER_AUTH_TOKEN"] = old


class TestValidationConstants(unittest.TestCase):
    def test_required_keys_present(self):
        for key in ("node_id", "node_type", "role", "capabilities",
                    "tower_url", "tower_ws_url"):
            self.assertIn(key, REQUIRED_KEYS)

    def test_valid_node_types(self):
        for nt in ("local_pc", "cloud_agent", "web_ai",
                   "edge_device", "external_mcp"):
            self.assertIn(nt, VALID_NODE_TYPES)

    def test_valid_roles(self):
        for r in ("planner", "coder", "tester", "gate", "observer"):
            self.assertIn(r, VALID_ROLES)


if __name__ == "__main__":
    unittest.main()

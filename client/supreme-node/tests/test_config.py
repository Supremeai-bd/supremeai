"""
Tests for config loading + validation (daemon.load_config).
MESH-3 #941 — Phase A; endpoint-contract alignment #2255.
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
    CONTROL_PLANE_URL_KEYS,
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
backend_url: https://api.supremeai.example
tower_ws_url: ""
"""

LEGACY_CONFIG_YAML = """
node_id: pc-1-dev-rig
node_type: local_pc
role: coder
capabilities:
  - file_edit
  - pytest
  - git_push
tower_url: https://api.supremeai.example
tower_ws_url: ""
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
        self.assertEqual(cfg["backend_url"], "https://api.supremeai.example")

    def test_legacy_tower_url_alias_resolves(self):
        """#2255: legacy `tower_url` configs still load; backend_url derived."""
        path = self._write_config(LEGACY_CONFIG_YAML)
        cfg = load_config(path)
        self.assertEqual(cfg["backend_url"], "https://api.supremeai.example")
        self.assertEqual(cfg["tower_url"], "https://api.supremeai.example")

    def test_missing_control_plane_url_raises(self):
        """#2255: neither backend_url nor tower_url -> actionable ConfigError."""
        bad = "\n".join(
            line for line in VALID_CONFIG_YAML.splitlines()
            if not line.startswith("backend_url:")
        )
        path = self._write_config(bad)
        with self.assertRaises(ConfigError) as ctx:
            load_config(path)
        self.assertIn("backend_url", str(ctx.exception))

    def test_env_interpolation_of_backend_url(self):
        """#2255: the template advertises ${VAR} support — it must work."""
        old = os.environ.get("SUPREME_TEST_BACKEND_URL")
        os.environ["SUPREME_TEST_BACKEND_URL"] = "https://env.example"
        try:
            path = self._write_config(
                VALID_CONFIG_YAML.replace(
                    "https://api.supremeai.example", "${SUPREME_TEST_BACKEND_URL}"
                )
            )
            cfg = load_config(path)
            self.assertEqual(cfg["backend_url"], "https://env.example")
        finally:
            if old is None:
                os.environ.pop("SUPREME_TEST_BACKEND_URL", None)
            else:
                os.environ["SUPREME_TEST_BACKEND_URL"] = old

    def test_unset_env_var_expands_empty(self):
        os.environ.pop("SUPREME_DEFINITELY_UNSET_XYZ", None)
        path = self._write_config(
            VALID_CONFIG_YAML.replace(
                "https://api.supremeai.example", "${SUPREME_DEFINITELY_UNSET_XYZ}"
            )
        )
        # empty url is falsy -> falls through to legacy key (also empty) ->
        # ConfigError is the honest fail-fast outcome; no garbage URL is built.
        with self.assertRaises(ConfigError):
            load_config(path)

    def test_empty_ws_url_loads(self):
        """Empty tower_ws_url is the default heartbeat-only mode (#2255)."""
        path = self._write_config(VALID_CONFIG_YAML)
        cfg = load_config(path)
        self.assertEqual(cfg["tower_ws_url"], "")

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
        for key in ("node_id", "node_type", "role", "capabilities"):
            self.assertIn(key, REQUIRED_KEYS)

    def test_control_plane_url_keys_order(self):
        """backend_url is the canonical key; tower_url the legacy alias."""
        self.assertEqual(
            CONTROL_PLANE_URL_KEYS, ("backend_url", "tower_url")
        )

    def test_valid_node_types(self):
        for nt in ("local_pc", "cloud_agent", "web_ai",
                   "edge_device", "external_mcp"):
            self.assertIn(nt, VALID_NODE_TYPES)

    def test_valid_roles(self):
        for r in ("planner", "coder", "tester", "gate", "observer"):
            self.assertIn(r, VALID_ROLES)


if __name__ == "__main__":
    unittest.main()

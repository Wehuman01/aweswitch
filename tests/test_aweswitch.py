import json
import os
import stat
import sys
import tempfile
import time
import unittest
import io
import unittest.mock
from pathlib import Path

from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aweswitch import cli as aweswitch
from aweswitch import update_check


class AweSwitchTests(unittest.TestCase):
    def assert_settings_file_secure(self, path):
        if os.name == "nt":
            return
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_init_creates_example_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"

            aweswitch.init_config(path)

            data = json.loads(path.read_text())
            self.assertIn("profiles", data)
            self.assertIn("accounts", data["profiles"])
            self.assertIn("claude", data["profiles"]["api"])
            self.assertIn("cc-glm", data["profiles"]["api"]["claude"])
            self.assertIn("codex", data["profiles"]["api"])
            self.assertIn("cx-openai", data["profiles"]["api"]["codex"])

    def test_package_entry_point_targets_cli_main(self):
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

        data = pyproject_path.read_text()

        self.assertRegex(data, r'version = "\d+\.\d+\.\d+"')
        self.assertIn('aweswitch = "aweswitch.cli:main"', data)
        self.assertIn('dependencies = ["click>=8.1"]', data)

    def test_main_help_uses_click_command_layout(self):
        result = CliRunner().invoke(aweswitch.cli, ["-h"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage: aweswitch [OPTIONS] COMMAND [ARGS]...", result.output)
        self.assertIn("Agent profile switcher for launching isolated runtime configs.", result.output)
        self.assertIn("-v, --version", result.output)
        self.assertIn("list", result.output)
        self.assertIn("config", result.output)

    def test_version_option(self):
        import aweswitch as pkg
        expected_version = pkg.__version__

        result = CliRunner().invoke(aweswitch.cli, ["-v"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn(expected_version, result.output)

    def test_config_help_uses_click_command_layout(self):
        result = CliRunner().invoke(aweswitch.cli, ["config", "-h"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage: aweswitch config [OPTIONS] COMMAND [ARGS]...", result.output)
        self.assertIn("Manage aweswitch config.", result.output)
        self.assertIn("path", result.output)
        self.assertIn("show", result.output)
        self.assertIn("edit", result.output)
        self.assertIn("init", result.output)

    def test_save_profile_adds_new_claude_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            aweswitch.save_profile(path, "my-profile", {
                "ANTHROPIC_BASE_URL": "https://example.com",
                "ANTHROPIC_AUTH_TOKEN": "${MY_TOKEN}",
                "ANTHROPIC_MODEL": "test-model",
            }, provider="claude")

            data = json.loads(path.read_text())
            profile = data["profiles"]["api"]["claude"]["my-profile"]
            self.assertEqual(profile["env"]["ANTHROPIC_BASE_URL"], "https://example.com")
            self.assertEqual(profile["env"]["ANTHROPIC_AUTH_TOKEN"], "${MY_TOKEN}")
            self.assertEqual(profile["env"]["ANTHROPIC_MODEL"], "test-model")

    def test_save_profile_adds_new_codex_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            aweswitch.save_profile(path, "cx-test", {
                "OPENAI_BASE_URL": "https://api.example.com/v1",
                "OPENAI_API_KEY": "${MY_KEY}",
            }, provider="codex")

            data = json.loads(path.read_text())
            profile = data["profiles"]["api"]["codex"]["cx-test"]
            self.assertEqual(profile["env"]["OPENAI_BASE_URL"], "https://api.example.com/v1")
            self.assertEqual(profile["env"]["OPENAI_API_KEY"], "${MY_KEY}")

    def test_save_profile_skips_empty_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            aweswitch.save_profile(path, "minimal", {
                "ANTHROPIC_BASE_URL": "https://example.com",
                "ANTHROPIC_AUTH_TOKEN": "${T}",
                "ANTHROPIC_MODEL": "m",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "",
            }, provider="claude")

            data = json.loads(path.read_text())
            env = data["profiles"]["api"]["claude"]["minimal"]["env"]
            self.assertNotIn("ANTHROPIC_DEFAULT_HAIKU_MODEL", env)
            self.assertNotIn("ANTHROPIC_DEFAULT_SONNET_MODEL", env)

    def test_save_profile_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            aweswitch.save_profile(path, "dup", {
                "ANTHROPIC_BASE_URL": "https://example.com",
                "ANTHROPIC_AUTH_TOKEN": "${T}",
                "ANTHROPIC_MODEL": "m",
            }, provider="claude")
            with self.assertRaisesRegex(SystemExit, "already exists"):
                aweswitch.save_profile(path, "dup", {
                    "ANTHROPIC_BASE_URL": "https://other.com",
                    "ANTHROPIC_AUTH_TOKEN": "${T}",
                    "ANTHROPIC_MODEL": "m",
                }, provider="claude")

    def test_save_profile_rejects_reserved_command_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            with self.assertRaisesRegex(SystemExit, "reserved command name"):
                aweswitch.save_profile(path, "list", {
                    "ANTHROPIC_BASE_URL": "https://example.com",
                    "ANTHROPIC_AUTH_TOKEN": "${T}",
                    "ANTHROPIC_MODEL": "m",
                }, provider="claude")

    def test_save_account_rejects_unsafe_filesystem_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            with self.assertRaisesRegex(SystemExit, "single path component"):
                aweswitch.save_account(path, "codex", "../../../escape", {"token": "x"})

            data = json.loads(path.read_text())
            self.assertEqual(data["profiles"]["accounts"], {})

    def test_add_command_creates_claude_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            result = CliRunner().invoke(aweswitch.cli, [
                "add",
            ], input="api\nclaude\ntest-profile\nhttps://example.com\nMY_TOKEN\ntest-model\n\n\n",
                env={"AWESWITCH_CONFIG": str(path)})

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Profile 'test-profile' added.", result.output)

            data = json.loads(path.read_text())
            profile = data["profiles"]["api"]["claude"]["test-profile"]
            self.assertEqual(profile["env"]["ANTHROPIC_BASE_URL"], "https://example.com")
            self.assertEqual(profile["env"]["ANTHROPIC_AUTH_TOKEN"], "${MY_TOKEN}")
            self.assertEqual(profile["env"]["ANTHROPIC_MODEL"], "test-model")
            self.assertNotIn("ANTHROPIC_DEFAULT_HAIKU_MODEL", profile["env"])
            self.assertNotIn("ANTHROPIC_DEFAULT_SONNET_MODEL", profile["env"])

    def test_add_command_with_optional_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            result = CliRunner().invoke(aweswitch.cli, [
                "add",
            ], input="api\nclaude\nfull-profile\nhttps://example.com\nMY_TOKEN\nmy-model\nhaiku-m\nsonnet-m\n",
                env={"AWESWITCH_CONFIG": str(path)})

            self.assertEqual(result.exit_code, 0, result.output)

            data = json.loads(path.read_text())
            env = data["profiles"]["api"]["claude"]["full-profile"]["env"]
            self.assertEqual(env["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "haiku-m")
            self.assertEqual(env["ANTHROPIC_DEFAULT_SONNET_MODEL"], "sonnet-m")

    def test_add_command_creates_codex_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            result = CliRunner().invoke(aweswitch.cli, [
                "add",
            ], input="api\ncodex\ncx-test\nhttps://api.example.com/v1\nMY_KEY\ngpt-5.2-codex, kimi-k2.7\n",
                env={"AWESWITCH_CONFIG": str(path)})

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Profile 'cx-test' added.", result.output)

            data = json.loads(path.read_text())
            profile = data["profiles"]["api"]["codex"]["cx-test"]
            self.assertEqual(profile["env"]["OPENAI_BASE_URL"], "https://api.example.com/v1")
            self.assertEqual(profile["env"]["OPENAI_API_KEY"], "${MY_KEY}")
            self.assertEqual(profile["env"]["OPENAI_MODEL"],
                             {"gpt-5.2-codex": "gpt-5.2-codex", "kimi-k2.7": "kimi-k2.7"})

    def test_add_command_codex_model_prompt_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            aweswitch.init_config(path)

            result = CliRunner().invoke(aweswitch.cli, [
                "add",
            ], input="api\ncodex\ncx-test\nhttps://api.example.com/v1\nMY_KEY\n\n",
                env={"AWESWITCH_CONFIG": str(path)})

            self.assertEqual(result.exit_code, 0, result.output)

            data = json.loads(path.read_text())
            profile = data["profiles"]["api"]["codex"]["cx-test"]
            self.assertNotIn("OPENAI_MODEL", profile["env"])

    @unittest.mock.patch("aweswitch.cli.subprocess.run")
    def test_add_command_official_login_runs_login_flow(self, mock_run):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            aweswitch.init_config(config_file)

            def fake_login(argv, env=None):
                cred_path = Path(env["CODEX_HOME"]) / "auth.json"
                cred_path.write_text(json.dumps({"tokens": {"access_token": "fresh"}}))
                return unittest.mock.MagicMock(returncode=0)

            mock_run.side_effect = fake_login

            result = CliRunner().invoke(aweswitch.cli, [
                "add",
            ], input="official\ncodex\ncxo-work\n\n",
                env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertEqual(result.exit_code, 0, result.output)
            data = json.loads(config_file.read_text())
            self.assertEqual(data["profiles"]["accounts"]["codex"]["cxo-work"]["auth"],
                             {"tokens": {"access_token": "fresh"}})

    def test_add_command_official_import_reads_live_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            aweswitch.init_config(config_file)
            live_dir = Path(tmp) / "codex"
            live_dir.mkdir()
            blob = {"tokens": {"access_token": "tok", "refresh_token": "ref"}}
            (live_dir / "auth.json").write_text(json.dumps(blob))

            result = CliRunner().invoke(aweswitch.cli, [
                "add",
            ], input="official\ncodex\ncxo-work\nimport\n",
                env={"AWESWITCH_CONFIG": str(config_file),
                     "CODEX_CONFIG": str(live_dir / "config.toml")})

            self.assertEqual(result.exit_code, 0, result.output)
            data = json.loads(config_file.read_text())
            self.assertEqual(data["profiles"]["accounts"]["codex"]["cxo-work"]["auth"], blob)
            self.assert_settings_file_secure(config_file)

    def test_prepare_claude_uses_provider_command_and_env_overrides(self):
        config = {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-glm": {
                            "env": {
                                "ANTHROPIC_BASE_URL": "${GLM_BASE}",
                                "ANTHROPIC_AUTH_TOKEN": "${GLM_TOKEN}",
                                "ANTHROPIC_MODEL": "glm-5.1",
                            },
                        }
                    }
                }
            }
        }
        base_env = {"PATH": "/bin", "GLM_BASE": "https://example.test", "GLM_TOKEN": "secret"}

        argv, env, _, _ = aweswitch.prepare_run(config, "cc-glm", ["--verbose"], base_env)

        self.assertEqual(argv[0], "claude")
        self.assertEqual(argv[1], "--settings")
        settings_path = argv[2]
        self.assertTrue(os.path.isfile(settings_path))
        self.assert_settings_file_secure(settings_path)
        self.assertEqual(json.loads(Path(settings_path).read_text()), {
            "env": {
                "ANTHROPIC_BASE_URL": "https://example.test",
                "ANTHROPIC_AUTH_TOKEN": "secret",
                "ANTHROPIC_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_FABLE_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_FABLE_MODEL_NAME": "glm-5.1",
                "CLAUDE_CODE_SUBAGENT_MODEL": "inherit",
            }
        })
        self.assertEqual(argv[3:], ["--verbose"])
        self.assertNotIn("ANTHROPIC_MODEL", env)
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assertEqual(base_env.get("ANTHROPIC_MODEL"), None)

    def test_prepare_claude_can_expand_from_claude_settings_env(self):
        config = {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-glm": {
                            "env": {
                                "ANTHROPIC_BASE_URL": "${ANTHROPIC_BASE_URL}",
                                "ANTHROPIC_AUTH_TOKEN": "${ANTHROPIC_AUTH_TOKEN}",
                                "ANTHROPIC_MODEL": "glm-5.1",
                            },
                        }
                    }
                }
            }
        }
        claude_settings_env = {
            "ANTHROPIC_BASE_URL": "https://example.test",
            "ANTHROPIC_AUTH_TOKEN": "secret",
        }

        argv, env, _, _ = aweswitch.prepare_run(config, "cc-glm", [], {}, claude_settings_env)

        self.assertEqual(argv[0], "claude")
        self.assertEqual(argv[1], "--settings")
        settings_path = argv[2]
        self.assertTrue(os.path.isfile(settings_path))
        self.assert_settings_file_secure(settings_path)
        self.assertEqual(json.loads(Path(settings_path).read_text()), {
            "env": {
                "ANTHROPIC_BASE_URL": "https://example.test",
                "ANTHROPIC_AUTH_TOKEN": "secret",
                "ANTHROPIC_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_FABLE_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_FABLE_MODEL_NAME": "glm-5.1",
                "CLAUDE_CODE_SUBAGENT_MODEL": "inherit",
            }
        })
        self.assertEqual(env, {})

    def test_prepare_claude_only_uses_settings_env_for_model(self):
        config = {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-glm": {
                            "env": {
                                "ANTHROPIC_BASE_URL": "https://example.test",
                                "ANTHROPIC_AUTH_TOKEN": "${SECRET_TOKEN}",
                                "ANTHROPIC_MODEL": "glm-5.1",
                            },
                        }
                    }
                }
            }
        }
        base_env = {"ANTHROPIC_MODEL": "old-model", "SECRET_TOKEN": "secret"}

        argv, env, _, _ = aweswitch.prepare_run(config, "cc-glm", [], base_env)

        self.assertEqual(env["ANTHROPIC_MODEL"], "old-model")
        self.assertEqual(argv[0], "claude")
        self.assertEqual(argv[1], "--settings")
        settings_path = argv[2]
        self.assertTrue(os.path.isfile(settings_path))
        self.assert_settings_file_secure(settings_path)
        self.assertEqual(json.loads(Path(settings_path).read_text()), {
            "env": {
                "ANTHROPIC_BASE_URL": "https://example.test",
                "ANTHROPIC_AUTH_TOKEN": "secret",
                "ANTHROPIC_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_FABLE_MODEL": "glm-5.1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME": "glm-5.1",
                "ANTHROPIC_DEFAULT_FABLE_MODEL_NAME": "glm-5.1",
                "CLAUDE_CODE_SUBAGENT_MODEL": "inherit",
            }
        })

    def test_prepare_claude_defaults_unset_tiers_to_main_model(self):
        # Regression: a profile that only sets ANTHROPIC_MODEL must still emit
        # every tier var. Claude Code merges --settings with ~/.claude/settings.json,
        # so an omitted tier lets a stale model from a different provider leak
        # through (e.g. minimax profile erroring with "selected model (mimo-v2.5)").
        config = {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-doubao-minimax": {
                            "env": {
                                "ANTHROPIC_BASE_URL": "https://ark.cn-beijing.volces.com/api/coding",
                                "ANTHROPIC_AUTH_TOKEN": "${SECRET_TOKEN}",
                                "ANTHROPIC_MODEL": "minimax-m3",
                            },
                        }
                    }
                }
            }
        }
        argv, env, _, _ = aweswitch.prepare_run(config, "cc-doubao-minimax", [], {"SECRET_TOKEN": "secret"})
        settings_path = argv[2]
        settings_env = json.loads(Path(settings_path).read_text())["env"]

        # Every tier resolves to the provider's own model, never a leaked stale one.
        for tier in ("OPUS", "SONNET", "HAIKU", "FABLE"):
            self.assertEqual(settings_env[f"ANTHROPIC_DEFAULT_{tier}_MODEL"], "minimax-m3")
        # An explicit per-tier override is preserved, not clobbered by the default.
        config["profiles"]["api"]["claude"]["cc-doubao-minimax"]["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = "minimax-m3-mini"
        argv, _, _, _ = aweswitch.prepare_run(config, "cc-doubao-minimax", [], {"SECRET_TOKEN": "secret"})
        settings_env = json.loads(Path(argv[2]).read_text())["env"]
        self.assertEqual(settings_env["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "minimax-m3-mini")
        self.assertEqual(settings_env["ANTHROPIC_DEFAULT_SONNET_MODEL"], "minimax-m3")

    def test_prepare_claude_passes_profile_subagent_model(self):
        config = {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-glm": {
                            "env": {
                                "ANTHROPIC_BASE_URL": "https://example.test",
                                "ANTHROPIC_AUTH_TOKEN": "secret",
                                "ANTHROPIC_MODEL": "glm-5.1",
                                "CLAUDE_CODE_SUBAGENT_MODEL": "glm-5.1-flash",
                            },
                        }
                    }
                }
            }
        }

        argv, _, _, _ = aweswitch.prepare_run(config, "cc-glm", [], {})

        settings_env = json.loads(Path(argv[2]).read_text())["env"]
        self.assertEqual(settings_env["CLAUDE_CODE_SUBAGENT_MODEL"], "glm-5.1-flash")

    def test_prepare_claude_masks_stale_subagent_model(self):
        # Regression: Claude Code merges --settings with ~/.claude/settings.json,
        # so a profile that omits the key must still emit an explicit
        # fall-through value instead of letting a stale pin leak through.
        config = {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-glm": {
                            "env": {
                                "ANTHROPIC_BASE_URL": "https://example.test",
                                "ANTHROPIC_AUTH_TOKEN": "secret",
                                "ANTHROPIC_MODEL": "glm-5.1",
                            },
                        }
                    }
                }
            }
        }

        argv, _, _, _ = aweswitch.prepare_run(config, "cc-glm", [], {})

        settings_env = json.loads(Path(argv[2]).read_text())["env"]
        self.assertEqual(settings_env["CLAUDE_CODE_SUBAGENT_MODEL"], "inherit")

    def test_prepare_claude_ignores_top_level_model(self):
        config = {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-glm": {
                            "model": "ignored-model",
                            "env": {
                                "ANTHROPIC_BASE_URL": "https://example.test",
                                "ANTHROPIC_AUTH_TOKEN": "${SECRET_TOKEN}",
                                "ANTHROPIC_MODEL": "glm-5.1",
                            },
                        }
                    }
                }
            }
        }
        argv, env, _, _ = aweswitch.prepare_run(config, "cc-glm", [], {"SECRET_TOKEN": "secret"})

        self.assertNotIn("ANTHROPIC_MODEL", env)
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assertNotIn("--model", argv)
        self.assertNotIn("ignored-model", argv)

    def test_prepare_codex_uses_config_overrides_and_env(self):
        config = {
            "profiles": {
                "api": {
                    "codex": {
                        "cx-test": {
                            "env": {
                                "OPENAI_BASE_URL": "${CODEX_BASE}",
                                "OPENAI_API_KEY": "${CODEX_KEY}",
                            },
                        }
                    }
                }
            }
        }
        base_env = {"PATH": "/bin", "CODEX_BASE": "https://provider.test/v1", "CODEX_KEY": "sk-test"}

        argv, env, _, _ = aweswitch.prepare_run(config, "cx-test", ["--verbose"], base_env)

        self.assertEqual(argv[0], "codex")
        self.assertIn("-c", argv)
        # Verify -c flags contain the expected overrides
        c_args = []
        i = 1
        while i < len(argv):
            if argv[i] == "-c" and i + 1 < len(argv):
                c_args.append(argv[i + 1])
                i += 2
            else:
                break
        self.assertIn('model_provider="custom"', c_args)
        self.assertIn('model_providers.custom.base_url="https://provider.test/v1"', c_args)
        self.assertIn('model_providers.custom.wire_api="responses"', c_args)
        self.assertIn('disable_response_storage=true', c_args)
        # API key injected via env; argv carries only the env var NAME (env_key), never the secret
        self.assertEqual(env["OPENAI_API_KEY"], "sk-test")
        self.assertNotIn("sk-test", " ".join(argv))
        # User args passed through
        self.assertIn("--verbose", argv)

    def test_prepare_codex_passes_subagent_model(self):
        config = self._make_cx_config()
        config["profiles"]["api"]["codex"]["cx-test"]["env"]["CODEX_SUBAGENT_MODEL"] = "glm-5.3-flash"

        argv, _, _, _ = aweswitch.prepare_run(config, "cx-test", [], {"CX_KEY": "sk-test"})

        self.assertIn('agents.default_subagent_model="glm-5.3-flash"', self._c_args(argv))

    def test_prepare_codex_without_subagent_model_adds_no_override(self):
        config = self._make_cx_config()

        argv, _, _, _ = aweswitch.prepare_run(config, "cx-test", [], {"CX_KEY": "sk-test"})

        self.assertFalse([c for c in self._c_args(argv) if c.startswith("agents.")])

    def test_prepare_codex_rejects_subagent_reference(self):
        config = self._make_cx_config()
        config["profiles"]["api"]["codex"]["cx-test"]["env"]["CODEX_SUBAGENT_MODEL"] = "@oc-glm/m1"

        with self.assertRaisesRegex(SystemExit, "does not support @profile/model"):
            aweswitch.prepare_run(config, "cx-test", [], {"CX_KEY": "sk-test"})

    def test_edit_codex_subagent_model_variants(self):
        base = [
            'model = "m"\n',
            '\n',
            '[agents]\n',
            'max_threads = 4\n',
            '\n',
            '[agents.researcher]\n',
            'description = "d"\n',
            '\n',
            '[mcp_servers]\n',
        ]
        # Pin lands right under the [agents] header; roles and other keys stay.
        lines, note = aweswitch.edit_codex_subagent_model(list(base), "glm-5.3-flash")
        header_idx = lines.index("[agents]\n")
        self.assertEqual(lines[header_idx + 1], 'default_subagent_model = "glm-5.3-flash"\n')
        text = "".join(lines)
        self.assertIn("max_threads = 4", text)
        self.assertIn("[agents.researcher]", text)
        self.assertIn("sub-agents spawn on this model", note)

        # Same value is idempotent; a different value overwrites.
        same_lines, same_note = aweswitch.edit_codex_subagent_model(list(lines), "glm-5.3-flash")
        self.assertEqual(same_lines, lines)
        self.assertIsNone(same_note)
        over_lines, over_note = aweswitch.edit_codex_subagent_model(list(lines), "other-m")
        self.assertIn('default_subagent_model = "other-m"', "".join(over_lines))
        self.assertIn("overwrote", over_note)

        # Release keeps the table, sibling keys, and role sub-tables.
        rel_lines, rel_note = aweswitch.edit_codex_subagent_model(list(lines), None)
        rel_text = "".join(rel_lines)
        self.assertNotIn("default_subagent_model", rel_text)
        self.assertIn("[agents]", rel_text)
        self.assertIn("max_threads = 4", rel_text)
        self.assertIn("[agents.researcher]", rel_text)
        self.assertIn("released", rel_note)

        # Releasing our only key drops the now-empty [agents] header.
        only = ['[agents]\n', 'default_subagent_model = "m"\n', '\n[mcp_servers]\n']
        drop_lines, _ = aweswitch.edit_codex_subagent_model(only, None)
        drop_text = "".join(drop_lines)
        self.assertNotIn("[agents]", drop_text)
        self.assertIn("[mcp_servers]", drop_text)

        # No table at all: one is appended.
        fresh = ['model = "m"\n']
        new_lines, _ = aweswitch.edit_codex_subagent_model(list(fresh), "flash")
        self.assertIn('[agents]\ndefault_subagent_model = "flash"', "".join(new_lines))

        # Dotted form: replaced and released in place.
        dotted = ['model = "m"\n', 'agents.max_threads = 4\n', 'agents.default_subagent_model = "old"\n']
        dot_lines, _ = aweswitch.edit_codex_subagent_model(list(dotted), "new-m")
        dot_text = "".join(dot_lines)
        self.assertIn('agents.default_subagent_model = "new-m"', dot_text)
        rel_dot, _ = aweswitch.edit_codex_subagent_model(list(dotted), None)
        rel_dot_text = "".join(rel_dot)
        self.assertNotIn("default_subagent_model", rel_dot_text)
        self.assertIn("agents.max_threads = 4", rel_dot_text)

        # Dotted siblings but no key: stays dotted (a new [agents] header would
        # be invalid TOML next to implicit dotted definitions).
        sib = ['model = "m"\n', 'agents.max_threads = 4\n']
        sib_lines, _ = aweswitch.edit_codex_subagent_model(list(sib), "flash")
        sib_text = "".join(sib_lines)
        self.assertIn('agents.default_subagent_model = "flash"', sib_text)
        self.assertNotIn("[agents]", sib_text)

        # An agents.x dotted line inside another table belongs to that table.
        inside = ['[wrapper]\n', 'agents.max_threads = 4\n']
        inside_lines, _ = aweswitch.edit_codex_subagent_model(list(inside), "flash")
        self.assertIn('[agents]', "".join(inside_lines))
        self.assertIn('agents.max_threads = 4', "".join(inside_lines))

    def test_prepare_codex_rejects_missing_base_url(self):
        config = {
            "profiles": {
                "api": {
                    "codex": {
                        "cx-bad": {
                            "env": {
                                "OPENAI_API_KEY": "${KEY}",
                            },
                        }
                    }
                }
            }
        }
        with self.assertRaisesRegex(SystemExit, "OPENAI_BASE_URL is required"):
            aweswitch.prepare_run(config, "cx-bad", [], {"KEY": "sk-test"})

    def test_prepare_codex_rejects_missing_api_key(self):
        config = {
            "profiles": {
                "api": {
                    "codex": {
                        "cx-bad": {
                            "env": {
                                "OPENAI_BASE_URL": "https://example.com/v1",
                            },
                        }
                    }
                }
            }
        }
        with self.assertRaisesRegex(SystemExit, "OPENAI_API_KEY is required"):
            aweswitch.prepare_run(config, "cx-bad", [], {})

    def _make_cx_config(self, models=None):
        env = {
            "OPENAI_BASE_URL": "https://provider.test/v1",
            "OPENAI_API_KEY": "${CX_KEY}",
        }
        if models is not None:
            env["OPENAI_MODEL"] = models
        return {"profiles": {"api": {"codex": {"cx-test": {"env": env}}}}}

    def _c_args(self, argv):
        c_args = []
        i = 1
        while i < len(argv):
            if argv[i] == "-c" and i + 1 < len(argv):
                c_args.append(argv[i + 1])
                i += 2
            else:
                break
        return c_args

    def test_prepare_codex_uses_model_from_args(self):
        config = self._make_cx_config({"gpt-5.2-codex": "GPT-5.2", "kimi-k2.7": "Kimi"})

        argv, env, _, _ = aweswitch.prepare_run(config, "cx-test", ["kimi-k2.7"], {"CX_KEY": "sk-test"})

        self.assertEqual(argv[0], "codex")
        self.assertIn('model="kimi-k2.7"', self._c_args(argv))
        self.assertIn('model_providers.custom.name="custom"', self._c_args(argv))
        self.assertIn('model_providers.custom.env_key="OPENAI_API_KEY"', self._c_args(argv))
        self.assertEqual(env["OPENAI_API_KEY"], "sk-test")

    def test_prepare_codex_defaults_to_first_model(self):
        config = self._make_cx_config({"gpt-5.2-codex": "GPT-5.2", "kimi-k2.7": "Kimi"})

        argv, env, _, _ = aweswitch.prepare_run(config, "cx-test", [], {"CX_KEY": "sk-test"})

        self.assertIn('model="gpt-5.2-codex"', self._c_args(argv))

    def test_prepare_codex_rejects_unknown_model(self):
        config = self._make_cx_config({"gpt-5.2-codex": "GPT-5.2"})

        with self.assertRaisesRegex(SystemExit, "unknown model 'gpt-9.9'"):
            aweswitch.prepare_run(config, "cx-test", ["gpt-9.9"], {"CX_KEY": "sk-test"})

    def test_prepare_codex_matches_model_case_insensitively(self):
        config = self._make_cx_config({"gpt-5.2-codex": "GPT-5.2", "kimi-k2.7": "Kimi"})

        argv, _, _, _ = aweswitch.prepare_run(config, "cx-test", ["GPT-5.2-CODEX"], {"CX_KEY": "sk-test"})

        self.assertIn('model="gpt-5.2-codex"', self._c_args(argv))

    def test_prepare_codex_matches_display_name_case_insensitively(self):
        config = self._make_cx_config({"gpt-5.2-codex": "GPT-5.2"})

        argv, _, _, _ = aweswitch.prepare_run(config, "cx-test", ["gpt-5.2"], {"CX_KEY": "sk-test"})

        self.assertIn('model="gpt-5.2-codex"', self._c_args(argv))

    def test_prepare_codex_matches_model_substring_case_insensitively(self):
        config = self._make_cx_config({"gpt-5.2-codex": "GPT-5.2", "kimi-k2.7": "Kimi"})

        argv, _, _, _ = aweswitch.prepare_run(config, "cx-test", ["GPT"], {"CX_KEY": "sk-test"})

        self.assertIn('model="gpt-5.2-codex"', self._c_args(argv))

    def test_prepare_codex_rejects_ambiguous_substring_match(self):
        config = self._make_cx_config({"gpt-5.2-codex": "GPT-5.2", "gpt-5.1": "GPT-5.1"})

        with self.assertRaisesRegex(SystemExit, "ambiguous model 'gpt'"):
            aweswitch.prepare_run(config, "cx-test", ["gpt"], {"CX_KEY": "sk-test"})

    def test_prepare_codex_rejects_non_string_model_display_name(self):
        config = self._make_cx_config({"gpt-5.2-codex": 42})

        with self.assertRaisesRegex(SystemExit, "model IDs and display names must be non-empty strings"):
            aweswitch.prepare_run(config, "cx-test", ["gpt"], {"CX_KEY": "sk-test"})

    def test_prepare_codex_without_models_keeps_legacy_behavior(self):
        config = self._make_cx_config(models=None)

        argv, env, _, _ = aweswitch.prepare_run(config, "cx-test", ["--verbose"], {"CX_KEY": "sk-test"})

        c_args = self._c_args(argv)
        self.assertNotIn('model="--verbose"', c_args)  # no model injected, arg passes through
        for c in c_args:
            self.assertFalse(c.startswith("model="))
        self.assertIn("--verbose", argv)
        self.assertIn('model_providers.custom.env_key="OPENAI_API_KEY"', c_args)

    def test_prepare_codex_normalizes_string_models(self):
        config = self._make_cx_config("gpt-5.2-codex, kimi-k2.7")

        argv, env, _, _ = aweswitch.prepare_run(config, "cx-test", ["kimi-k2.7"], {"CX_KEY": "sk-test"})

        self.assertIn('model="kimi-k2.7"', self._c_args(argv))

    def test_prepare_rejects_unknown_provider(self):
        config = {
            "profiles": {
                "api": {
                    "unknown": {
                        "test": {"env": {}},
                    }
                }
            }
        }

        with self.assertRaisesRegex(SystemExit, "unsupported provider"):
            aweswitch.prepare_run(config, "test", [], {})

    def test_profile_model_label_uses_anthropic_model_for_claude(self):
        self.assertEqual(
            aweswitch.profile_model_label("claude", {"env": {"ANTHROPIC_MODEL": "glm-5.1"}}),
            "glm-5.1",
        )

    def test_profile_model_label_uses_base_url_for_codex(self):
        self.assertEqual(
            aweswitch.profile_model_label("codex", {"env": {"OPENAI_BASE_URL": "https://api.test/v1"}}),
            "https://api.test/v1",
        )

    def test_profile_model_label_shows_string_model_for_codex(self):
        self.assertEqual(
            aweswitch.profile_model_label("codex", {"env": {"OPENAI_MODEL": "auto"}}),
            "auto",
        )

    def test_profile_model_label_shows_list_model_for_codex(self):
        self.assertEqual(
            aweswitch.profile_model_label("codex", {"env": {"OPENAI_MODEL": ["gpt-5.2-codex", "kimi-k2.7"]}}),
            "gpt-5.2-codex, kimi-k2.7",
        )

    def test_profile_model_label_falls_back_to_base_url_for_empty_codex_model(self):
        self.assertEqual(
            aweswitch.profile_model_label("codex", {"env": {"OPENAI_BASE_URL": "https://api.test/v1", "OPENAI_MODEL": ""}}),
            "https://api.test/v1",
        )

    def test_profile_model_label_shows_models_for_codex(self):
        self.assertEqual(
            aweswitch.profile_model_label(
                "codex",
                {"env": {"OPENAI_BASE_URL": "https://api.test/v1",
                         "OPENAI_MODEL": {"kimi-k2.7": "Kimi", "gpt-5.2-codex": "GPT"}}},
            ),
            "gpt-5.2-codex, kimi-k2.7",
        )

    def test_profile_for_errors_on_duplicate_profile_names(self):
        config = {
            "profiles": {
                "api": {
                    "claude": {"default": {"env": {}}},
                    "codex": {"default": {"env": {}}},
                }
            }
        }

        with self.assertRaisesRegex(SystemExit, "ambiguous profile"):
            aweswitch.profile_for(config, "default")

    def test_redact_hides_secret_values(self):
        data = {
            "profiles": {
                "x": {
                    "env": {
                        "ANTHROPIC_AUTH_TOKEN": "secret",
                        "ANTHROPIC_BASE_URL": "https://example.test",
                    }
                }
            }
        }

        redacted = aweswitch.redact(data)

        self.assertEqual(redacted["profiles"]["x"]["env"]["ANTHROPIC_AUTH_TOKEN"], "<redacted>")
        self.assertEqual(redacted["profiles"]["x"]["env"]["ANTHROPIC_BASE_URL"], "https://example.test")

    def test_redact_hides_codex_api_key(self):
        data = {
            "profiles": {
                "x": {
                    "env": {
                        "OPENAI_API_KEY": "sk-secret",
                        "OPENAI_BASE_URL": "https://example.test",
                    }
                }
            }
        }

        redacted = aweswitch.redact(data)

        self.assertEqual(redacted["profiles"]["x"]["env"]["OPENAI_API_KEY"], "<redacted>")
        self.assertEqual(redacted["profiles"]["x"]["env"]["OPENAI_BASE_URL"], "https://example.test")

    def test_expand_env_errors_on_missing_variable(self):
        with self.assertRaisesRegex(SystemExit, "required environment variable not set"):
            aweswitch.expand_value("${MISSING_ENV}", {})

    def test_editor_argv_splits_editor_with_flags(self):
        argv = aweswitch.editor_argv("code -w", Path("/tmp/config.json"))

        self.assertEqual(argv, ["code", "-w", str(Path("/tmp/config.json"))])

    def test_exec_agent_reports_missing_command(self):
        with self.assertRaisesRegex(SystemExit, "command not found"):
            aweswitch.exec_agent(["/tmp/aweswitch-command-that-does-not-exist"], {})

    @unittest.mock.patch.object(aweswitch.os, "name", "nt")
    @unittest.mock.patch.object(aweswitch.shutil, "which")
    @unittest.mock.patch.object(aweswitch.subprocess, "run")
    @unittest.mock.patch.object(aweswitch.sys, "exit")
    def test_exec_agent_resolves_cmd_on_windows(self, mock_exit, mock_run, mock_which):
        """A bare 'claude' resolves to claude.cmd and is exec'd as-is."""
        mock_which.return_value = r"C:\Users\me\AppData\Roaming\npm\claude.cmd"
        mock_run.return_value = unittest.mock.MagicMock(returncode=0)

        aweswitch.exec_agent(["claude", "--settings", "/tmp/settings.json"], {"PATH": r"C:\Windows"})

        mock_which.assert_called_once_with("claude", path=r"C:\Windows")
        called_argv = mock_run.call_args[0][0]
        self.assertEqual(
            called_argv,
            [r"C:\Users\me\AppData\Roaming\npm\claude.cmd", "--settings", "/tmp/settings.json"],
        )
        mock_exit.assert_called_once_with(0)

    @unittest.mock.patch.object(aweswitch.os, "name", "nt")
    @unittest.mock.patch.object(aweswitch.shutil, "which")
    @unittest.mock.patch.object(aweswitch.subprocess, "run")
    @unittest.mock.patch.object(aweswitch.sys, "exit")
    def test_exec_agent_wraps_ps1_in_powershell_on_windows(self, mock_exit, mock_run, mock_which):
        """A 'claude' that resolves to claude.ps1 is routed through powershell.exe -File."""
        # shutil.which is called twice: first for the user's command, then for powershell itself.
        mock_which.side_effect = [
            r"C:\Users\me\bin\claude.ps1",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        ]
        mock_run.return_value = unittest.mock.MagicMock(returncode=0)

        aweswitch.exec_agent(
            ["claude", "--settings", "/tmp/settings.json"],
            {"PATH": r"C:\Windows"},
        )

        self.assertEqual(mock_which.call_count, 2)
        self.assertEqual(mock_which.call_args_list[0], unittest.mock.call("claude", path=r"C:\Windows"))
        self.assertEqual(mock_which.call_args_list[1][0][0], "powershell")
        called_argv = mock_run.call_args[0][0]
        self.assertEqual(
            called_argv,
            [
                r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
                "-NoLogo", "-ExecutionPolicy", "Bypass",
                "-File", r"C:\Users\me\bin\claude.ps1",
                "--settings", "/tmp/settings.json",
            ],
        )
        mock_exit.assert_called_once_with(0)

    @unittest.mock.patch.object(aweswitch.os, "name", "nt")
    @unittest.mock.patch.object(aweswitch.shutil, "which")
    @unittest.mock.patch.object(aweswitch.subprocess, "run")
    @unittest.mock.patch.object(aweswitch.sys, "exit")
    def test_exec_agent_resolves_exe_on_windows(self, mock_exit, mock_run, mock_which):
        """A 'opencode' that resolves to opencode.exe is exec'd as-is (Go binary case)."""
        mock_which.return_value = r"C:\Program Files\opencode\opencode.exe"
        mock_run.return_value = unittest.mock.MagicMock(returncode=0)

        aweswitch.exec_agent(["opencode", "-m", "oc-glm/glm-5.1"], {"PATH": r"C:\Windows"})

        called_argv = mock_run.call_args[0][0]
        self.assertEqual(
            called_argv,
            [r"C:\Program Files\opencode\opencode.exe", "-m", "oc-glm/glm-5.1"],
        )
        mock_exit.assert_called_once_with(0)

    def test_generate_codex_config_produces_valid_toml(self):
        config = aweswitch.generate_codex_config("AiHubMix", "https://aihubmix.com/v1")

        self.assertIn('model_provider = "aihubmix"', config)
        self.assertIn('base_url = "https://aihubmix.com/v1"', config)
        self.assertIn('wire_api = "responses"', config)
        self.assertIn('requires_openai_auth = true', config)
        self.assertIn("[model_providers.aihubmix]", config)


    # --- opencode profiles ---

    def _make_oc_config(self, models=None,
                        base_url="https://example.com/v1", api_key="${OC_KEY}"):
        if models is None:
            models = {"glm-5.1": "GLM-5.1", "glm-5.2": "GLM-5.2"}
        return {
            "profiles": {
                "api": {
                    "opencode": {
                        "oc-test": {
                            "env": {
                                "OPENCODE_BASE_URL": base_url,
                                "OPENCODE_API_KEY": api_key,
                                "OPENCODE_MODEL": models,
                            }
                        }
                    }
                }
            }
        }

    def test_prepare_opencode_uses_model_from_args(self):
        config = self._make_oc_config()

        argv, env, oc_info, _ = aweswitch.prepare_run(config, "oc-test", ["glm-5.1"], {"OC_KEY": "sk-test"})

        self.assertEqual(argv[0], "opencode")
        self.assertEqual(argv[1:3], ["-m", "oc-test/glm-5.1"])
        self.assertEqual(env, {"OC_KEY": "sk-test"})
        self.assertEqual(oc_info["provider_name"], "oc-test")
        self.assertEqual(oc_info["model"], "glm-5.1")
        self.assertEqual(oc_info["base_url"], "https://example.com/v1")
        self.assertEqual(oc_info["api_key_ref"], "{env:OC_KEY}")

    def test_prepare_opencode_uses_model_display_name_from_args(self):
        config = self._make_oc_config(models={"peng1/step-router-v1": "step-router-v1"})

        argv, _, oc_info, _ = aweswitch.prepare_run(
            config, "oc-test", ["step-router-v1"], {"OC_KEY": "sk-test"}
        )

        self.assertEqual(argv[1:3], ["-m", "oc-test/peng1/step-router-v1"])
        self.assertEqual(oc_info["model"], "peng1/step-router-v1")

    def test_prepare_opencode_rejects_ambiguous_model_display_name(self):
        config = self._make_oc_config(models={
            "peng1/step-router-v1": "step-router-v1",
            "peng2/step-router-v1": "step-router-v1",
        })

        with self.assertRaisesRegex(SystemExit, "ambiguous model 'step-router-v1'"):
            aweswitch.prepare_run(config, "oc-test", ["step-router-v1"], {"OC_KEY": "sk-test"})

    def test_prepare_opencode_matches_model_case_insensitively(self):
        config = self._make_oc_config(models={"Doubao-Seed-Evolving": "Doubao Seed"})

        argv, _, oc_info, _ = aweswitch.prepare_run(
            config, "oc-test", ["doubao-seed-evolving"], {"OC_KEY": "sk-test"}
        )

        self.assertEqual(argv[1:3], ["-m", "oc-test/Doubao-Seed-Evolving"])
        self.assertEqual(oc_info["model"], "Doubao-Seed-Evolving")

    def test_prepare_opencode_matches_display_name_case_insensitively(self):
        config = self._make_oc_config(models={"hub/seed-evolving": "Seed-Evolving"})

        argv, _, oc_info, _ = aweswitch.prepare_run(
            config, "oc-test", ["seed-evolving"], {"OC_KEY": "sk-test"}
        )

        self.assertEqual(argv[1:3], ["-m", "oc-test/hub/seed-evolving"])
        self.assertEqual(oc_info["model"], "hub/seed-evolving")

    def test_prepare_opencode_rejects_ambiguous_case_insensitive_match(self):
        config = self._make_oc_config(models={"hub/a": "Seed", "hub/b": "seed"})

        with self.assertRaisesRegex(SystemExit, "ambiguous model 'SEED'"):
            aweswitch.prepare_run(config, "oc-test", ["SEED"], {"OC_KEY": "sk-test"})

    def test_prepare_opencode_matches_model_substring_case_insensitively(self):
        config = self._make_oc_config(models={"gpt-5.2-codex": "GPT-5.2 Codex"})

        argv, _, oc_info, _ = aweswitch.prepare_run(
            config, "oc-test", ["GPT"], {"OC_KEY": "sk-test"}
        )

        self.assertEqual(argv[1:3], ["-m", "oc-test/gpt-5.2-codex"])
        self.assertEqual(oc_info["model"], "gpt-5.2-codex")

    def test_prepare_opencode_rejects_ambiguous_substring_match(self):
        config = self._make_oc_config(models={"gpt-5.2": "GPT-5.2", "gpt-5.1": "GPT-5.1"})

        with self.assertRaisesRegex(SystemExit, "ambiguous model 'gpt'"):
            aweswitch.prepare_run(config, "oc-test", ["gpt"], {"OC_KEY": "sk-test"})

    def test_prepare_opencode_passes_extra_args(self):
        config = self._make_oc_config(models={"mimo-v2.5-pro": "MiMo"})

        argv, env, _, _ = aweswitch.prepare_run(config, "oc-test",
                                              ["mimo-v2.5-pro", "--mini"], {"OC_KEY": "sk-test"})

        self.assertEqual(argv[1:3], ["-m", "oc-test/mimo-v2.5-pro"])
        self.assertIn("--mini", argv)
        self.assertNotIn("mimo-v2.5-pro", argv[3:])  # model stripped from extra args

    def test_prepare_opencode_expands_env_refs(self):
        config = self._make_oc_config(api_key="${MY_KEY}")
        base_env = {"MY_KEY": "sk-resolved"}

        argv, env, oc_info, _ = aweswitch.prepare_run(config, "oc-test", ["glm-5.1"], base_env)

        self.assertEqual(oc_info["api_key_ref"], "{env:MY_KEY}")

    def test_prepare_opencode_defaults_to_first_model(self):
        config = self._make_oc_config()

        argv, env, oc_info, _ = aweswitch.prepare_run(config, "oc-test", [], {"OC_KEY": "sk-test"})

        self.assertEqual(argv[1:3], ["-m", "oc-test/glm-5.1"])
        self.assertEqual(oc_info["model"], "glm-5.1")

    def test_prepare_opencode_rejects_unknown_model(self):
        config = self._make_oc_config()

        with self.assertRaisesRegex(SystemExit, "unknown model 'glm-9.9'"):
            aweswitch.prepare_run(config, "oc-test", ["glm-9.9"], {"OC_KEY": "sk-test"})

    def test_prepare_opencode_rejects_missing_base_url(self):
        config = {"profiles": {"api": {"opencode": {"oc-bad": {"env": {
            "OPENCODE_API_KEY": "k", "OPENCODE_MODEL": {"m": "M"},
        }}}}}}

        with self.assertRaisesRegex(SystemExit, "OPENCODE_BASE_URL is required"):
            aweswitch.prepare_run(config, "oc-bad", ["m"], {})

    def test_prepare_opencode_rejects_missing_api_key(self):
        config = {"profiles": {"api": {"opencode": {"oc-bad": {"env": {
            "OPENCODE_BASE_URL": "https://x", "OPENCODE_MODEL": {"m": "M"},
        }}}}}}

        with self.assertRaisesRegex(SystemExit, "OPENCODE_API_KEY is required"):
            aweswitch.prepare_run(config, "oc-bad", ["m"], {})

    def test_prepare_opencode_rejects_empty_model(self):
        config = {"profiles": {"api": {"opencode": {"oc-bad": {"env": {
            "OPENCODE_BASE_URL": "https://x", "OPENCODE_API_KEY": "${OC_KEY}",
            "OPENCODE_MODEL": {},
        }}}}}}

        with self.assertRaisesRegex(
                SystemExit, "OPENCODE_MODEL or OPENCODE_RESPONSES_MODEL is required"):
            aweswitch.prepare_run(config, "oc-bad", ["m"], {"OC_KEY": "sk-test"})

    def test_prepare_opencode_warns_on_plaintext_api_key(self):
        config = self._make_oc_config(api_key="sk-test")

        with unittest.mock.patch("sys.stderr", new=io.StringIO()) as mock_stderr:
            argv, env, oc_info, _ = aweswitch.prepare_run(config, "oc-test", ["glm-5.1"], {})
            self.assertEqual(oc_info["api_key_ref"], "sk-test")
            self.assertIn("tip: OPENCODE_API_KEY is a plain value", mock_stderr.getvalue())

    def test_prepare_opencode_allows_responses_model_without_opencode_model(self):
        config = {"profiles": {"api": {"opencode": {"oc-test": {"env": {
            "OPENCODE_BASE_URL": "https://x/v1", "OPENCODE_API_KEY": "${OC_KEY}",
            "OPENCODE_RESPONSES_MODEL": ["peng1/x", "peng1/y"],
        }}}}}}

        argv, _, oc_info, _ = aweswitch.prepare_run(config, "oc-test", ["peng1/y"], {"OC_KEY": "sk-test"})

        self.assertEqual(argv[-1], "oc-test/peng1/y")
        self.assertEqual(oc_info["model_display_name"], "peng1/y")
        self.assertEqual(oc_info["responses_models"], ["peng1/x", "peng1/y"])

    def test_prepare_opencode_carries_responses_model_list(self):
        config = self._make_oc_config(models={"peng1/x": "x", "peng1/y": "y"})
        config["profiles"]["api"]["opencode"]["oc-test"]["env"]["OPENCODE_RESPONSES_MODEL"] = "ope/openai1"

        _, _, oc_info, _ = aweswitch.prepare_run(
            config, "oc-test", ["ope/openai1"], {"OC_KEY": "sk-test"})

        self.assertEqual(oc_info["responses_models"], ["ope/openai1"])

    def test_prepare_opencode_carries_subagents_and_dep_specs(self):
        config = self._make_oc_config(models={"glm-5.1": "GLM-5.1"})
        config["profiles"]["api"]["opencode"]["oc-step"] = {"env": {
            "OPENCODE_BASE_URL": "https://step.example/v1",
            "OPENCODE_API_KEY": "${STEP_KEY}",
            "OPENCODE_MODEL": ["step-3.7-flash"],
        }}
        config["subagents"] = {"opencode": {"explore": "oc-step/step-3.7-flash"}}

        _, _, oc_info, _ = aweswitch.prepare_run(config, "oc-test", [], {"OC_KEY": "k", "STEP_KEY": "s"})

        self.assertEqual(oc_info["subagents"], {"explore": "oc-step/step-3.7-flash"})
        self.assertEqual(len(oc_info["deps"]), 1)
        self.assertEqual(oc_info["deps"][0]["provider_name"], "oc-step")
        self.assertEqual(oc_info["deps"][0]["models"], {"step-3.7-flash": "step-3.7-flash"})

    def test_launch_write_registers_pinned_models_and_never_releases(self):
        config = self._make_oc_config()  # oc-test: glm-5.1 + glm-5.2
        config["subagents"] = {"opencode": {"explore": "oc-test/glm-5.1"}}
        config["profiles"]["api"]["opencode"]["oc-other"] = {"env": {
            "OPENCODE_BASE_URL": "https://other.example/v1",
            "OPENCODE_API_KEY": "${OTHER_KEY}",
            "OPENCODE_MODEL": ["other-m"],
        }}
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            agents_dir = oc_path.parent / "agents"
            agents_dir.mkdir()
            (agents_dir / "explore.md").write_text("---\ndescription: scout\n---\nbody\n")

            def launch(profile, args, env):
                _, _, oc_info, _ = aweswitch.prepare_run(config, profile, args, env)
                with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                    return list(aweswitch.write_opencode_launch(oc_info))

            # Launch on the primary model still registers the pinned model.
            notes = launch("oc-test", ["glm-5.2"], {"OC_KEY": "k", "OTHER_KEY": "o"})
            self.assertEqual(notes, ["pinned agent 'explore' -> oc-test/glm-5.1"])
            models = json.loads(oc_path.read_text())["provider"]["oc-test"]["models"]
            self.assertEqual(sorted(models), ["glm-5.1", "glm-5.2"])
            self.assertEqual(
                (agents_dir / "explore.md").read_text(),
                "---\ndescription: scout\nmodel: oc-test/glm-5.1\n---\nbody\n")

            # Launching another profile re-writes the same global pins
            # (already matching, so no note) and never releases them;
            # models stay additive.
            notes = launch("oc-other", [], {"OC_KEY": "k", "OTHER_KEY": "o"})
            self.assertEqual(notes, [])
            self.assertEqual(
                (agents_dir / "explore.md").read_text(),
                "---\ndescription: scout\nmodel: oc-test/glm-5.1\n---\nbody\n")
            data = json.loads(oc_path.read_text())["provider"]
            self.assertEqual(sorted(data["oc-test"]["models"]), ["glm-5.1", "glm-5.2"])
            self.assertEqual(sorted(data["oc-other"]["models"]), ["other-m"])
            sidecar = json.loads(
                (oc_path.parent / ".aweswitch-managed-providers.json").read_text())
            self.assertEqual(sidecar["agents"], ["explore"])

    def _make_oc_db(self, tmp, session_id, user_models):
        """Create a minimal opencode.db: one session plus user messages.

        user_models entries are "provider/model" stamps, or None for a user
        message without one (pre-model-stamp history).
        """
        import sqlite3
        db = Path(tmp) / "opencode.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE session (id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE message (session_id TEXT, time_created INTEGER, data TEXT)")
        conn.execute("INSERT INTO session VALUES (?)", (session_id,))
        for i, model in enumerate(user_models):
            data = {"role": "user"}
            if model:
                provider, _, model_id = model.partition("/")
                data["model"] = {"providerID": provider, "modelID": model_id}
            conn.execute(
                "INSERT INTO message VALUES (?, ?, ?)",
                (session_id, 1000 + i, json.dumps(data)),
            )
        conn.commit()
        conn.close()

    def _prepare_oc_resume(self, config, tmp, args):
        with unittest.mock.patch.dict(os.environ, {"OPENCODE_DATA": tmp}):
            with unittest.mock.patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                argv, _, _, _ = aweswitch.prepare_run(
                    config, "oc-test", args, {"OC_KEY": "sk-test"}
                )
        return mock_stderr.getvalue()

    def test_prepare_opencode_warns_when_resume_keeps_previous_model(self):
        config = self._make_oc_config()
        with tempfile.TemporaryDirectory() as tmp:
            self._make_oc_db(tmp, "ses_abc", ["opencode/x-preview-f-free"])

            stderr = self._prepare_oc_resume(
                config, tmp, ["glm-5.1", "-s", "ses_abc"]
            )

            self.assertIn(
                "warning: opencode resumes ses_abc with its previous model "
                "(opencode/x-preview-f-free) and ignores -m",
                stderr,
            )
            self.assertIn("To use oc-test/glm-5.1", stderr)

    def test_prepare_opencode_silent_when_resume_model_matches(self):
        config = self._make_oc_config()
        with tempfile.TemporaryDirectory() as tmp:
            self._make_oc_db(tmp, "ses_abc", ["oc-test/glm-5.1"])

            stderr = self._prepare_oc_resume(
                config, tmp, ["glm-5.1", "-s", "ses_abc"]
            )

            self.assertEqual(stderr, "")

    def test_prepare_opencode_resolves_partial_session_id(self):
        config = self._make_oc_config()
        with tempfile.TemporaryDirectory() as tmp:
            self._make_oc_db(tmp, "ses_abcI", ["opencode/x-preview-f-free"])

            stderr = self._prepare_oc_resume(
                config, tmp, ["glm-5.1", "-s", "ses_abc"]
            )

            self.assertIn("resumes ses_abc with its previous model", stderr)

    def test_prepare_opencode_accepts_long_session_flag(self):
        config = self._make_oc_config()
        with tempfile.TemporaryDirectory() as tmp:
            self._make_oc_db(tmp, "ses_abc", ["opencode/x-preview-f-free"])

            stderr = self._prepare_oc_resume(
                config, tmp, ["glm-5.1", "--session=ses_abc"]
            )

            self.assertIn("resumes ses_abc with its previous model", stderr)

    def test_prepare_opencode_silent_when_last_user_message_lacks_model(self):
        config = self._make_oc_config()
        with tempfile.TemporaryDirectory() as tmp:
            self._make_oc_db(tmp, "ses_abc", [None])

            stderr = self._prepare_oc_resume(
                config, tmp, ["glm-5.1", "-s", "ses_abc"]
            )

            self.assertEqual(stderr, "")

    def test_prepare_opencode_silent_without_session_or_db(self):
        config = self._make_oc_config()
        with tempfile.TemporaryDirectory() as tmp:
            # no -s flag
            self.assertEqual(self._prepare_oc_resume(config, tmp, ["glm-5.1"]), "")
            # -s flag but no opencode.db in the data dir
            self.assertEqual(
                self._prepare_oc_resume(config, tmp, ["glm-5.1", "-s", "ses_missing"]), ""
            )

    def test_parse_version_accepts_prerelease_suffix(self):
        self.assertEqual(update_check._parse_version("0.3.0a1"), (0, 3, 0))
        self.assertTrue(update_check._version_gte("0.3.0a1", "0.3.0"))
        self.assertTrue(update_check._version_gte("0.3.0", "0.3.0a1"))

    def test_write_settings_file_removes_old_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            settings_dir = tmp_root / "aweswitch"
            settings_dir.mkdir()
            old_file = settings_dir / "aweswitch-settings-old.json"
            old_file.write_text("{}")
            old_time = time.time() - (25 * 60 * 60)
            os.utime(old_file, (old_time, old_time))

            with unittest.mock.patch("tempfile.gettempdir", return_value=tmp):
                settings_path = aweswitch.write_settings_file({"env": {"A": "B"}})

            self.assertFalse(old_file.exists())
            self.assertTrue(settings_path.exists())
            self.assertEqual(json.loads(settings_path.read_text()), {"env": {"A": "B"}})

    def test_apply_stops_if_backup_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(json.dumps({"env": {"OLD": "value"}}) + "\n")
            config_path.write_text(json.dumps({
                "profiles": {
                    "api": {
                        "claude": {
                            "cc-test": {
                                "env": {
                                    "ANTHROPIC_BASE_URL": "https://example.test",
                                    "ANTHROPIC_AUTH_TOKEN": "${TOKEN}",
                                    "ANTHROPIC_MODEL": "model",
                                }
                            }
                        }
                    }
                }
            }) + "\n")

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path), \
                 unittest.mock.patch("aweswitch.cli.shutil.copy2", side_effect=OSError("disk full")):
                result = CliRunner().invoke(
                    aweswitch.cli,
                    ["apply", "cc-test"],
                    env={"AWESWITCH_CONFIG": str(config_path), "TOKEN": "secret"},
                )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("failed to create backup", result.output)
            self.assertEqual(json.loads(settings_path.read_text()), {"env": {"OLD": "value"}})

    def test_apply_claude_creates_missing_settings_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "new-claude-home" / "settings.json"
            config = self._make_apply_config()

            result, _ = self._apply(
                ["apply", "cc-test"], config, tmp,
                extra_env={"CLAUDE_SETTINGS": str(settings_path)},
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(settings_path.exists())
            self.assert_settings_file_secure(settings_path)

    def test_apply_claude_removes_stale_mutually_exclusive_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(json.dumps({"env": {
                "ANTHROPIC_API_KEY": "stale",
                "KEEP_ME": "yes",
            }}) + "\n")

            result, _ = self._apply(
                ["apply", "cc-test"], self._make_apply_config(), tmp,
                extra_env={"CLAUDE_SETTINGS": str(settings_path)},
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Removed stale ANTHROPIC_API_KEY (not in new profile)", result.output)
            env = json.loads(settings_path.read_text())["env"]
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "secret")
            self.assertEqual(env["KEEP_ME"], "yes")

    def test_apply_claude_masks_stale_subagent_model(self):
        # Regression: apply merges into settings.json env, so a subagent pin
        # left by a different provider must be overwritten with the explicit
        # fall-through value instead of surviving the profile switch.
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text(json.dumps({"env": {
                "CLAUDE_CODE_SUBAGENT_MODEL": "old-gateway/leaked-model",
                "KEEP_ME": "yes",
            }}) + "\n")

            result, _ = self._apply(
                ["apply", "cc-test"], self._make_apply_config(), tmp,
                extra_env={"CLAUDE_SETTINGS": str(settings_path)},
            )

            self.assertEqual(result.exit_code, 0, result.output)
            env = json.loads(settings_path.read_text())["env"]
            self.assertEqual(env["CLAUDE_CODE_SUBAGENT_MODEL"], "inherit")
            self.assertEqual(env["KEEP_ME"], "yes")

    def test_profile_model_label_shows_available_models_for_opencode(self):
        profile = {"env": {"OPENCODE_MODEL": {"glm-5.1": "GLM-5.1", "glm-5.2": "GLM-5.2"}}}
        label = aweswitch.profile_model_label("opencode", profile)
        self.assertIn("glm-5.1", label)
        self.assertIn("glm-5.2", label)

    def test_profile_model_label_shows_string_models_for_opencode(self):
        profile = {"env": {"OPENCODE_MODEL": "glm-5.1, glm-5.2"}}
        label = aweswitch.profile_model_label("opencode", profile)
        self.assertIn("glm-5.1", label)
        self.assertIn("glm-5.2", label)

    def test_profile_model_label_shows_list_models_for_opencode(self):
        profile = {"env": {"OPENCODE_MODEL": ["glm-5.1", "glm-5.2"]}}
        label = aweswitch.profile_model_label("opencode", profile)
        self.assertIn("glm-5.1", label)
        self.assertIn("glm-5.2", label)

    def test_profile_model_label_shows_auto_for_opencode(self):
        profile = {"env": {"OPENCODE_MODEL": "auto"}}
        self.assertEqual(aweswitch.profile_model_label("opencode", profile), "auto")

    def test_init_creates_opencode_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"

            aweswitch.init_config(path)

            data = json.loads(path.read_text())
            self.assertIn("opencode", data["profiles"]["api"])
            self.assertIn("oc-glm", data["profiles"]["api"]["opencode"])
            env = data["profiles"]["api"]["opencode"]["oc-glm"]["env"]
            self.assertNotIn("OPENCODE_PROVIDER", env)
            self.assertIsInstance(env["OPENCODE_MODEL"], dict)
            self.assertIn("glm-5.1", env["OPENCODE_MODEL"])

    def test_ensure_opencode_provider_creates_new_provider_with_env_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://new.com/v1",
                                                   "{env:MY_KEY}", "oc-doubao", {"doubao-1": "Doubao 1"})

            self.assertEqual(status, "created")
            data = json.loads(oc_path.read_text())
            prov = data["provider"]["oc-doubao"]
            self.assertEqual(prov["options"]["baseURL"], "https://new.com/v1")
            self.assertEqual(prov["options"]["apiKey"], "{env:MY_KEY}")
            self.assertEqual(prov["models"]["doubao-1"]["name"], "Doubao 1")
            self.assertEqual(prov["models"]["doubao-1"]["attachment"], True)
            self.assertEqual(prov["models"]["doubao-1"]["modalities"],
                             {"input": ["text", "image"], "output": ["text"]})
            self.assertEqual(prov["models"]["doubao-1"]["variants"], {
                effort: {"reasoningEffort": effort}
                for effort in ("low", "medium", "high", "xhigh", "max")
            })
            managed = json.loads(
                oc_path.with_name(".aweswitch-managed-providers.json").read_text()
            )
            self.assertEqual(managed, {"providers": ["oc-doubao"]})
            self.assert_settings_file_secure(
                oc_path.with_name(".aweswitch-managed-providers.json")
            )

    def test_ensure_opencode_provider_backfills_default_modalities(self):
        """Entries written before the modalities/attachment defaults (and fresh
        models) get the declaration on the next write; hand-set values win."""
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://zhipu.com/v1", "apiKey": "{env:GLM_KEY}"},
                    "models": {
                        "glm-5.1": {"name": "glm-5.1"},
                        "glm-text": {"name": "GLM Text", "attachment": False,
                                     "modalities": {"input": ["text"], "output": ["text"]}},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm",
                                                   {"glm-5.1": "glm-5.1", "glm-text": "GLM Text"})

            self.assertEqual(status, "updated")
            models = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]
            variants = {
                effort: {"reasoningEffort": effort}
                for effort in ("low", "medium", "high", "xhigh", "max")
            }
            self.assertEqual(models["glm-5.1"], {
                "name": "glm-5.1",
                "attachment": True,
                "modalities": {"input": ["text", "image"], "output": ["text"]},
                "variants": variants,
            })
            self.assertEqual(models["glm-text"], {
                "name": "GLM Text",
                "attachment": False,
                "modalities": {"input": ["text"], "output": ["text"]},
                "variants": variants,
            })

    def test_ensure_opencode_provider_backfills_reasoning_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://zhipu.com/v1", "apiKey": "{env:GLM_KEY}"},
                    "models": {"glm-5.1": {"name": "glm-5.1", "variants": {
                        "low": {"reasoningEffort": "minimal"},
                        "turbo": {"reasoningEffort": "high"},
                    }}}
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider(
                    "https://zhipu.com/v1", "{env:GLM_KEY}", "oc-glm",
                    {"glm-5.1": "glm-5.1"})

            self.assertEqual(status, "updated")
            variants = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]["glm-5.1"]["variants"]
            self.assertEqual(variants["low"], {"reasoningEffort": "minimal"})
            self.assertEqual(variants["turbo"], {"reasoningEffort": "high"})
            self.assertEqual(set(variants), {"low", "medium", "high", "xhigh", "max", "turbo"})
            for effort in ("medium", "high", "xhigh", "max"):
                self.assertEqual(variants[effort], {"reasoningEffort": effort})

    def test_ensure_opencode_provider_variants_only_touch_managed_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            foreign = {"name": "foreign", "variants": {"custom": {"reasoningEffort": "high"}}}
            oc_path.write_text(json.dumps({"provider": {"oc-glm": {
                "name": "oc-glm",
                "options": {"baseURL": "https://x/v1", "apiKey": "{env:KEY}"},
                "models": {"managed": {"name": "managed"}, "foreign": foreign},
            }}}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                aweswitch.ensure_opencode_provider(
                    "https://x/v1", "{env:KEY}", "oc-glm", {"managed": "managed"})

            models = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]
            self.assertIn("variants", models["managed"])
            self.assertEqual(models["foreign"], foreign)

    def test_ensure_opencode_provider_adds_model_to_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://zhipu.com/v1", "apiKey": "{env:GLM_KEY}"},
                    "models": {"glm-5.1": {"name": "glm-5.1"}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm", {"glm-5.2": "glm-5.2"})

            data = json.loads(oc_path.read_text())
            self.assertIn("glm-5.2", data["provider"]["oc-glm"]["models"])
            self.assertIn("glm-5.1", data["provider"]["oc-glm"]["models"])

    def test_ensure_opencode_provider_skips_if_model_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            declared = {"name": "glm-5.1", "attachment": True,
                        "modalities": {"input": ["text", "image"], "output": ["text"]},
                        "variants": {
                            effort: {"reasoningEffort": effort}
                            for effort in ("low", "medium", "high", "xhigh", "max")
                        }}
            original = {"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://zhipu.com/v1", "apiKey": "{env:GLM_KEY}"},
                    "models": {"glm-5.1": declared},
                }
            }
            }
            original_text = json.dumps(original, indent=2) + "\n"
            oc_path.write_text(original_text)

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm", {"glm-5.1": "glm-5.1"})

            self.assertEqual(status, "unchanged")
            self.assertEqual(oc_path.read_text(), original_text)

    def test_ensure_opencode_provider_updates_stale_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://old.com/v1", "apiKey": "sk-old"},
                    "models": {"glm-5.1": {"name": "glm-5.1"}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://new.com/v1",
                                                   "{env:NEW_KEY}", "oc-glm", {"glm-5.1": "glm-5.1"})

            self.assertEqual(status, "updated")
            data = json.loads(oc_path.read_text())
            prov = data["provider"]["oc-glm"]
            self.assertEqual(prov["options"]["baseURL"], "https://new.com/v1")
            self.assertEqual(prov["options"]["apiKey"], "{env:NEW_KEY}")
            self.assertIn("glm-5.1", prov["models"])

    def test_ensure_opencode_provider_prunes_models_not_in_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://zhipu.com/v1", "apiKey": "{env:GLM_KEY}"},
                    "models": {"glm-5.1": {"name": "glm-5.1"}, "glm-stale": {"name": "glm-stale"}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm",
                                                   {"glm-5.1": "glm-5.1"}, prune=True)

            models = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]
            self.assertEqual(list(models), ["glm-5.1"])

    def test_ensure_opencode_provider_prune_reorders_to_config_order(self):
        """apply (prune=True) makes the config's model order authoritative:
        the opencode.json key order — the picker order — is rebuilt to match,
        with per-model hand-set values preserved. Launch (no prune) never
        reorders; it stays additive."""
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://zhipu.com/v1", "apiKey": "{env:GLM_KEY}"},
                    "models": {
                        "glm-5.1": {"name": "glm-5.1", "attachment": False},
                        "glm-5.2": {"name": "glm-5.2"},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm",
                                                   {"glm-5.2": "glm-5.2", "glm-5.1": "glm-5.1"},
                                                   prune=True)

            self.assertEqual(status, "updated")
            models = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]
            self.assertEqual(list(models), ["glm-5.2", "glm-5.1"])
            self.assertIs(models["glm-5.1"]["attachment"], False)

            # launch path: the selected model must not jump the queue
            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm",
                                                   {"glm-5.1": "glm-5.1"})
            models = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]
            self.assertEqual(list(models), ["glm-5.2", "glm-5.1"])

    def test_ensure_opencode_provider_apply_stamps_release_dates_in_config_order(self):
        """OpenCode's picker sorts by release_date (newest first) and ignores
        key order. apply stamps descending dates in config order — the first
        model leads the picker and becomes the provider default — and
        reconciles a hand-set date that contradicts the config order. Launch
        never stamps, so it cannot reshuffle the picker."""
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "oc-glm",
                    "options": {"baseURL": "https://zhipu.com/v1", "apiKey": "{env:GLM_KEY}"},
                    "models": {
                        "glm-5.1": {"name": "glm-5.1", "release_date": "2020-01-01"},
                        "glm-5.2": {"name": "glm-5.2"},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm",
                                                   {"glm-5.2": "glm-5.2", "glm-5.1": "glm-5.1"},
                                                   prune=True)

            self.assertEqual(status, "updated")
            models = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]
            dates = [models[m]["release_date"] for m in ("glm-5.2", "glm-5.1")]
            self.assertEqual(dates, sorted(dates, reverse=True))
            self.assertNotEqual(dates[0], dates[1])
            self.assertGreater(dates[0], "2020-01-01")  # hand-set date reconciled

            # idempotent: a second apply changes nothing
            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm",
                                                   {"glm-5.2": "glm-5.2", "glm-5.1": "glm-5.1"},
                                                   prune=True)
            self.assertEqual(status, "unchanged")

            # launch path: an added model gets no date, existing dates untouched
            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm",
                                                   {"glm-5.3": "glm-5.3"})
            models = json.loads(oc_path.read_text())["provider"]["oc-glm"]["models"]
            self.assertNotIn("release_date", models["glm-5.3"])
            self.assertEqual(models["glm-5.2"]["release_date"], dates[0])

    def test_ensure_opencode_provider_repairs_hand_edited_shapes(self):
        """Hand-edited entries (plain-string model, non-object options/models) must
        not crash; they get repaired to the aweswitch shape in place."""
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "options": "oops",
                    "models": {"glm-5.1": "plain string", "keep": {"name": "Keep"}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://zhipu.com/v1",
                                                   "{env:GLM_KEY}", "oc-glm", {"glm-5.1": "GLM-5.1"})

            self.assertEqual(status, "updated")
            prov = json.loads(oc_path.read_text())["provider"]["oc-glm"]
            self.assertEqual(prov["options"]["baseURL"], "https://zhipu.com/v1")
            self.assertEqual(prov["models"]["glm-5.1"], {
                "name": "GLM-5.1",
                "attachment": True,
                "modalities": {"input": ["text", "image"], "output": ["text"]},
                "variants": {
                    effort: {"reasoningEffort": effort}
                    for effort in ("low", "medium", "high", "xhigh", "max")
                },
            })
            self.assertEqual(prov["models"]["keep"], {"name": "Keep"})

    def test_ensure_opencode_provider_refuses_to_clobber_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            original = '{ "provider": { broken json ,,'
            oc_path.write_text(original)

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                with self.assertRaisesRegex(SystemExit, "invalid JSON"):
                    aweswitch.ensure_opencode_provider("https://new.com/v1",
                                                       "{env:KEY}", "oc-x", {"m-1": "m-1"})

            self.assertEqual(oc_path.read_text(), original)

    def test_ensure_opencode_provider_reverts_responses_npm_when_flag_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-chat": {
                    "name": "oc-chat",
                    "npm": "@ai-sdk/openai",
                    "options": {"baseURL": "https://x/v1", "apiKey": "{env:KEY}", "setCacheKey": True},
                    "models": {"m-1": {"name": "m-1"}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://x/v1",
                                                            "{env:KEY}", "oc-chat", {"m-1": "m-1"})

            self.assertEqual(status, "updated")
            prov = json.loads(oc_path.read_text())["provider"]["oc-chat"]
            self.assertEqual(prov["npm"], "@ai-sdk/openai-compatible")

    def test_ensure_opencode_provider_leaves_foreign_npm_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-anthropic": {
                    "name": "oc-anthropic",
                    "npm": "@ai-sdk/anthropic",
                    "options": {"baseURL": "https://x/v1", "apiKey": "{env:KEY}"},
                    "models": {"m-1": {"name": "m-1", "attachment": True,
                                       "modalities": {"input": ["text", "image"], "output": ["text"]},
                                       "variants": {
                                           effort: {"reasoningEffort": effort}
                                           for effort in ("low", "medium", "high", "xhigh", "max")
                                       }}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider("https://x/v1",
                                                            "{env:KEY}", "oc-anthropic", {"m-1": "m-1"})

            self.assertEqual(status, "unchanged")
            prov = json.loads(oc_path.read_text())["provider"]["oc-anthropic"]
            self.assertEqual(prov["npm"], "@ai-sdk/anthropic")

    def test_opencode_responses_models_parsing(self):
        parse = lambda raw: aweswitch._parse_responses_models(
            raw, "oc-t", "OPENCODE_RESPONSES_MODEL")
        self.assertEqual(parse(None), [])
        self.assertEqual(parse(""), [])
        self.assertEqual(parse([]), [])
        self.assertEqual(parse("peng1/x"), ["peng1/x"])
        self.assertEqual(parse(" peng1/x , peng1/y "), ["peng1/x", "peng1/y"])
        self.assertEqual(parse(["peng1/y"]), ["peng1/y"])
        self.assertEqual(parse(["b", "a", "b"]), ["b", "a"])  # order kept, deduped
        with self.assertRaisesRegex(SystemExit, "OPENCODE_RESPONSES_MODEL must be"):
            parse({"peng1/x": "x"})

    def test_zcode_responses_models_bad_shape_names_zcode_key(self):
        with self.assertRaisesRegex(SystemExit, "ZCODE_RESPONSES_MODEL must be"):
            aweswitch._parse_responses_models(
                {"r1": "R1"}, "zc-t", "ZCODE_RESPONSES_MODEL")

    def test_merge_opencode_models_order_is_deterministic(self):
        # responses-only profile: configured order is the model order
        merged, resp = aweswitch._merge_opencode_models(
            {"OPENCODE_RESPONSES_MODEL": ["b", "a"]}, "oc-t")
        self.assertEqual(list(merged), ["b", "a"])
        self.assertEqual(resp, ["b", "a"])

        # mixed profile: whichever field is written first in env leads the dict
        merged, resp = aweswitch._merge_opencode_models(
            {"OPENCODE_MODEL": {"hub/a": "A", "hub/b": "B"},
             "OPENCODE_RESPONSES_MODEL": "peng1/x"}, "oc-t")
        self.assertEqual(list(merged), ["hub/a", "hub/b", "peng1/x"])
        merged, resp = aweswitch._merge_opencode_models(
            {"OPENCODE_RESPONSES_MODEL": "peng1/x",
             "OPENCODE_MODEL": {"hub/a": "A", "hub/b": "B"}}, "oc-t")
        self.assertEqual(list(merged), ["peng1/x", "hub/a", "hub/b"])
        with self.assertRaisesRegex(SystemExit, "must not be listed in both"):
            aweswitch._merge_opencode_models(
                {"OPENCODE_MODEL": {"peng1/x": "X Display"},
                 "OPENCODE_RESPONSES_MODEL": "peng1/x,peng1/y"}, "oc-t")

    def test_zcode_models_resolve_chat_field_to_provider_kind(self):
        models, kind = aweswitch._resolve_zcode_models(
            {"chat": "Chat"}, None, "zc-test")
        self.assertEqual(models, {"chat": "Chat"})
        self.assertEqual(kind, "openai-compatible")

        models, kind = aweswitch._resolve_zcode_models(
            None, ["r1", "r2"], "zc-test")
        self.assertEqual(models, {"r1": "r1", "r2": "r2"})
        self.assertEqual(kind, "openai")

    def test_zcode_models_reject_both_fields(self):
        with self.assertRaisesRegex(SystemExit, "not both"):
            aweswitch._resolve_zcode_models("chat1", ["resp1"], "zc-test")

    def test_ensure_opencode_provider_stamps_per_model_responses_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider(
                    "https://x/v1", "{env:KEY}", "oc-mix",
                    {"peng1/x": "x", "peng1/y": "y"},
                    responses_models={"peng1/x"})

            self.assertEqual(status, "created")
            models = json.loads(oc_path.read_text())["provider"]["oc-mix"]["models"]
            self.assertEqual(models["peng1/x"]["provider"], {"npm": "@ai-sdk/openai"})
            self.assertNotIn("provider", models["peng1/y"])
            self.assertEqual(
                json.loads(oc_path.read_text())["provider"]["oc-mix"]["npm"],
                "@ai-sdk/openai-compatible",
            )

    def test_ensure_opencode_provider_removes_stale_per_model_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-mix": {
                    "name": "oc-mix",
                    "npm": "@ai-sdk/openai-compatible",
                    "options": {"baseURL": "https://x/v1", "apiKey": "{env:KEY}", "setCacheKey": True},
                    "models": {
                        "peng1/x": {"name": "peng1/x", "provider": {"npm": "@ai-sdk/openai"}},
                        "peng1/y": {"name": "y"},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider(
                    "https://x/v1", "{env:KEY}", "oc-mix",
                    {"peng1/x": "x", "peng1/y": "y"})

            self.assertEqual(status, "updated")
            models = json.loads(oc_path.read_text())["provider"]["oc-mix"]["models"]
            self.assertNotIn("provider", models["peng1/x"])

    def test_ensure_opencode_provider_keeps_hand_set_model_npm(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            declared = {"attachment": True,
                        "modalities": {"input": ["text", "image"], "output": ["text"]},
                        "variants": {
                            effort: {"reasoningEffort": effort}
                            for effort in ("low", "medium", "high", "xhigh", "max")
                        }}
            oc_path.write_text(json.dumps({"provider": {
                "oc-mix": {
                    "name": "oc-mix",
                    "npm": "@ai-sdk/openai-compatible",
                    "options": {"baseURL": "https://x/v1", "apiKey": "{env:KEY}", "setCacheKey": True},
                    "models": {
                        "peng1/x": {"name": "peng1/x", "provider": {"npm": "@ai-sdk/cerebras"}, **declared},
                        "peng1/y": {"name": "peng1/y", **declared},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                status = aweswitch.ensure_opencode_provider(
                    "https://x/v1", "{env:KEY}", "oc-mix",
                    {"peng1/x": "x", "peng1/y": "y"})

            self.assertEqual(status, "unchanged")
            models = json.loads(oc_path.read_text())["provider"]["oc-mix"]["models"]
            self.assertEqual(models["peng1/x"]["provider"], {"npm": "@ai-sdk/cerebras"})

    def test_ensure_opencode_provider_launch_additive_keeps_other_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-mix": {
                    "name": "oc-mix",
                    "npm": "@ai-sdk/openai-compatible",
                    "options": {"baseURL": "https://x/v1", "apiKey": "{env:KEY}", "setCacheKey": True},
                    "models": {
                        "peng1/x": {"name": "peng1/x", "provider": {"npm": "@ai-sdk/openai"}},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                # launch of another model (no prune, only that model managed)
                aweswitch.ensure_opencode_provider(
                    "https://x/v1", "{env:KEY}", "oc-mix", {"peng1/y": "y"})

            models = json.loads(oc_path.read_text())["provider"]["oc-mix"]["models"]
            self.assertEqual(models["peng1/x"]["provider"], {"npm": "@ai-sdk/openai"})

    def test_sync_applies_responses_model_overrides(self):
        config = self._make_sync_config()
        env = config["profiles"]["api"]["opencode"]["oc-glm"]["env"]
        env["OPENCODE_RESPONSES_MODEL"] = ["glm-5.3"]

        _, data = self._sync(config)

        models = data["provider"]["oc-glm"]["models"]
        self.assertEqual(models["glm-5.3"]["provider"], {"npm": "@ai-sdk/openai"})
        self.assertNotIn("provider", models["glm-5.1"])

    def test_sync_clearing_responses_model_removes_override(self):
        config = self._make_sync_config()
        env = config["profiles"]["api"]["opencode"]["oc-glm"]["env"]
        env["OPENCODE_RESPONSES_MODEL"] = ["glm-5.3"]

        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._sync(config, oc_path=oc_path)

            del env["OPENCODE_RESPONSES_MODEL"]
            results, data = self._sync(config, oc_path=oc_path)

            self.assertEqual(results[0], ("oc-glm", "updated", 2, []))
            self.assertNotIn("glm-5.3", data["provider"]["oc-glm"]["models"])

    def test_sync_responses_model_overrides_are_idempotent(self):
        config = self._make_sync_config()
        env = config["profiles"]["api"]["opencode"]["oc-glm"]["env"]
        env["OPENCODE_RESPONSES_MODEL"] = "glm-5.3"

        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._sync(config, oc_path=oc_path)
            text_after_first = oc_path.read_text()

            results, _ = self._sync(config, oc_path=oc_path)

            self.assertEqual(results[0], ("oc-glm", "unchanged", 3, []))
            self.assertEqual(oc_path.read_text(), text_after_first)

    def test_sync_allows_responses_model_without_opencode_model(self):
        config = self._make_sync_config()
        env = config["profiles"]["api"]["opencode"]["oc-glm"]["env"]
        del env["OPENCODE_MODEL"]
        env["OPENCODE_RESPONSES_MODEL"] = "glm-5.2"

        results, data = self._sync(config)

        self.assertEqual(results[0], ("oc-glm", "created", 1, []))
        self.assertEqual(
            {m: v["name"] for m, v in data["provider"]["oc-glm"]["models"].items()},
            {"glm-5.2": "glm-5.2"},
        )
        self.assertEqual(
            data["provider"]["oc-glm"]["models"]["glm-5.2"]["provider"],
            {"npm": "@ai-sdk/openai"},
        )

    # --- sync (opencode profiles -> opencode.json) ---

    def _make_sync_config(self):
        return {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-glm": {"env": {"ANTHROPIC_BASE_URL": "https://x", "ANTHROPIC_AUTH_TOKEN": "t"}},
                    },
                    "opencode": {
                        "oc-glm": {"env": {
                            "OPENCODE_BASE_URL": "https://zhipu.com/v1",
                            "OPENCODE_API_KEY": "${GLM_KEY}",
                            "OPENCODE_NAME": "Zhipu GLM",
                            "OPENCODE_MODEL": {"glm-5.1": "GLM-5.1", "glm-5.2": "GLM-5.2"},
                        }},
                        "oc-xiaomi": {"env": {
                            "OPENCODE_BASE_URL": "https://xiaomi.com/v1",
                            "OPENCODE_API_KEY": "${MIMO_KEY}",
                            "OPENCODE_MODEL": ["mimo-v2.5", "mimo-v2.5-pro"],
                        }},
                    },
                }
            }
        }

    def _sync(self, config, names=None, oc_path=None):
        oc_path = oc_path or (Path(tempfile.mkdtemp()) / "opencode.json")
        if not oc_path.exists():
            oc_path.write_text(json.dumps({"provider": {}}))
        with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
            results = aweswitch.sync_opencode_profiles(config, names)
        return results, json.loads(oc_path.read_text())

    def test_edit_agent_model_line_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            agents_dir = Path(tmp) / "agents"
            agents_dir.mkdir()

            replace = agents_dir / "a.md"
            replace.write_text("---\ndescription: x\nmodel: old/old\n---\nbody\n")
            self.assertTrue(aweswitch._edit_agent_model_line(replace, "new/new"))
            self.assertEqual(replace.read_text(), "---\ndescription: x\nmodel: new/new\n---\nbody\n")
            self.assertFalse(aweswitch._edit_agent_model_line(replace, "new/new"))

            insert = agents_dir / "b.md"
            insert.write_text("---\ndescription: x\n---\nbody\n")
            self.assertTrue(aweswitch._edit_agent_model_line(insert, "n/m"))
            self.assertEqual(insert.read_text(), "---\ndescription: x\nmodel: n/m\n---\nbody\n")

            create = agents_dir / "c.md"
            create.write_text("body only\n")
            self.assertTrue(aweswitch._edit_agent_model_line(create, "n/m"))
            self.assertEqual(create.read_text(), "---\nmodel: n/m\n---\nbody only\n")

            self.assertTrue(aweswitch._edit_agent_model_line(replace, None))
            self.assertEqual(replace.read_text(), "---\ndescription: x\n---\nbody\n")
            self.assertFalse(aweswitch._edit_agent_model_line(replace, None))

    def test_parse_subagent_pins_forms(self):
        config = self._make_sync_config()

        config["subagents"] = {"opencode": {"explore": "oc-glm/glm-5.1"}}
        self.assertEqual(
            aweswitch.parse_subagent_pins(config, "opencode"),
            {"explore": "oc-glm/glm-5.1"})

        config["subagents"] = {"opencode": {"explore": "oc-xiaomi/mimo-v2.5"}}
        self.assertEqual(
            aweswitch.parse_subagent_pins(config, "opencode"),
            {"explore": "oc-xiaomi/mimo-v2.5"})

        # Slash-bearing model ids split at the first slash only.
        config["profiles"]["api"]["opencode"]["oc-glm"]["env"]["OPENCODE_MODEL"]["hub/x"] = "hub x"
        config["subagents"] = {"opencode": {"explore": "oc-glm/hub/x"}}
        self.assertEqual(
            aweswitch.parse_subagent_pins(config, "opencode"),
            {"explore": "oc-glm/hub/x"})

        config["subagents"] = {"opencode": {"explore": "oc-glm/nope"}}
        with self.assertRaisesRegex(SystemExit, "not in"):
            aweswitch.parse_subagent_pins(config, "opencode")

        config["subagents"] = {"opencode": {"explore": "cc-glm/x"}}
        with self.assertRaisesRegex(SystemExit, "not an api profile under profiles.api.opencode"):
            aweswitch.parse_subagent_pins(config, "opencode")

        config["subagents"] = {"opencode": {"explore": "ghost/m"}}
        with self.assertRaisesRegex(SystemExit, "not an api profile under profiles.api.opencode"):
            aweswitch.parse_subagent_pins(config, "opencode")

        config["subagents"] = {"opencode": {"explore": "oc-xiaomi/missing"}}
        with self.assertRaisesRegex(SystemExit, "not in profile oc-xiaomi"):
            aweswitch.parse_subagent_pins(config, "opencode")

        config["subagents"] = {"opencode": {"explore": "glm-5.1"}}
        with self.assertRaisesRegex(SystemExit, "profile/model-id"):
            aweswitch.parse_subagent_pins(config, "opencode")

        config["subagents"] = {"claude": {"x": "cc-glm/m"}}
        with self.assertRaisesRegex(SystemExit, "supports targets"):
            aweswitch.parse_subagent_pins(config, "opencode")

    def test_migrate_subagents_folds_env_pins_into_section(self):
        config = {
            "profiles": {"api": {
                "opencode": {"oc-glm": {"env": {
                    "OPENCODE_BASE_URL": "https://zhipu.com/v1",
                    "OPENCODE_API_KEY": "${GLM_KEY}",
                    "OPENCODE_MODEL": ["glm-5.1"],
                    "OPENCODE_SUBAGENT_MODEL": {
                        "explore": "glm-5.1", "general": "@oc-xiaomi/mimo-v2.5"},
                }}},
                "zcode": {"zc-a": {"env": {
                    "ZCODE_BASE_URL": "https://a.test/v1",
                    "ZCODE_API_KEY": "${A_KEY}",
                    "ZCODE_CHAT_MODEL": ["m1"],
                    "ZCODE_SUBAGENT_MODEL": {"review": "m1", "search": "@zc-b/n1"},
                }}},
            }},
        }

        changed = aweswitch.migrate_subagents(config)

        self.assertTrue(changed)
        env = config["profiles"]["api"]["opencode"]["oc-glm"]["env"]
        self.assertNotIn("OPENCODE_SUBAGENT_MODEL", env)
        self.assertEqual(config["subagents"]["opencode"], {
            "explore": "oc-glm/glm-5.1",
            "general": "oc-xiaomi/mimo-v2.5",
        })
        zc_env = config["profiles"]["api"]["zcode"]["zc-a"]["env"]
        self.assertNotIn("ZCODE_SUBAGENT_MODEL", zc_env)
        self.assertEqual(config["subagents"]["zcode"], {
            "review": "zc-a/m1",
            "search": "zc-b/n1",
        })

    def test_migrate_subagents_expands_zcode_scalar_to_builtins(self):
        config = {"profiles": {"api": {"zcode": {"zc-a": {"env": {
            "ZCODE_BASE_URL": "https://a.test/v1",
            "ZCODE_API_KEY": "${A_KEY}",
            "ZCODE_CHAT_MODEL": ["m1"],
            "ZCODE_SUBAGENT_MODEL": "m1",
        }}}}}}

        changed = aweswitch.migrate_subagents(config)

        self.assertTrue(changed)
        self.assertNotIn("ZCODE_SUBAGENT_MODEL",
                         config["profiles"]["api"]["zcode"]["zc-a"]["env"])
        self.assertEqual(config["subagents"]["zcode"], {
            "general-purpose": "zc-a/m1",
            "Explore": "zc-a/m1",
        })

    def test_migrate_subagents_ignores_config_without_env_pins(self):
        config = {"profiles": {"api": {"opencode": {"oc-glm": {"env": {
            "OPENCODE_BASE_URL": "https://zhipu.com/v1",
            "OPENCODE_API_KEY": "${GLM_KEY}",
            "OPENCODE_MODEL": ["glm-5.1"],
        }}}}}, "subagents": {"opencode": {"explore": "oc-glm/glm-5.1"}}}

        self.assertFalse(aweswitch.migrate_subagents(config))
        self.assertEqual(config["subagents"]["opencode"], {"explore": "oc-glm/glm-5.1"})

    def _sync_agents(self, config, names=None, oc_path=None):
        if not oc_path.exists():
            oc_path.write_text(json.dumps({"provider": {}}))
        with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
            results = aweswitch.sync_opencode_profiles(config, names)
        return results, json.loads(oc_path.read_text())

    def test_sync_pins_and_releases_agent_model_lines(self):
        config = self._make_sync_config()
        config["subagents"] = {"opencode": {"explore": "oc-glm/glm-5.1"}}
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            agents_dir = oc_path.parent / "agents"
            agents_dir.mkdir()
            (agents_dir / "explore.md").write_text(
                "---\ndescription: scout\nmodel: hand/pinned\n---\nbody stays\n")

            results, _ = self._sync_agents(config, oc_path=oc_path)
            self.assertEqual(results[0][3], ["pinned agent 'explore' -> oc-glm/glm-5.1"])
            self.assertEqual(
                (agents_dir / "explore.md").read_text(),
                "---\ndescription: scout\nmodel: oc-glm/glm-5.1\n---\nbody stays\n")
            sidecar = json.loads(
                (oc_path.parent / ".aweswitch-managed-providers.json").read_text())
            self.assertEqual(sidecar["agents"], ["explore"])

            # Applying another profile keeps the pin the section still
            # declares (and ensures oc-glm's provider so the pin keeps
            # resolving).
            results, data = self._sync_agents(config, names=["oc-xiaomi"], oc_path=oc_path)
            self.assertEqual(results[0][3], [])
            self.assertIn("oc-glm", data["provider"])
            self.assertIn("oc-xiaomi", data["provider"])
            self.assertEqual(
                (agents_dir / "explore.md").read_text(),
                "---\ndescription: scout\nmodel: oc-glm/glm-5.1\n---\nbody stays\n")

            # The pin is released only once the section no longer names it.
            del config["subagents"]["opencode"]["explore"]
            results, _ = self._sync_agents(config, names=["oc-xiaomi"], oc_path=oc_path)
            self.assertEqual(
                results[0][3], ["released agent 'explore' (inherits primary model)"])
            self.assertEqual(
                (agents_dir / "explore.md").read_text(),
                "---\ndescription: scout\n---\nbody stays\n")

    def test_sync_opencode_creates_and_deletes_templated_agents(self):
        config = self._make_sync_config()
        config["subagents"] = {"opencode": {"ghost": "oc-glm/glm-5.1"}}
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"

            # A declared agent with no file is created from the template.
            results, _ = self._sync_agents(config, oc_path=oc_path)
            self.assertEqual(
                results[0][3], ["created agent 'ghost' from template -> oc-glm/glm-5.1"])
            self.assertEqual(
                (oc_path.parent / "agents" / "ghost.md").read_text(),
                aweswitch.OPENCODE_AGENT_TEMPLATE.format(
                    model="glm-5.1", ref="oc-glm/glm-5.1"))
            sidecar = json.loads(
                (oc_path.parent / ".aweswitch-managed-providers.json").read_text())
            self.assertEqual(sidecar["agents"], ["ghost"])
            self.assertEqual(sidecar["createdAgents"], ["ghost"])

            # Removing the entry deletes the file aweswitch created.
            del config["subagents"]["opencode"]["ghost"]
            results, _ = self._sync_agents(config, oc_path=oc_path)
            self.assertEqual(
                results[0][3], ["deleted agent 'ghost' (created by aweswitch)"])
            self.assertFalse((oc_path.parent / "agents" / "ghost.md").exists())
            sidecar = json.loads(
                (oc_path.parent / ".aweswitch-managed-providers.json").read_text())
            self.assertEqual(sidecar["agents"], [])
            self.assertEqual(sidecar["createdAgents"], [])

    def test_sync_opencode_pin_ensures_dep_provider(self):
        config = self._make_sync_config()
        config["subagents"] = {"opencode": {"explore": "oc-xiaomi/mimo-v2.5"}}
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            agents_dir = oc_path.parent / "agents"
            agents_dir.mkdir()
            (agents_dir / "explore.md").write_text("---\ndescription: scout\n---\nbody\n")

            results, data = self._sync_agents(config, names=["oc-glm"], oc_path=oc_path)

            self.assertIn("oc-xiaomi", data["provider"])
            self.assertEqual(
                (agents_dir / "explore.md").read_text(),
                "---\ndescription: scout\nmodel: oc-xiaomi/mimo-v2.5\n---\nbody\n")
            self.assertEqual(results[0][3], ["pinned agent 'explore' -> oc-xiaomi/mimo-v2.5"])

    def test_managed_sidecar_agents_key_backcompat(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / ".aweswitch-managed-providers.json"
            sidecar.write_text(json.dumps({"providers": ["oc-old"]}))
            with unittest.mock.patch("aweswitch.cli.managed_opencode_path", return_value=sidecar):
                self.assertEqual(aweswitch.load_managed_opencode_agents(), set())
                aweswitch.set_managed_opencode_agents({"explore"})
                self.assertEqual(aweswitch.load_managed_opencode_providers(), {"oc-old"})
                self.assertEqual(aweswitch.load_managed_opencode_agents(), {"explore"})

    def _make_zcode_subagent_config(self):
        return {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-a": {"env": {
                            "ZCODE_BASE_URL": "https://a.test/v1",
                            "ZCODE_API_KEY": "${A_KEY}",
                            "ZCODE_CHAT_MODEL": {"m1": "M1"},
                        }},
                        "zc-b": {"env": {
                            "ZCODE_BASE_URL": "https://b.test/v1",
                            "ZCODE_API_KEY": "${B_KEY}",
                            "ZCODE_CHAT_MODEL": ["n1"],
                        }},
                    }
                }
            },
            "subagents": {"zcode": {
                "general-purpose": "zc-a/m1",
                "Explore": "zc-a/m1",
            }},
        }

    def test_sync_zcode_pins_and_releases_builtin_overrides(self):
        config = self._make_zcode_subagent_config()
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))
            state_path = zc_path.with_name("agents-state.json")
            state_path.write_text(json.dumps({
                "builtInModelOverrides": {"custom-agent": "user/pin"},
                "builtInThoughtLevelOverrides": {},
                "disabledAgentIds": ["judge"],
            }))

            env = {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a", "B_KEY": "b"}
            with unittest.mock.patch.dict(os.environ, env):
                with unittest.mock.patch("aweswitch.cli.zcode_app_running", return_value=False):
                    results = aweswitch.sync_zcode_profiles(config, ["zc-a"])

            self.assertEqual(results[0][3], [
                "pinned built-in agent 'Explore' -> zc-a/m1",
                "pinned built-in agent 'general-purpose' -> zc-a/m1",
            ])
            state = json.loads(state_path.read_text())
            self.assertEqual(state["builtInModelOverrides"], {
                "custom-agent": "user/pin",
                "Explore": "custom:zc-a:m1",
                "general-purpose": "custom:zc-a:m1",
            })
            self.assertEqual(state["disabledAgentIds"], ["judge"])

            # Applying another profile keeps the override the section still
            # declares (and ensures zc-a's provider so the override keeps
            # resolving).
            with unittest.mock.patch.dict(os.environ, env):
                with unittest.mock.patch("aweswitch.cli.zcode_app_running", return_value=False):
                    results = aweswitch.sync_zcode_profiles(config, ["zc-b"])

            self.assertEqual(results[0][3], [])
            self.assertIn("zc-a", json.loads(zc_path.read_text())["provider"])
            state = json.loads(state_path.read_text())
            self.assertEqual(state["builtInModelOverrides"], {
                "custom-agent": "user/pin",
                "Explore": "custom:zc-a:m1",
                "general-purpose": "custom:zc-a:m1",
            })

            # The pin is released only once the section no longer names it.
            del config["subagents"]["zcode"]["general-purpose"]
            del config["subagents"]["zcode"]["Explore"]
            with unittest.mock.patch.dict(os.environ, env):
                with unittest.mock.patch("aweswitch.cli.zcode_app_running", return_value=False):
                    results = aweswitch.sync_zcode_profiles(config, ["zc-b"])

            self.assertEqual(results[0][3], [
                "released built-in agent 'Explore' (inherits session model)",
                "released built-in agent 'general-purpose' (inherits session model)",
            ])
            state = json.loads(state_path.read_text())
            self.assertEqual(state["builtInModelOverrides"], {"custom-agent": "user/pin"})
            self.assertEqual(state["disabledAgentIds"], ["judge"])

    def test_zcode_override_value_encodes_like_the_app(self):
        self.assertEqual(
            aweswitch._zcode_override_value("zc-a/m1"), "custom:zc-a:m1")
        self.assertEqual(
            aweswitch._zcode_override_value("zc-a/hub/deepseek-v4-flash"),
            "custom:zc-a:hub%2Fdeepseek-v4-flash")

    def _make_zcode_user_agent_config(self):
        return {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-a": {"env": {
                            "ZCODE_BASE_URL": "https://a.test/v1",
                            "ZCODE_API_KEY": "${A_KEY}",
                            "ZCODE_CHAT_MODEL": {"m1": "M1", "m2": "M2"},
                        }},
                        "zc-b": {"env": {
                            "ZCODE_BASE_URL": "https://b.test/v1",
                            "ZCODE_API_KEY": "${B_KEY}",
                            "ZCODE_CHAT_MODEL": ["n1"],
                        }},
                    }
                }
            },
            "subagents": {"zcode": {
                "review": "zc-a/m1",
                "search": "zc-b/n1",
            }},
        }

    def _make_zcode_user_agent_dirs(self, tmp):
        """Real layout: config under v2/, user agents beside it in agents/."""
        root = Path(tmp)
        v2 = root / "v2"
        v2.mkdir()
        zc_path = v2 / "config.json"
        zc_path.write_text(json.dumps({"provider": {}}))
        agents = root / "agents"
        agents.mkdir()
        (agents / "review.md").write_text(
            "---\nname: review\ndescription: code reviewer\nmodel: custom:old/pin\n---\nbody\n")
        (agents / "search.md").write_text(
            "---\nname: search\ndescription: fast search\n---\nbody\n")
        return zc_path, agents, v2 / ".aweswitch-managed-providers.json"

    def test_sync_zcode_pins_named_user_agents(self):
        config = self._make_zcode_user_agent_config()
        with tempfile.TemporaryDirectory() as tmp:
            zc_path, agents, sidecar_path = self._make_zcode_user_agent_dirs(tmp)
            env = {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a", "B_KEY": "b"}
            with unittest.mock.patch.dict(os.environ, env):
                with unittest.mock.patch("aweswitch.cli.zcode_app_running", return_value=False):
                    results = aweswitch.sync_zcode_profiles(config, ["zc-a"])

            self.assertEqual(results[0][3], [
                "pinned agent 'review' -> zc-a/m1",
                "pinned agent 'search' -> zc-b/n1",
            ])
            self.assertEqual(
                (agents / "review.md").read_text(),
                "---\nname: review\ndescription: code reviewer\n"
                "model: custom:zc-a:m1\n---\nbody\n")
            self.assertEqual(
                (agents / "search.md").read_text(),
                "---\nname: search\ndescription: fast search\n"
                "model: custom:zc-b:n1\n---\nbody\n")
            sidecar = json.loads(sidecar_path.read_text())
            self.assertEqual(sidecar["userAgents"], ["review", "search"])
            self.assertNotIn("agents", sidecar)
            # The dict form never touches the built-in overrides.
            self.assertFalse(zc_path.with_name("agents-state.json").exists())

    def test_sync_zcode_creates_and_deletes_templated_user_agents(self):
        config = self._make_zcode_user_agent_config()
        config["subagents"]["zcode"]["ghost"] = "zc-a/m2"
        with tempfile.TemporaryDirectory() as tmp:
            zc_path, agents, sidecar_path = self._make_zcode_user_agent_dirs(tmp)
            env = {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a", "B_KEY": "b"}
            with unittest.mock.patch.dict(os.environ, env):
                results = aweswitch.sync_zcode_profiles(config, ["zc-a"])

            self.assertEqual(results[0][3], [
                "created agent 'ghost' from template -> zc-a/m2",
                "pinned agent 'review' -> zc-a/m1",
                "pinned agent 'search' -> zc-b/n1",
            ])
            self.assertEqual(
                (agents / "ghost.md").read_text(),
                aweswitch.ZCODE_AGENT_TEMPLATE.format(
                    name="ghost", model="m2", value="custom:zc-a:m2"))
            sidecar = json.loads(sidecar_path.read_text())
            self.assertEqual(sidecar["userAgents"], ["ghost", "review", "search"])
            self.assertEqual(sidecar["createdUserAgents"], ["ghost"])

            # Removing the entry deletes the template-created file; the
            # hand-authored ones are only released.
            config["subagents"]["zcode"] = {}
            with unittest.mock.patch.dict(os.environ, env):
                results = aweswitch.sync_zcode_profiles(config, ["zc-a"])
            self.assertEqual(results[0][3], [
                "deleted agent 'ghost' (created by aweswitch)",
                "released agent 'review' (inherits session model)",
                "released agent 'search' (inherits session model)",
            ])
            self.assertFalse((agents / "ghost.md").exists())
            self.assertTrue((agents / "review.md").exists())
            sidecar = json.loads(sidecar_path.read_text())
            self.assertEqual(sidecar["userAgents"], [])
            self.assertEqual(sidecar["createdUserAgents"], [])

    def test_sync_zcode_user_agents_release_on_field_removal(self):
        config = self._make_zcode_user_agent_config()
        with tempfile.TemporaryDirectory() as tmp:
            zc_path, agents, sidecar_path = self._make_zcode_user_agent_dirs(tmp)
            env = {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a", "B_KEY": "b"}
            with unittest.mock.patch.dict(os.environ, env):
                aweswitch.sync_zcode_profiles(config, ["zc-a"])

            config["subagents"]["zcode"] = {}
            with unittest.mock.patch.dict(os.environ, env):
                results = aweswitch.sync_zcode_profiles(config, ["zc-a"])

            self.assertEqual(results[0][3], [
                "released agent 'review' (inherits session model)",
                "released agent 'search' (inherits session model)",
            ])
            self.assertEqual(
                (agents / "review.md").read_text(),
                "---\nname: review\ndescription: code reviewer\n---\nbody\n")
            self.assertEqual(
                (agents / "search.md").read_text(),
                "---\nname: search\ndescription: fast search\n---\nbody\n")
            self.assertEqual(json.loads(sidecar_path.read_text())["userAgents"], [])

    def test_sync_zcode_builtins_and_user_agents_mixed(self):
        config = self._make_zcode_user_agent_config()
        config["subagents"]["zcode"]["general-purpose"] = "zc-a/m2"
        config["subagents"]["zcode"]["Explore"] = "zc-b/n1"
        with tempfile.TemporaryDirectory() as tmp:
            zc_path, agents, sidecar_path = self._make_zcode_user_agent_dirs(tmp)
            state_path = zc_path.with_name("agents-state.json")
            env = {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a", "B_KEY": "b"}
            with unittest.mock.patch.dict(os.environ, env):
                with unittest.mock.patch("aweswitch.cli.zcode_app_running", return_value=False):
                    results = aweswitch.sync_zcode_profiles(config, ["zc-a"])

            self.assertEqual(results[0][3], [
                "pinned built-in agent 'Explore' -> zc-b/n1",
                "pinned built-in agent 'general-purpose' -> zc-a/m2",
                "pinned agent 'review' -> zc-a/m1",
                "pinned agent 'search' -> zc-b/n1",
            ])
            self.assertEqual(json.loads(state_path.read_text())["builtInModelOverrides"], {
                "general-purpose": "custom:zc-a:m2",
                "Explore": "custom:zc-b:n1",
            })
            self.assertIn("model: custom:zc-a:m1\n", (agents / "review.md").read_text())
            sidecar = json.loads(sidecar_path.read_text())
            self.assertEqual(sidecar["agents"], ["Explore", "general-purpose"])
            self.assertEqual(sidecar["userAgents"], ["review", "search"])

            # Removing just the built-in entries releases only those pins.
            del config["subagents"]["zcode"]["general-purpose"]
            del config["subagents"]["zcode"]["Explore"]
            with unittest.mock.patch.dict(os.environ, env):
                with unittest.mock.patch("aweswitch.cli.zcode_app_running", return_value=False):
                    results = aweswitch.sync_zcode_profiles(config, ["zc-a"])
            self.assertEqual(results[0][3], [
                "released built-in agent 'Explore' (inherits session model)",
                "released built-in agent 'general-purpose' (inherits session model)",
            ])
            self.assertEqual(
                json.loads(state_path.read_text())["builtInModelOverrides"], {})
            sidecar = json.loads(sidecar_path.read_text())
            self.assertEqual(sidecar["agents"], [])
            self.assertEqual(sidecar["userAgents"], ["review", "search"])


    def test_sync_writes_all_opencode_profiles_with_full_model_lists(self):
        results, data = self._sync(self._make_sync_config())

        self.assertEqual(results, [
            ("oc-glm", "created", 2, []),
            ("oc-xiaomi", "created", 2, []),
        ])
        glm = data["provider"]["oc-glm"]
        self.assertEqual(glm["name"], "Zhipu GLM")
        self.assertEqual(glm["options"]["baseURL"], "https://zhipu.com/v1")
        self.assertEqual(glm["options"]["apiKey"], "{env:GLM_KEY}")
        self.assertEqual(
            {m: v["name"] for m, v in glm["models"].items()},
            {"glm-5.1": "GLM-5.1", "glm-5.2": "GLM-5.2"},
        )
        mimo = data["provider"]["oc-xiaomi"]
        self.assertEqual(mimo["name"], "oc-xiaomi")  # no OPENCODE_NAME -> profile name
        self.assertEqual(
            {m: v["name"] for m, v in mimo["models"].items()},
            {"mimo-v2.5": "mimo-v2.5", "mimo-v2.5-pro": "mimo-v2.5-pro"},
        )

    def test_sync_prunes_stale_models_and_updates_credentials(self):
        config = self._make_sync_config()
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {
                "oc-glm": {
                    "name": "Old Name",
                    "options": {"baseURL": "https://old.com/v1", "apiKey": "sk-old"},
                    "models": {"glm-5.1": {"name": "glm-5.1"}, "glm-stale": {"name": "glm-stale"}},
                },
                "opencode": {"options": {}, "models": {}},  # foreign provider stays untouched
            }}))

            results, data = self._sync(config, oc_path=oc_path)

            self.assertEqual(results[0], ("oc-glm", "updated", 2, []))
            glm = data["provider"]["oc-glm"]
            self.assertEqual(glm["name"], "Zhipu GLM")
            self.assertEqual(glm["options"]["baseURL"], "https://zhipu.com/v1")
            self.assertEqual(list(glm["models"]), ["glm-5.1", "glm-5.2"])
            self.assertIn("opencode", data["provider"])  # not an aweswitch profile

    def test_sync_named_profiles_only(self):
        results, data = self._sync(self._make_sync_config(), names=["oc-glm"])

        self.assertEqual(results, [("oc-glm", "created", 2, [])])
        self.assertIn("oc-glm", data["provider"])
        self.assertNotIn("oc-xiaomi", data["provider"])

    def test_sync_second_run_is_unchanged(self):
        config = self._make_sync_config()
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            first_results, _ = self._sync(config, oc_path=oc_path)
            text_after_first = oc_path.read_text()

            second_results, _ = self._sync(config, oc_path=oc_path)

            self.assertEqual([r[1] for r in first_results], ["created", "created"])
            self.assertEqual([r[1] for r in second_results], ["unchanged", "unchanged"])
            self.assertEqual(oc_path.read_text(), text_after_first)

    def test_sync_rejects_non_opencode_profile(self):
        with self.assertRaisesRegex(SystemExit, "sync only supports opencode api profiles"):
            self._sync(self._make_sync_config(), names=["cc-glm"])

    def test_sync_rejects_unknown_profile(self):
        with self.assertRaisesRegex(SystemExit, "unknown profile"):
            self._sync(self._make_sync_config(), names=["oc-nope"])

    def test_sync_validates_all_profiles_before_writing_any(self):
        config = self._make_sync_config()
        config["profiles"]["api"]["opencode"]["oc-broken"] = {"env": {
            "OPENCODE_BASE_URL": "${OC_URL_MISSING}",
            "OPENCODE_API_KEY": "${K}",
            "OPENCODE_MODEL": ["m"],
        }}
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch("aweswitch.cli.opencode_config_path", return_value=oc_path):
                with self.assertRaisesRegex(SystemExit, "OC_URL_MISSING"):
                    aweswitch.sync_opencode_profiles(config)

            # nothing was written even though oc-glm sorted before oc-broken
            self.assertEqual(json.loads(oc_path.read_text()), {"provider": {}})

    # ------------------------------------------------------------------
    # zcode tests
    # ------------------------------------------------------------------

    def test_ensure_zcode_provider_creates_new_provider_with_env_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/anthropic",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["GLM-5.3-Flash", "GLM-Turbo"],
                    display_name="BigModel - Coding Plan",
                )

            self.assertEqual(status, "created")
            data = json.loads(zc_path.read_text())
            prov = data["provider"]["zc-glm"]
            self.assertEqual(prov["name"], "BigModel - Coding Plan")
            self.assertEqual(prov["kind"], "openai-compatible")
            self.assertEqual(prov["options"]["baseURL"], "https://open.bigmodel.cn/api/anthropic")
            self.assertEqual(prov["options"]["apiKey"], "{env:GLM_KEY}")
            self.assertTrue(prov["enabled"])
            self.assertEqual(prov["source"], "custom")
            self.assertEqual(prov["models"]["GLM-5.3-Flash"]["name"], "GLM-5.3-Flash")
            self.assertEqual(prov["models"]["GLM-5.3-Flash"]["limit"],
                             {"context": 1000000, "output": 128000})
            self.assertEqual(prov["models"]["GLM-5.3-Flash"]["modalities"],
                             {"input": ["text", "image"], "output": ["text"]})
            self.assertTrue(prov["models"]["GLM-5.3-Flash"]["zcode"]["modalitiesConfigured"])
            self.assertNotIn("kind", prov["models"]["GLM-5.3-Flash"])
            managed = json.loads(
                zc_path.with_name(".aweswitch-managed-providers.json").read_text()
            )
            self.assertEqual(managed, {"providers": ["zc-glm"]})
            self.assert_settings_file_secure(
                zc_path.with_name(".aweswitch-managed-providers.json")
            )

    def test_ensure_zcode_provider_backfills_default_modalities(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "anthropic",
                    "options": {
                        "baseURL": "https://open.bigmodel.cn/api/anthropic",
                        "apiKey": "{env:GLM_KEY}",
                    },
                    "models": {
                        "GLM-5.3-Flash": {"name": "GLM-5.3-Flash"},
                        "GLM-text": {"name": "GLM Text", "modalities": {"input": ["text"], "output": ["text"]}},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/anthropic",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["GLM-5.3-Flash", "GLM-text"],
                    display_name="BigModel - Coding Plan",
                )

            self.assertEqual(status, "updated")
            prov = json.loads(zc_path.read_text())["provider"]["zc-glm"]
            self.assertEqual(prov["kind"], "openai-compatible")
            models = prov["models"]
            self.assertEqual(models["GLM-5.3-Flash"], {
                "name": "GLM-5.3-Flash",
                "limit": {"context": 1000000, "output": 128000},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
                "zcode": {"modalitiesConfigured": True},
                "reasoning": aweswitch._zcode_default_reasoning(),
            })
            self.assertEqual(models["GLM-text"], {
                "name": "GLM Text",
                "limit": {"context": 1000000, "output": 128000},
                "modalities": {"input": ["text"], "output": ["text"]},
                "zcode": {"modalitiesConfigured": True},
                "reasoning": aweswitch._zcode_default_reasoning(),
            })

    def test_zcode_default_reasoning_shape(self):
        """The stamped block is a plain reasoning dict — the only form zcode
        keeps for custom providers — with none (the canonical effort name
        that actually turns thinking off on the wire) leading the ladder."""
        block = aweswitch._zcode_default_reasoning()
        self.assertEqual(block, {
            "enabled": True,
            "variants": ["none", "low", "medium", "high", "xhigh", "max"],
            "defaultVariant": "medium",
        })

    def test_ensure_zcode_provider_migrates_legacy_default_reasoning(self):
        """aweswitch's own older plain fill (low..max, max selected) gains
        the none level; nothing else about the entry changes."""
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "openai-compatible",
                    "options": {
                        "baseURL": "https://open.bigmodel.cn/api/paas/v4",
                        "apiKey": "{env:GLM_KEY}",
                    },
                    "models": {
                        "glm-5.3": {
                            "name": "glm-5.3",
                            "reasoning": {
                                "enabled": True,
                                "variants": ["low", "medium", "high", "xhigh", "max"],
                                "defaultVariant": "max",
                            },
                        },
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/paas/v4",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["glm-5.3"],
                )

            self.assertEqual(status, "updated")
            model = json.loads(zc_path.read_text())["provider"]["zc-glm"]["models"]["glm-5.3"]
            self.assertEqual(model["reasoning"], aweswitch._zcode_default_reasoning())
            self.assertEqual(model["zcode"], {"modalitiesConfigured": True})

    def test_ensure_zcode_provider_migrates_legacy_reasoning_spec(self):
        """The unreleased build's zcode.reasoning spec — inert in zcode and
        stripped by its next save — is replaced by the plain block; a
        hand-written spec is never touched."""
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "openai-compatible",
                    "options": {
                        "baseURL": "https://open.bigmodel.cn/api/paas/v4",
                        "apiKey": "{env:GLM_KEY}",
                    },
                    "models": {
                        "glm-5.3": {
                            "name": "glm-5.3",
                            "zcode": {"reasoning": aweswitch._legacy_zcode_reasoning_spec()},
                        },
                        "glm-5.3-flash": {
                            "name": "glm-5.3-flash",
                            "zcode": {"reasoning": {"levels": {"off": {}}}},
                        },
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/paas/v4",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["glm-5.3", "glm-5.3-flash"],
                )

            self.assertEqual(status, "updated")
            models = json.loads(zc_path.read_text())["provider"]["zc-glm"]["models"]
            self.assertEqual(models["glm-5.3"]["reasoning"],
                             aweswitch._zcode_default_reasoning())
            self.assertNotIn("reasoning", models["glm-5.3"]["zcode"])
            self.assertEqual(models["glm-5.3-flash"]["zcode"],
                             {"reasoning": {"levels": {"off": {}}},
                              "modalitiesConfigured": True})
            self.assertNotIn("reasoning", models["glm-5.3-flash"])

    def test_ensure_zcode_provider_preserves_hand_set_reasoning(self):
        """A hand-written variants list wins wholesale: never edited, appended
        to, or reordered; missing sibling keys are still filled, and an
        explicit reasoning: false opt-out is left alone."""
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "openai-compatible",
                    "options": {
                        "baseURL": "https://open.bigmodel.cn/api/anthropic",
                        "apiKey": "{env:GLM_KEY}",
                    },
                    "models": {
                        "glm-5.3": {"name": "glm-5.3",
                                    "reasoning": {"variants": ["off", "high", "max"]}},
                        "glm-turbo": {"name": "glm-turbo", "reasoning": False},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/anthropic",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["glm-5.3", "glm-turbo"],
                )

            self.assertEqual(status, "updated")
            models = json.loads(zc_path.read_text())["provider"]["zc-glm"]["models"]
            self.assertEqual(models["glm-5.3"]["reasoning"], {
                "enabled": True,
                "variants": ["off", "high", "max"],
                "defaultVariant": "medium",
            })
            self.assertFalse(models["glm-turbo"]["reasoning"])

    def test_ensure_zcode_provider_stamps_reasoning_for_responses_kind(self):
        """Responses models get the same default reasoning block as chat
        models — the plain shape zcode itself persists for them — so both
        kinds offer the same think/off ladder; hand-set blocks still win."""
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-x": {
                    "name": "zc-x",
                    "kind": "openai",
                    "options": {
                        "baseURL": "https://x/v1",
                        "apiKey": "{env:KEY}",
                    },
                    "models": {
                        "m-hand": {"name": "m-hand",
                                   "reasoning": {"variants": ["off", "high"]}},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://x/v1", "{env:KEY}", "zc-x", "openai",
                    ["m-new", "m-hand"])

            self.assertEqual(status, "updated")
            models = json.loads(zc_path.read_text())["provider"]["zc-x"]["models"]
            self.assertEqual(models["m-new"]["reasoning"],
                             aweswitch._zcode_default_reasoning())
            self.assertEqual(models["m-hand"]["reasoning"], {
                "enabled": True,
                "variants": ["off", "high"],
                "defaultVariant": "medium",
            })

    def test_ensure_zcode_provider_updates_stale_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "openai",
                    "options": {
                        "baseURL": "https://old.com/v1",
                        "apiKey": "sk-old",
                    },
                    "models": {"GLM-5.3-Flash": {"name": "GLM-5.3-Flash"}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/anthropic",
                    "{env:NEW_KEY}", "zc-glm", "openai-compatible",
                    ["GLM-5.3-Flash"],
                    display_name="BigModel - Coding Plan",
                )

            self.assertEqual(status, "updated")
            data = json.loads(zc_path.read_text())
            prov = data["provider"]["zc-glm"]
            self.assertEqual(prov["options"]["baseURL"], "https://open.bigmodel.cn/api/anthropic")
            self.assertEqual(prov["options"]["apiKey"], "{env:NEW_KEY}")
            self.assertEqual(prov["kind"], "openai-compatible")
            self.assertEqual(prov["name"], "BigModel - Coding Plan")

    def test_ensure_zcode_provider_prunes_models_not_in_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "anthropic",
                    "options": {
                        "baseURL": "https://open.bigmodel.cn/api/anthropic",
                        "apiKey": "{env:GLM_KEY}",
                    },
                    "models": {
                        "GLM-5.3-Flash": {"name": "GLM-5.3-Flash"},
                        "GLM-stale": {"name": "GLM-stale"},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/anthropic",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["GLM-5.3-Flash"],
                    prune=True,
                )

            models = json.loads(zc_path.read_text())["provider"]["zc-glm"]["models"]
            self.assertEqual(list(models), ["GLM-5.3-Flash"])

    def test_ensure_zcode_provider_prune_reorders_to_config_order(self):
        """apply makes the config's model order authoritative: the zcode
        config.json key order — the picker order — is rebuilt to match, with
        per-model hand-set values preserved."""
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "openai-compatible",
                    "options": {
                        "baseURL": "https://open.bigmodel.cn/api/anthropic",
                        "apiKey": "{env:GLM_KEY}",
                    },
                    "models": {
                        "GLM-5.3-Flash": {"name": "GLM-5.3-Flash", "limit": {"context": 128000}},
                        "GLM-5.3": {"name": "GLM-5.3"},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/anthropic",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["GLM-5.3", "GLM-5.3-Flash"],
                    prune=True,
                )

            self.assertEqual(status, "updated")
            models = json.loads(zc_path.read_text())["provider"]["zc-glm"]["models"]
            self.assertEqual(list(models), ["GLM-5.3", "GLM-5.3-Flash"])
            self.assertEqual(models["GLM-5.3-Flash"]["limit"], {"context": 128000})

    def test_ensure_zcode_provider_repairs_hand_edited_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "options": "oops",
                    "models": {"GLM-5.3-Flash": "plain string", "keep": {"name": "Keep"}},
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                status = aweswitch.ensure_zcode_provider(
                    "https://open.bigmodel.cn/api/anthropic",
                    "{env:GLM_KEY}", "zc-glm", "openai-compatible",
                    ["GLM-5.3-Flash"],
                )

            self.assertEqual(status, "updated")
            prov = json.loads(zc_path.read_text())["provider"]["zc-glm"]
            self.assertEqual(prov["kind"], "openai-compatible")
            self.assertEqual(prov["options"]["baseURL"], "https://open.bigmodel.cn/api/anthropic")
            self.assertEqual(prov["models"]["GLM-5.3-Flash"]["name"], "GLM-5.3-Flash")
            self.assertTrue(prov["enabled"])
            self.assertEqual(prov["source"], "custom")
            self.assertEqual(prov["models"]["keep"], {"name": "Keep"})

    def test_ensure_zcode_provider_refuses_to_clobber_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            original = '{ "provider": { broken json ,,'
            zc_path.write_text(original)

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                with self.assertRaisesRegex(SystemExit, "invalid JSON"):
                    aweswitch.ensure_zcode_provider(
                        "https://x/v1", "{env:KEY}", "zc-x", "openai-compatible", ["m-1"]
                    )

            self.assertEqual(zc_path.read_text(), original)

    def test_sync_zcode_profiles_writes_all_profiles_with_full_model_lists(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-a": {"env": {
                            "ZCODE_BASE_URL": "https://a.test/v1",
                            "ZCODE_API_KEY": "${A_KEY}",
                            "ZCODE_CHAT_MODEL": {"m1": "M1", "m2": "M2"},
                        }},
                        "zc-b": {"env": {
                            "ZCODE_BASE_URL": "https://b.test/v1",
                            "ZCODE_API_KEY": "${B_KEY}",
                            "ZCODE_CHAT_MODEL": ["n1", "n2"],
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a", "B_KEY": "b"}):
                results = aweswitch.sync_zcode_profiles(config)

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0][0], "zc-a")
            self.assertEqual(results[0][1], "created")
            self.assertEqual(results[0][2], 2)
            self.assertEqual(results[1][0], "zc-b")
            self.assertEqual(results[1][1], "created")
            self.assertEqual(results[1][2], 2)

            data = json.loads(zc_path.read_text())
            self.assertEqual(data["provider"]["zc-a"]["kind"], "openai-compatible")
            self.assertEqual(sorted(data["provider"]["zc-a"]["models"]), ["m1", "m2"])
            self.assertEqual(data["provider"]["zc-b"]["kind"], "openai-compatible")
            self.assertEqual(sorted(data["provider"]["zc-b"]["models"]), ["n1", "n2"])

    def test_sync_zcode_profiles_writes_openai_kind_for_responses_profile(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-resp": {"env": {
                            "ZCODE_BASE_URL": "https://a.test/v1",
                            "ZCODE_API_KEY": "${A_KEY}",
                            "ZCODE_RESPONSES_MODEL": ["resp1"],
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a"}):
                aweswitch.sync_zcode_profiles(config)

            prov = json.loads(zc_path.read_text())["provider"]["zc-resp"]
            self.assertEqual(prov["kind"], "openai")
            self.assertEqual(list(prov["models"]), ["resp1"])
            self.assertNotIn("kind", prov["models"]["resp1"])
            self.assertEqual(prov["models"]["resp1"]["reasoning"],
                             aweswitch._zcode_default_reasoning())

    def test_sync_zcode_profiles_rejects_chat_and_responses_in_one_profile(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-mix": {"env": {
                            "ZCODE_BASE_URL": "https://a.test/v1",
                            "ZCODE_API_KEY": "${A_KEY}",
                            "ZCODE_CHAT_MODEL": ["chat1"],
                            "ZCODE_RESPONSES_MODEL": ["resp1"],
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a"}):
                with self.assertRaisesRegex(SystemExit, "not both"):
                    aweswitch.sync_zcode_profiles(config)

            self.assertEqual(json.loads(zc_path.read_text()), {"provider": {}})

    def test_sync_zcode_profiles_rejects_legacy_zcode_model_field(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-x": {"env": {
                            "ZCODE_BASE_URL": "https://a.test/v1",
                            "ZCODE_API_KEY": "${A_KEY}",
                            "ZCODE_MODEL": "m1",
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a"}):
                with self.assertRaisesRegex(SystemExit, "ZCODE_MODEL is no longer supported"):
                    aweswitch.sync_zcode_profiles(config)

    def test_ensure_zcode_provider_strips_stale_model_kinds_and_updates_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-x": {
                    "name": "zc-x",
                    "kind": "anthropic",
                    "options": {
                        "baseURL": "https://a.test/v1",
                        "apiKey": "{env:A_KEY}",
                    },
                    "models": {
                        "chat1": {"name": "chat1", "kind": "openai"},
                        "chat2": {"name": "chat2", "kind": "openai-compatible"},
                    },
                }
            }}))

            with unittest.mock.patch("aweswitch.cli.zcode_config_path", return_value=zc_path):
                aweswitch.ensure_zcode_provider(
                    "https://a.test/v1", "{env:A_KEY}", "zc-x",
                    "openai-compatible", ["chat1", "chat2"], prune=True,
                )

            prov = json.loads(zc_path.read_text())["provider"]["zc-x"]
            self.assertEqual(prov["kind"], "openai-compatible")
            self.assertNotIn("kind", prov["models"]["chat1"])
            self.assertNotIn("kind", prov["models"]["chat2"])

    def test_sync_zcode_profiles_expands_api_key_reference(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-secret": {"env": {
                            "ZCODE_BASE_URL": "https://zcode.test/v1",
                            "ZCODE_API_KEY": "${ZCODE_TOKEN}",
                            "ZCODE_CHAT_MODEL": "m1",
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch.dict(os.environ, {
                "ZCODE_CONFIG": str(zc_path),
                "ZCODE_TOKEN": "super-secret",
            }):
                aweswitch.sync_zcode_profiles(config)

            provider = json.loads(zc_path.read_text())["provider"]["zc-secret"]
            self.assertEqual(provider["options"]["apiKey"], "super-secret")

    def test_sync_zcode_rejects_non_zcode_profile(self):
        config = self._make_apply_config()
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))
            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path), "X_KEY": "x"}):
                with self.assertRaisesRegex(SystemExit, "sync only supports zcode api profiles"):
                    aweswitch.sync_zcode_profiles(config, ["oc-test"])

    def test_sync_zcode_requires_model(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-x": {"env": {
                            "ZCODE_BASE_URL": "https://x.test/v1",
                            "ZCODE_API_KEY": "${X_KEY}",
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))
            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path)}):
                with self.assertRaisesRegex(SystemExit, "ZCODE_CHAT_MODEL or ZCODE_RESPONSES_MODEL is required"):
                    aweswitch.sync_zcode_profiles(config)

    def test_sync_zcode_rejects_removed_kind_field(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-x": {"env": {
                            "ZCODE_BASE_URL": "https://x.test/v1",
                            "ZCODE_API_KEY": "${X_KEY}",
                            "ZCODE_KIND": "anthropic",
                            "ZCODE_CHAT_MODEL": "m1",
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))
            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path)}):
                with self.assertRaisesRegex(SystemExit, "ZCODE_KIND is no longer supported"):
                    aweswitch.sync_zcode_profiles(config)

    def test_sync_zcode_prunes_models_not_in_config(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-glm": {"env": {
                            "ZCODE_BASE_URL": "https://a.test/v1",
                            "ZCODE_API_KEY": "${A_KEY}",
                            "ZCODE_CHAT_MODEL": "m1",
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-glm": {
                    "name": "zc-glm",
                    "kind": "anthropic",
                    "options": {"baseURL": "https://a.test/v1", "apiKey": "{env:A_KEY}"},
                    "models": {"m1": {"name": "m1"}, "m-stale": {"name": "m-stale"}},
                }
            }}))
            with unittest.mock.patch.dict(os.environ, {"ZCODE_CONFIG": str(zc_path), "A_KEY": "a"}):
                aweswitch.sync_zcode_profiles(config)

            models = json.loads(zc_path.read_text())["provider"]["zc-glm"]["models"]
            self.assertEqual(list(models), ["m1"])

    def test_apply_zcode_profile_upserts_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            config = {
                "profiles": {
                    "api": {
                        "zcode": {
                            "zc-test": {"env": {
                                "ZCODE_BASE_URL": "https://example.test/v1",
                                "ZCODE_API_KEY": "${TOKEN}",
                                "ZCODE_CHAT_MODEL": {"m1": "M1", "m2": "M2"},
                            }},
                        }
                    }
                }
            }
            (Path(tmp) / "config.json").write_text(json.dumps(config) + "\n")
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
                "ZCODE_CONFIG": str(zc_path),
                "TOKEN": "secret",
            }
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(aweswitch.cli, ["apply", "zc-test"], env=env)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("zc-test: created (2 models)", result.output)
            prov = json.loads(zc_path.read_text())["provider"]["zc-test"]
            self.assertEqual(sorted(prov["models"]), ["m1", "m2"])

            # second apply overwrites to match config
            config["profiles"]["api"]["zcode"]["zc-test"]["env"]["ZCODE_CHAT_MODEL"] = {"m1": "M1"}
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(aweswitch.cli, ["apply", "zc-test"], env=env)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("zc-test: updated (1 models)", result.output)
            self.assertEqual(list(json.loads(zc_path.read_text())["provider"]["zc-test"]["models"]), ["m1"])

    def test_apply_zcode_flag_applies_all_zcode_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            config = {
                "profiles": {
                    "api": {
                        "zcode": {
                            "zc-a": {"env": {
                                "ZCODE_BASE_URL": "https://a.test/v1",
                                "ZCODE_API_KEY": "${A_KEY}",
                                "ZCODE_CHAT_MODEL": "m1",
                            }},
                            "zc-b": {"env": {
                                "ZCODE_BASE_URL": "https://b.test/v1",
                                "ZCODE_API_KEY": "${B_KEY}",
                                "ZCODE_CHAT_MODEL": "n1",
                            }},
                        }
                    }
                }
            }
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
                "ZCODE_CONFIG": str(zc_path),
                "A_KEY": "a",
                "B_KEY": "b",
            }
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(aweswitch.cli, ["apply", "--zcode"], env=env)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("zc-a: created (1 models)", result.output)
            self.assertIn("zc-b: created (1 models)", result.output)
            self.assertIn("Synced to", result.output)

    def test_apply_zcode_flag_rejects_profile_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            config = {
                "profiles": {
                    "api": {
                        "zcode": {
                            "zc-test": {"env": {
                                "ZCODE_BASE_URL": "https://x.test/v1",
                                "ZCODE_API_KEY": "${X_KEY}",
                                "ZCODE_CHAT_MODEL": "m1",
                            }},
                        }
                    }
                }
            }
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
                "ZCODE_CONFIG": str(zc_path),
                "X_KEY": "x",
            }
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(aweswitch.cli, ["apply", "--zcode", "zc-test"], env=env)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("pick one", result.output)

    def test_apply_zcode_warns_about_orphaned_aweswitch_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            orphan = {
                "name": "zc-old", "kind": "anthropic",
                "options": {"baseURL": "https://old.com/v1", "apiKey": "sk-old"},
                "models": {"m1": {"name": "m1"}},
            }
            hand_written = {
                "name": "mine", "kind": "openai-compatible",
                "options": {"apiKey": "sk", "baseURL": "https://mine/v1"},
            }
            zc_path.write_text(json.dumps({"provider": {"zc-old": orphan, "mine": hand_written}}))
            managed_path = zc_path.with_name(".aweswitch-managed-providers.json")
            managed_path.write_text(json.dumps({"providers": ["zc-old"]}) + "\n")

            config = {
                "profiles": {
                    "api": {
                        "zcode": {
                            "zc-test": {"env": {
                                "ZCODE_BASE_URL": "https://example.test/v1",
                                "ZCODE_API_KEY": "${TOKEN}",
                                "ZCODE_CHAT_MODEL": "m1",
                            }},
                        }
                    }
                }
            }
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
                "ZCODE_CONFIG": str(zc_path),
                "TOKEN": "secret",
            }
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(aweswitch.cli, ["apply", "--zcode"], env=env)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("orphaned", result.output)
            self.assertIn("zc-old", result.output)
            self.assertIn("--prune orphans", result.output)
            providers = json.loads(zc_path.read_text())["provider"]
            self.assertIn("zc-old", providers)
            self.assertIn("mine", providers)

    def test_apply_zcode_prune_orphans_removes_only_aweswitch_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            orphan = {
                "name": "zc-old", "kind": "anthropic",
                "options": {"baseURL": "https://old.com/v1", "apiKey": "sk-old"},
                "models": {"m1": {"name": "m1"}},
            }
            hand_written = {
                "name": "mine", "kind": "openai-compatible",
                "options": {"apiKey": "sk", "baseURL": "https://mine/v1"},
            }
            zc_path.write_text(json.dumps({"provider": {"zc-old": orphan, "mine": hand_written}}))
            managed_path = zc_path.with_name(".aweswitch-managed-providers.json")
            managed_path.write_text(json.dumps({"providers": ["zc-old"]}) + "\n")

            config = {
                "profiles": {
                    "api": {
                        "zcode": {
                            "zc-test": {"env": {
                                "ZCODE_BASE_URL": "https://example.test/v1",
                                "ZCODE_API_KEY": "${TOKEN}",
                                "ZCODE_CHAT_MODEL": "m1",
                            }},
                        }
                    }
                }
            }
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
                "ZCODE_CONFIG": str(zc_path),
                "TOKEN": "secret",
            }
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(
                aweswitch.cli, ["apply", "--zcode", "--prune", "orphans"], env=env, input="y\n"
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'zc-old'", result.output)
            providers = json.loads(zc_path.read_text())["provider"]
            self.assertNotIn("zc-old", providers)
            self.assertIn("zc-test", providers)
            self.assertIn("mine", providers)
            managed = json.loads(
                zc_path.with_name(".aweswitch-managed-providers.json").read_text()
            )["providers"]
            self.assertNotIn("zc-old", managed)
            self.assertIn("zc-test", managed)

    def test_apply_zcode_prune_requires_confirmation_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            original = {"provider": {"zc-old": {
                "name": "zc-old", "kind": "openai-compatible",
                "options": {"baseURL": "https://old.com/v1", "apiKey": "sk-old"},
            }}}
            zc_path.write_text(json.dumps(original))
            zc_path.with_name(".aweswitch-managed-providers.json").write_text(
                json.dumps({"providers": ["zc-old"]}) + "\n")
            config = {"profiles": {"api": {"zcode": {"zc-test": {"env": {
                "ZCODE_BASE_URL": "https://example.test/v1",
                "ZCODE_API_KEY": "${TOKEN}",
                "ZCODE_CHAT_MODEL": "m1",
            }}}}}}
            config_path = Path(tmp) / "aweswitch-config.json"
            config_path.write_text(json.dumps(config) + "\n")

            result = CliRunner().invoke(
                aweswitch.cli, ["apply", "--zcode", "--prune", "orphans"],
                env={
                    "AWESWITCH_CONFIG": str(config_path),
                    "ZCODE_CONFIG": str(zc_path),
                    "TOKEN": "secret",
                },
                input="n\n",
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Will prune provider 'zc-old'", result.output)
            self.assertIn("Continue pruning? [y/N]", result.output)
            self.assertEqual(json.loads(zc_path.read_text()), original)

    def test_apply_zcode_prune_all_keeps_builtin_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "zcode.json"
            zc_path.write_text(json.dumps({"provider": {
                "builtin:bigmodel": {"name": "BigModel"},
                "zc-old": {"name": "zc-old", "kind": "openai-compatible",
                           "options": {"baseURL": "https://old.com/v1", "apiKey": "sk-old"}},
            }}))
            config = self._make_apply_config()
            config["profiles"]["api"]["zcode"] = {"zc-test": {"env": {
                "ZCODE_BASE_URL": "https://example.test/v1",
                "ZCODE_API_KEY": "${TOKEN}",
                "ZCODE_CHAT_MODEL": "m1",
            }}}

            result, _ = self._apply(
                ["apply", "--zcode", "--prune", "all"], config, tmp,
                extra_env={"ZCODE_CONFIG": str(zc_path)}, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'zc-old'", result.output)
            self.assertNotIn("Pruned provider 'builtin:bigmodel'", result.output)
            self.assertEqual(
                set(json.loads(zc_path.read_text())["provider"]),
                {"builtin:bigmodel", "zc-test"},
            )

    def test_apply_zcode_prune_orphans_keeps_builtin_providers(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "zcode.json"
            zc_path.write_text(json.dumps({"provider": {
                "builtin:bigmodel": {"name": "BigModel"},
            }}))
            zc_path.with_name(".aweswitch-managed-providers.json").write_text(
                json.dumps({"providers": ["builtin:bigmodel"]}) + "\n")
            config = self._make_apply_config()
            config["profiles"]["api"]["zcode"] = {"zc-test": {"env": {
                "ZCODE_BASE_URL": "https://example.test/v1",
                "ZCODE_API_KEY": "${TOKEN}",
                "ZCODE_CHAT_MODEL": "m1",
            }}}

            result, _ = self._apply(
                ["apply", "--zcode", "--prune", "orphans"], config, tmp,
                extra_env={"ZCODE_CONFIG": str(zc_path)})

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Skipping protected zcode built-in provider", result.output)
            self.assertIn(
                "builtin:bigmodel", json.loads(zc_path.read_text())["provider"])

    def test_apply_zcode_prune_refuses_named_builtin_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "zcode.json"
            original = {"provider": {"builtin:bigmodel": {"name": "BigModel"}}}
            zc_path.write_text(json.dumps(original))
            config = self._make_apply_config()
            config["profiles"]["api"]["zcode"] = {"zc-test": {"env": {
                "ZCODE_BASE_URL": "https://example.test/v1",
                "ZCODE_API_KEY": "${TOKEN}",
                "ZCODE_CHAT_MODEL": "m1",
            }}}

            result, _ = self._apply(
                ["apply", "--zcode", "--prune", "builtin:bigmodel"], config, tmp,
                extra_env={"ZCODE_CONFIG": str(zc_path)})

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("cannot remove zcode built-in providers", result.output)
            self.assertEqual(json.loads(zc_path.read_text()), original)

    def test_apply_zcode_prune_refuses_invalid_managed_provider_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            original = {"provider": {"manual": {
                "name": "manual", "kind": "openai",
                "options": {"apiKey": "sk", "baseURL": "https://manual/v1"},
            }}}
            zc_path.write_text(json.dumps(original))
            zc_path.with_name(".aweswitch-managed-providers.json").write_text("{broken")

            config = {
                "profiles": {
                    "api": {
                        "zcode": {
                            "zc-test": {"env": {
                                "ZCODE_BASE_URL": "https://example.test/v1",
                                "ZCODE_API_KEY": "${TOKEN}",
                                "ZCODE_CHAT_MODEL": "m1",
                            }},
                        }
                    }
                }
            }
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
                "ZCODE_CONFIG": str(zc_path),
                "TOKEN": "secret",
            }
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(
                aweswitch.cli, ["apply", "--zcode", "--prune", "orphans"], env=env
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("invalid managed-provider JSON", result.output)
            self.assertEqual(json.loads(zc_path.read_text()), original)

    def test_apply_zcode_named_prune_unknown_name_dies_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "config.json"
            zc_path.write_text(json.dumps({"provider": {}}))
            config = {
                "profiles": {
                    "api": {
                        "zcode": {
                            "zc-test": {"env": {
                                "ZCODE_BASE_URL": "https://example.test/v1",
                                "ZCODE_API_KEY": "${TOKEN}",
                                "ZCODE_CHAT_MODEL": "m1",
                            }},
                        }
                    }
                }
            }
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
                "ZCODE_CONFIG": str(zc_path),
                "TOKEN": "secret",
            }
            (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
            result = CliRunner().invoke(
                aweswitch.cli, ["apply", "--zcode", "--prune", "nope"], env=env
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("no provider 'nope'", result.output)
            self.assertEqual(
                json.loads(zc_path.read_text()), {"provider": {}},
                "the prune name list must be validated before any sync write",
            )

    def _mixed_apply_env(self, tmp, oc_providers=None, zc_providers=None):
        """One opencode + one zcode profile, with both agent config files staged."""
        config = {
            "profiles": {
                "api": {
                    "opencode": {
                        "oc-test": {"env": {
                            "OPENCODE_BASE_URL": "https://example.test/v1",
                            "OPENCODE_API_KEY": "${OC_KEY}",
                            "OPENCODE_MODEL": {"m1": "M1"},
                        }},
                    },
                    "zcode": {
                        "zc-test": {"env": {
                            "ZCODE_BASE_URL": "https://example.test/v1",
                            "ZCODE_API_KEY": "${TOKEN}",
                            "ZCODE_CHAT_MODEL": "m1",
                        }},
                    },
                }
            }
        }
        oc_path = Path(tmp) / "opencode.json"
        oc_path.write_text(json.dumps({"provider": oc_providers or {}}))
        zc_path = Path(tmp) / "zcode.json"
        zc_path.write_text(json.dumps({"provider": zc_providers or {}}))
        env = {
            "AWESWITCH_CONFIG": str(Path(tmp) / "aweswitch-config.json"),
            "OPENCODE_CONFIG": str(oc_path),
            "ZCODE_CONFIG": str(zc_path),
            "OC_KEY": "sk-oc",
            "TOKEN": "secret",
        }
        (Path(tmp) / "aweswitch-config.json").write_text(json.dumps(config) + "\n")
        return oc_path, zc_path, env

    def test_apply_mixed_prune_name_resolves_in_opencode_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(
                tmp, oc_providers={"stale-oc": {"name": "stale-oc", "models": {}}})

            result = CliRunner().invoke(
                aweswitch.cli,
                ["apply", "oc-test", "zc-test", "--prune", "stale-oc"], env=env, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'stale-oc'", result.output)
            self.assertNotIn("stale-oc", json.loads(oc_path.read_text())["provider"])
            self.assertEqual(
                sorted(json.loads(zc_path.read_text())["provider"]), ["zc-test"])

    def test_apply_mixed_prune_name_resolves_in_zcode_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(
                tmp, zc_providers={"stale-zc": {"name": "stale-zc", "models": {}}})

            result = CliRunner().invoke(
                aweswitch.cli,
                ["apply", "oc-test", "zc-test", "--prune", "stale-zc"], env=env, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'stale-zc'", result.output)
            self.assertNotIn("stale-zc", json.loads(zc_path.read_text())["provider"])
            self.assertEqual(
                sorted(json.loads(oc_path.read_text())["provider"]), ["oc-test"])

    def test_apply_mixed_prune_name_in_both_configs_prunes_both(self):
        leftover = {"name": "leftover", "models": {}}
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(
                tmp, oc_providers={"leftover": leftover},
                zc_providers={"leftover": leftover})

            result = CliRunner().invoke(
                aweswitch.cli,
                ["apply", "oc-test", "zc-test", "--prune", "leftover"], env=env, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn("leftover", json.loads(oc_path.read_text())["provider"])
            self.assertNotIn("leftover", json.loads(zc_path.read_text())["provider"])

    def test_apply_mixed_prune_unknown_name_dies_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(tmp)
            oc_before, zc_before = oc_path.read_text(), zc_path.read_text()

            result = CliRunner().invoke(
                aweswitch.cli,
                ["apply", "oc-test", "zc-test", "--prune", "nope"], env=env)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("no provider 'nope'", result.output)
            self.assertEqual(oc_path.read_text(), oc_before)
            self.assertEqual(zc_path.read_text(), zc_before)

    def test_apply_without_arguments_bulk_applies_both_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(tmp)

            result = CliRunner().invoke(aweswitch.cli, ["apply"], env=env)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("oc-test: created (1 models)", result.output)
            self.assertIn("zc-test: created (1 models)", result.output)
            self.assertEqual(sorted(json.loads(oc_path.read_text())["provider"]), ["oc-test"])
            self.assertEqual(sorted(json.loads(zc_path.read_text())["provider"]), ["zc-test"])

    def test_apply_both_flags_run_both_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(tmp)

            result = CliRunner().invoke(
                aweswitch.cli, ["apply", "--opencode", "--zcode"], env=env)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(sorted(json.loads(oc_path.read_text())["provider"]), ["oc-test"])
            self.assertEqual(sorted(json.loads(zc_path.read_text())["provider"]), ["zc-test"])

    def test_apply_bare_prune_name_resolves_in_either_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(
                tmp, oc_providers={"stale-oc": {"name": "stale-oc", "models": {}}})

            result = CliRunner().invoke(
                aweswitch.cli, ["apply", "--prune", "stale-oc"], env=env, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'stale-oc'", result.output)
            self.assertNotIn("stale-oc", json.loads(oc_path.read_text())["provider"])
            self.assertEqual(sorted(json.loads(zc_path.read_text())["provider"]), ["zc-test"])

    def test_apply_bare_dry_run_previews_opencode_and_notes_zcode(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path, zc_path, env = self._mixed_apply_env(
                tmp, oc_providers={"stale-oc": {"name": "stale-oc", "models": {}}})
            oc_before, zc_before = oc_path.read_text(), zc_path.read_text()

            result = CliRunner().invoke(
                aweswitch.cli, ["apply", "--dry-run", "--prune", "stale-oc"], env=env)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Dry run: nothing will be written.", result.output)
            self.assertIn("Would prune provider 'stale-oc'", result.output)
            self.assertIn("no zcode prune preview", result.output)
            self.assertEqual(oc_path.read_text(), oc_before)
            self.assertEqual(zc_path.read_text(), zc_before)

    def test_prepare_run_zcode_rejects_launch(self):
        config = {
            "profiles": {
                "api": {
                    "zcode": {
                        "zc-test": {"env": {
                            "ZCODE_BASE_URL": "https://example.test/v1",
                            "ZCODE_API_KEY": "${TOKEN}",
                            "ZCODE_CHAT_MODEL": "m1",
                        }},
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                "TOKEN": "secret",
            }
            (Path(tmp) / "config.json").write_text(json.dumps(config) + "\n")
            with self.assertRaisesRegex(SystemExit, "zcode is a desktop GUI app"):
                aweswitch.prepare_run(aweswitch.load_config(Path(tmp) / "config.json"), "zc-test", [])

    def test_profile_model_label_for_zcode(self):
        # dict
        label = aweswitch.profile_model_label("zcode", {"env": {"ZCODE_CHAT_MODEL": {"a": "A", "b": "B"}}})
        self.assertEqual(label, "a, b")
        # list
        label = aweswitch.profile_model_label("zcode", {"env": {"ZCODE_CHAT_MODEL": ["a", "b"]}})
        self.assertEqual(label, "a, b")
        # string
        label = aweswitch.profile_model_label("zcode", {"env": {"ZCODE_CHAT_MODEL": "a,b"}})
        self.assertEqual(label, "a, b")
        # responses-only profile falls back to ZCODE_RESPONSES_MODEL
        label = aweswitch.profile_model_label(
            "zcode", {"env": {"ZCODE_RESPONSES_MODEL": ["r1", "r2"]}})
        self.assertEqual(label, "r1, r2")
        # empty
        label = aweswitch.profile_model_label("zcode", {"env": {}})
        self.assertEqual(label, "?")

    def test_apply_mixed_apply_rejects_missing_zcode_model_before_writing_codex(self):
        """preflight is supposed to validate every profile before any target
        file changes. A zcode profile missing both model fields must abort
        the call
        before codex.toml is written — otherwise a mixed apply leaves the
        user with a partial state (codex written, zcode failed)."""
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_apply_config()
            config["profiles"]["api"]["zcode"] = {
                "zc-x": {"env": {
                    "ZCODE_BASE_URL": "https://z/v1",
                    "ZCODE_API_KEY": "${ZKEY}",
                }},
            }
            codex_path = Path(tmp) / "config.toml"
            codex_path.write_text("# original codex\n")

            result, _ = self._apply(
                ["apply", "cx-glm", "zc-x"], config, tmp,
                extra_env={"CODEX_CONFIG": str(codex_path), "ZKEY": "z"},
            )

            self.assertNotEqual(result.exit_code, 0, result.output)
            self.assertIn("ZCODE_CHAT_MODEL or ZCODE_RESPONSES_MODEL is required for zc-x", result.output)
            self.assertEqual(
                codex_path.read_text(), "# original codex\n",
                "codex.toml must not be written when zcode preflight fails",
            )

    def test_auto_bookmark_runs_worker_in_detached_child(self):
        """On POSIX the bookmark worker must run in a forked child, because
        os.execvpe() in exec_agent destroys threads before their first poll."""
        if os.name == "nt":
            self.skipTest("POSIX fork path")
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "done"

            def fake_worker(start_time, category, profile, title):
                marker.write_text(f"{category}/{profile}/{title}")

            with unittest.mock.patch.object(aweswitch, "_bookmark_worker", side_effect=fake_worker):
                aweswitch._auto_bookmark("dev", "cc-x", title="t")

            for _ in range(50):
                if marker.exists():
                    break
                time.sleep(0.1)
            self.assertTrue(marker.exists(), "detached bookmark worker never ran")
            self.assertEqual(marker.read_text(), "dev/cc-x/t")


    # --- official accounts (config schema v2) ---

    def test_load_config_migrates_old_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({
                "profiles": {"claude": {"cc-old": {"env": {"ANTHROPIC_BASE_URL": "https://x"}}}},
            }) + "\n")

            data = aweswitch.load_config(path)

            self.assertEqual(
                data["profiles"]["api"]["claude"]["cc-old"]["env"]["ANTHROPIC_BASE_URL"],
                "https://x",
            )
            saved = json.loads(path.read_text())
            self.assertNotIn("claude", saved["profiles"])
            self.assertTrue((Path(tmp) / "config.json.bak").exists())

    def test_load_config_rejects_mixed_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({
                "profiles": {"api": {}, "claude": {"cc-x": {"env": {}}}},
            }) + "\n")

            with self.assertRaisesRegex(SystemExit, "mixes old and new"):
                aweswitch.load_config(path)

    def test_load_config_keeps_new_layout_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            original = json.dumps({"profiles": {"api": {}, "accounts": {}}}) + "\n"
            path.write_text(original)

            aweswitch.load_config(path)

            self.assertEqual(path.read_text(), original)

    def test_load_config_keeps_empty_profiles_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            original = json.dumps({"profiles": {}}) + "\n"
            path.write_text(original)

            aweswitch.load_config(path)

            self.assertEqual(path.read_text(), original)
            self.assertFalse((Path(tmp) / "config.json.bak").exists())

    def test_profile_for_resolves_kind(self):
        config = {
            "profiles": {
                "api": {"claude": {"cc-glm": {"env": {}}}},
                "accounts": {"codex": {"cxo-work": {"auth": {"tokens": {}}}}},
            },
        }

        provider, kind, entry = aweswitch.profile_for(config, "cc-glm")
        self.assertEqual((provider, kind), ("claude", "api"))
        provider, kind, entry = aweswitch.profile_for(config, "cxo-work")
        self.assertEqual((provider, kind), ("codex", "account"))

    def test_profile_for_rejects_name_reused_across_kinds(self):
        config = {
            "profiles": {
                "api": {"claude": {"dup": {"env": {}}}},
                "accounts": {"codex": {"dup": {"auth": {}}}},
            },
        }

        with self.assertRaisesRegex(SystemExit, "ambiguous profile"):
            aweswitch.profile_for(config, "dup")

    def test_prepare_codex_account_sets_private_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"profiles": {"accounts": {"codex": {
                "cxo-work": {"auth": {"tokens": {"access_token": "t"}}},
            }}}}

            with unittest.mock.patch.dict(os.environ, {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json")}):
                argv, env, _, account_info = aweswitch.prepare_run(config, "cxo-work", ["--verbose"], {})

            self.assertEqual(argv, ["codex", "--verbose"])
            self.assertEqual(env["CODEX_HOME"], str(Path(tmp) / "accounts" / "codex" / "cxo-work"))
            self.assertEqual(account_info["provider"], "codex")
            self.assertEqual(account_info["blob"], {"tokens": {"access_token": "t"}})

    def test_prepare_claude_account_sets_private_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {"profiles": {"accounts": {"claude": {
                "cco-team": {"credentials": {"claudeAiOauth": {"accessToken": "t"}}},
            }}}}

            with unittest.mock.patch.dict(os.environ, {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json")}):
                argv, env, _, account_info = aweswitch.prepare_run(config, "cco-team", [], {})

            self.assertEqual(argv, ["claude"])
            self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(Path(tmp) / "accounts" / "claude" / "cco-team"))
            self.assertEqual(env["CLAUDE_CODE_DONT_USE_KEYCHAIN"], "1")
            self.assertEqual(account_info["provider"], "claude")

    def test_prepare_account_rejects_opencode(self):
        config = {"profiles": {"accounts": {"opencode": {"oco-x": {"auth": {}}}}}}

        with self.assertRaisesRegex(SystemExit, "official accounts are not supported"):
            aweswitch.prepare_run(config, "oco-x", [], {})

    def test_ensure_account_dir_materializes_codex_and_preserves_refreshed_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            live_config = Path(tmp) / "codex-config.toml"
            live_config.write_text('model = "gpt-5.2-codex"\n')
            blob = {"tokens": {"access_token": "old"}}
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                   "CODEX_CONFIG": str(live_config)}
            with unittest.mock.patch.dict(os.environ, env):
                d = aweswitch.ensure_account_dir("codex", "cxo-work", blob)
                cred = d / "auth.json"
                self.assertEqual(json.loads(cred.read_text()), blob)
                self.assert_settings_file_secure(cred)
                self.assertEqual((d / "config.toml").read_text(), 'model = "gpt-5.2-codex"\n')

                # The CLI refreshes tokens inside the dir; the config blob must not clobber them.
                refreshed = {"tokens": {"access_token": "new"}}
                cred.write_text(json.dumps(refreshed))
                aweswitch.ensure_account_dir("codex", "cxo-work", blob)
                self.assertEqual(json.loads(cred.read_text()), refreshed)

                # force=True reseeds the credentials from the config blob.
                aweswitch.ensure_account_dir("codex", "cxo-work", blob, force=True)
                self.assertEqual(json.loads(cred.read_text()), blob)

    def test_ensure_account_dir_materializes_claude_and_seeds_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            live_settings = Path(tmp) / "settings.json"
            live_settings.write_text('{"permissions": {}}\n')
            blob = {"claudeAiOauth": {"accessToken": "t"}}
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                   "CLAUDE_SETTINGS": str(live_settings)}
            with unittest.mock.patch.dict(os.environ, env):
                d = aweswitch.ensure_account_dir("claude", "cco-team", blob)

            self.assertEqual(json.loads((d / ".credentials.json").read_text()), blob)
            self.assert_settings_file_secure(d / ".credentials.json")
            self.assertEqual(json.loads((d / "settings.json").read_text()), {"permissions": {}})

    def test_ensure_account_dir_removes_provider_overrides_from_seed_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_settings = Path(tmp) / "settings.json"
            claude_settings.write_text(json.dumps({
                "permissions": {"allow": ["Read"]},
                "env": {
                    "ANTHROPIC_BASE_URL": "https://third-party.example",
                    "ANTHROPIC_AUTH_TOKEN": "secret",
                    "KEEP_ME": "yes",
                },
            }) + "\n")
            codex_config = Path(tmp) / "config.toml"
            codex_config.write_text(
                'model = "gpt-5"\n'
                'model_provider = "relay"\n\n'
                '[model_providers.relay]\n'
                'base_url = "https://third-party.example/v1"\n'
                'wire_api = "responses"\n\n'
                '[mcp_servers.docs]\n'
                'command = "docs-mcp"\n'
            )
            env = {
                "AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                "CLAUDE_SETTINGS": str(claude_settings),
                "CODEX_CONFIG": str(codex_config),
            }
            with unittest.mock.patch.dict(os.environ, env):
                claude_dir = aweswitch.ensure_account_dir("claude", "cco-work", {})
                codex_dir = aweswitch.ensure_account_dir("codex", "cxo-work", {})

            seeded_settings = json.loads((claude_dir / "settings.json").read_text())
            self.assertEqual(seeded_settings["permissions"], {"allow": ["Read"]})
            self.assertEqual(seeded_settings["env"], {"KEEP_ME": "yes"})
            seeded_codex = (codex_dir / "config.toml").read_text()
            self.assertIn('model = "gpt-5"', seeded_codex)
            self.assertNotIn("model_provider", seeded_codex)
            self.assertNotIn("model_providers.relay", seeded_codex)
            self.assertIn("[mcp_servers.docs]", seeded_codex)

    def test_share_sessions_links_codex_accounts_to_one_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_config = Path(tmp) / "codex-config.toml"
            codex_config.write_text('model = "gpt-5.2-codex"\n')
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                   "CODEX_CONFIG": str(codex_config)}
            with unittest.mock.patch.dict(os.environ, env):
                config = {"share_sessions": True}
                d1 = aweswitch.ensure_account_dir("codex", "cxo-a", {})
                d2 = aweswitch.ensure_account_dir("codex", "cxo-b", {})

                notes = aweswitch.sync_account_session_dirs("codex", d1, config)
                self.assertIn("sharing sessions", "\n".join(notes))
                aweswitch.sync_account_session_dirs("codex", d2, config)

                pool = Path(tmp) / "accounts" / "codex" / ".shared" / "sessions"
                self.assertTrue(pool.is_dir())
                self.assertEqual(os.path.realpath(d1 / "sessions"), os.path.realpath(pool))
                self.assertEqual(os.path.realpath(d2 / "sessions"), os.path.realpath(pool))

                # A rollout written through one account is visible to the other.
                session = d1 / "sessions" / "2026" / "09" / "11" / "rollout-2026-09-11T07-00-00-1a2b3c4d.jsonl"
                session.parent.mkdir(parents=True)
                session.write_text("rollout")
                self.assertEqual(
                    (d2 / "sessions" / "2026" / "09" / "11" / session.name).read_text(), "rollout")

                # Already linked: relinking is quiet.
                self.assertEqual(aweswitch.sync_account_session_dirs("codex", d1, config), [])

    def test_share_sessions_migrates_existing_rollout_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json")}
            with unittest.mock.patch.dict(os.environ, env):
                d = aweswitch.ensure_account_dir("codex", "cxo-work", {})
                existing = d / "sessions" / "2026" / "09" / "11" / "rollout-2026-09-11T07-00-00-1a2b3c4d.jsonl"
                existing.parent.mkdir(parents=True)
                existing.write_text("rollout")

                notes = aweswitch.sync_account_session_dirs(
                    "codex", d, {"share_sessions": True})

                pool = Path(tmp) / "accounts" / "codex" / ".shared"
                self.assertEqual(
                    (pool / "sessions" / "2026" / "09" / "11" / existing.name).read_text(), "rollout")
                self.assertEqual(os.path.realpath(d / "sessions"),
                                 os.path.realpath(pool / "sessions"))
                # archived_sessions had no files but is linked too.
                self.assertEqual(os.path.realpath(d / "archived_sessions"),
                                 os.path.realpath(pool / "archived_sessions"))
                self.assertIn("moved 1 session file(s)", "\n".join(notes))

    def test_share_sessions_migration_handles_colliding_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json")}
            with unittest.mock.patch.dict(os.environ, env):
                d = aweswitch.ensure_account_dir("codex", "cxo-work", {})
                pool = Path(tmp) / "accounts" / "codex" / ".shared" / "sessions" / "2026" / "09" / "11"
                pool.mkdir(parents=True)
                name = "rollout-2026-09-11T07-00-00-1a2b3c4d.jsonl"
                (pool / name).write_text("longer existing rollout")
                incoming = d / "sessions" / "2026" / "09" / "11" / name
                incoming.parent.mkdir(parents=True)
                incoming.write_text("same")

                aweswitch.sync_account_session_dirs("codex", d, {"share_sessions": True})

                # Same-size file: treated as a duplicate and dropped.
                self.assertEqual((pool / name).read_text(), "longer existing rollout")
                # Different-size file: preserved under a merged name.
                (d / "sessions" / "2026" / "09" / "11" / name).write_text("different content!")
                aweswitch.sync_account_session_dirs("codex", d, {"share_sessions": True})

    def test_share_sessions_off_unlinks_pool_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json")}
            with unittest.mock.patch.dict(os.environ, env):
                d = aweswitch.ensure_account_dir("codex", "cxo-work", {})
                pool = Path(tmp) / "accounts" / "codex" / ".shared" / "sessions"
                aweswitch.sync_account_session_dirs("codex", d, {"share_sessions": True})
                (pool / "rollout.jsonl").write_text("rollout")

                notes = aweswitch.sync_account_session_dirs("codex", d, {"share_sessions": False})

                self.assertFalse((d / "sessions").exists())
                self.assertFalse((d / "archived_sessions").exists())
                self.assertEqual((pool / "rollout.jsonl").read_text(), "rollout")
                self.assertIn("unlinked sessions", "\n".join(notes))

    def test_share_sessions_rejects_non_bool(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json")}
            with unittest.mock.patch.dict(os.environ, env):
                d = aweswitch.ensure_account_dir("codex", "cxo-work", {})
                with self.assertRaisesRegex(SystemExit, "must be true or false"):
                    aweswitch.sync_account_session_dirs("codex", d, {"share_sessions": "yes"})

    def test_share_sessions_leaves_claude_accounts_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_settings = Path(tmp) / "settings.json"
            claude_settings.write_text("{}\n")
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                   "CLAUDE_SETTINGS": str(claude_settings)}
            with unittest.mock.patch.dict(os.environ, env):
                d = aweswitch.ensure_account_dir("claude", "cco-work", {})
                session = d / "sessions" / "keep.jsonl"
                session.parent.mkdir(parents=True)
                session.write_text("rollout")

                notes = aweswitch.sync_account_session_dirs("claude", d, {"share_sessions": True})

                self.assertEqual(notes, [])
                self.assertTrue((d / "sessions").is_dir())
                self.assertFalse((d / "sessions").is_symlink())
                self.assertEqual(session.read_text(), "rollout")

    def test_share_sessions_pools_default_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                   "CODEX_HOME": str(Path(tmp) / "codex-home")}
            with unittest.mock.patch.dict(os.environ, env):
                existing = (Path(tmp) / "codex-home" / "sessions" / "2026" / "09" / "12"
                            / "rollout-2026-09-12T08-42-31-01a09310.jsonl")
                existing.parent.mkdir(parents=True)
                existing.write_text("rollout")

                notes = aweswitch.sync_default_codex_sessions({"share_sessions": True})

                pool = Path(tmp) / "accounts" / "codex" / ".shared"
                self.assertEqual(
                    (pool / "sessions" / "2026" / "09" / "12" / existing.name).read_text(),
                    "rollout")
                self.assertEqual(
                    os.path.realpath(Path(tmp) / "codex-home" / "sessions"),
                    os.path.realpath(pool / "sessions"))
                self.assertEqual(
                    os.path.realpath(Path(tmp) / "codex-home" / "archived_sessions"),
                    os.path.realpath(pool / "archived_sessions"))
                self.assertIn("moved 1 session file(s)", "\n".join(notes))
                # Already linked: relinking is quiet.
                self.assertEqual(aweswitch.sync_default_codex_sessions({"share_sessions": True}), [])

    def test_share_sessions_off_unlinks_default_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
                   "CODEX_HOME": str(Path(tmp) / "codex-home")}
            with unittest.mock.patch.dict(os.environ, env):
                pool = Path(tmp) / "accounts" / "codex" / ".shared" / "sessions"
                aweswitch.sync_default_codex_sessions({"share_sessions": True})
                (pool / "rollout.jsonl").write_text("rollout")

                notes = aweswitch.sync_default_codex_sessions({"share_sessions": False})

                self.assertFalse((Path(tmp) / "codex-home" / "sessions").exists())
                self.assertFalse((Path(tmp) / "codex-home" / "archived_sessions").exists())
                self.assertEqual((pool / "rollout.jsonl").read_text(), "rollout")
                self.assertIn("unlinked sessions", "\n".join(notes))

    def test_codex_api_launch_links_default_home_to_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_config = Path(tmp) / "codex-config.toml"
            codex_config.write_text('model = "gpt-5.2-codex"\n')
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "share_sessions": True,
                "profiles": {
                    "api": {
                        "codex": {"cx-test": {"env": {
                            "OPENAI_BASE_URL": "https://example.com/v1",
                            "OPENAI_API_KEY": "${CX_KEY}",
                        }}},
                    },
                    "accounts": {},
                },
            }))
            env = {"AWESWITCH_CONFIG": str(config_file),
                   "CODEX_CONFIG": str(codex_config),
                   "CODEX_HOME": str(Path(tmp) / "codex-home"),
                   "CX_KEY": "k"}
            with unittest.mock.patch.dict(os.environ, env):
                with unittest.mock.patch.object(aweswitch, "exec_agent") as exec_agent:
                    result = CliRunner().invoke(aweswitch.cli, ["cx-test"])

                self.assertEqual(result.exit_code, 0, result.output)
                exec_agent.assert_called_once()
                home_sessions = Path(tmp) / "codex-home" / "sessions"
                pool_sessions = Path(tmp) / "accounts" / "codex" / ".shared" / "sessions"
                self.assertEqual(os.path.realpath(home_sessions), os.path.realpath(pool_sessions))
                self.assertIn("sharing sessions", result.output)

    def test_account_add_imports_live_codex_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            aweswitch.init_config(config_file)
            live_dir = Path(tmp) / "codex"
            live_dir.mkdir()
            blob = {"tokens": {"access_token": "tok", "refresh_token": "ref"}}
            (live_dir / "auth.json").write_text(json.dumps(blob))

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "add", "codex", "cxo-work"],
                env={"AWESWITCH_CONFIG": str(config_file),
                     "CODEX_CONFIG": str(live_dir / "config.toml")})

            self.assertEqual(result.exit_code, 0, result.output)
            data = json.loads(config_file.read_text())
            self.assertEqual(data["profiles"]["accounts"]["codex"]["cxo-work"]["auth"], blob)
            self.assert_settings_file_secure(config_file)

    def test_account_add_rejects_name_used_by_api_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {"claude": {"work": {"env": {
                    "ANTHROPIC_BASE_URL": "https://x"}}}}},
            }) + "\n")
            live_dir = Path(tmp) / "codex"
            live_dir.mkdir()
            (live_dir / "auth.json").write_text(json.dumps({"tokens": {}}))

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "add", "codex", "work"],
                env={"AWESWITCH_CONFIG": str(config_file),
                     "CODEX_CONFIG": str(live_dir / "config.toml")})

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("already used", result.output)

    @unittest.mock.patch("aweswitch.cli.subprocess.run")
    def test_account_login_captures_credentials(self, mock_run):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            aweswitch.init_config(config_file)

            def fake_login(argv, env=None):
                cred_path = Path(env["CODEX_HOME"]) / "auth.json"
                cred_path.write_text(json.dumps({"tokens": {"access_token": "fresh"}}))
                return unittest.mock.MagicMock(returncode=0)

            mock_run.side_effect = fake_login

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "login", "codex", "cxo-work"],
                env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertEqual(result.exit_code, 0, result.output)
            data = json.loads(config_file.read_text())
            self.assertEqual(data["profiles"]["accounts"]["codex"]["cxo-work"]["auth"],
                             {"tokens": {"access_token": "fresh"}})
            login_env = mock_run.call_args.kwargs["env"]
            self.assertEqual(login_env["CODEX_HOME"],
                             str(Path(tmp) / "accounts" / "codex" / "cxo-work"))

    @unittest.mock.patch("aweswitch.cli.subprocess.run")
    def test_account_login_rejects_old_credentials_when_relogin_fails(self, mock_run):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            old_blob = {"tokens": {"access_token": "old"}}
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-work": {"auth": old_blob},
                }}},
            }) + "\n")
            mock_run.return_value = unittest.mock.MagicMock(returncode=1)

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "login", "codex", "cxo-work"],
                env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("no credentials captured", result.output)
            saved = json.loads(config_file.read_text())
            self.assertEqual(saved["profiles"]["accounts"]["codex"]["cxo-work"]["auth"], old_blob)

    @unittest.mock.patch("aweswitch.cli.subprocess.run")
    def test_account_login_restores_old_credentials_after_spawn_error(self, mock_run):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            old_blob = {"tokens": {"access_token": "old"}}
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-work": {"auth": old_blob},
                }}},
            }) + "\n")
            mock_run.side_effect = PermissionError("blocked")

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "login", "codex", "cxo-work"],
                env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("failed to run codex", result.output)
            runtime_cred = Path(tmp) / "accounts" / "codex" / "cxo-work" / "auth.json"
            self.assertEqual(json.loads(runtime_cred.read_text()), old_blob)

    def test_build_claude_env_names_rejected_profile_kind(self):
        config = {"profiles": {"accounts": {"claude": {
            "cco-work": {"credentials": {}},
        }}}}

        with self.assertRaisesRegex(SystemExit, "provider=claude, kind=account"):
            aweswitch.build_claude_env(config, "cco-work", {})

    def test_account_sync_updates_blob_from_runtime_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-work": {"auth": {"tokens": {"access_token": "stale"}}},
                }}},
            }) + "\n")
            cred = Path(tmp) / "accounts" / "codex" / "cxo-work" / "auth.json"
            cred.parent.mkdir(parents=True)
            cred.write_text(json.dumps({"tokens": {"access_token": "fresh"}}))

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "sync", "codex", "cxo-work"],
                env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertEqual(result.exit_code, 0, result.output)
            data = json.loads(config_file.read_text())
            self.assertEqual(
                data["profiles"]["accounts"]["codex"]["cxo-work"]["auth"]["tokens"]["access_token"],
                "fresh")

    def test_account_remove_and_purge(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-work": {"auth": {"tokens": {}}},
                }}},
            }) + "\n")
            cred = Path(tmp) / "accounts" / "codex" / "cxo-work" / "auth.json"
            cred.parent.mkdir(parents=True)
            cred.write_text(json.dumps({"tokens": {}}))

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "remove", "codex", "cxo-work", "--purge"],
                env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertEqual(result.exit_code, 0, result.output)
            data = json.loads(config_file.read_text())
            self.assertNotIn("accounts", data["profiles"])
            self.assertFalse(cred.exists())

    def test_account_remove_rejects_escaping_name_before_mutating_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            unsafe_name = "../../outside"
            original = {
                "profiles": {"api": {}, "accounts": {"codex": {
                    unsafe_name: {"auth": {"tokens": {}}},
                }}},
            }
            config_file.write_text(json.dumps(original) + "\n")
            outside = Path(tmp) / "outside"
            outside.mkdir()
            sentinel = outside / "keep.txt"
            sentinel.write_text("keep")

            result = CliRunner().invoke(
                aweswitch.cli, ["account", "remove", "codex", unsafe_name, "--purge"],
                env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("single path component", result.output)
            self.assertEqual(json.loads(config_file.read_text()), original)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_list_marks_account_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {
                    "api": {"claude": {"cc-glm": {"env": {
                        "ANTHROPIC_BASE_URL": "https://x", "ANTHROPIC_MODEL": "glm-5.1"}}}},
                    "accounts": {"claude": {"cco-team": {"credentials": {"x": 1}}}},
                },
            }) + "\n")

            result = CliRunner().invoke(aweswitch.cli, ["list"],
                                        env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("cc-glm\tclaude\tapi\tglm-5.1", result.output)
            self.assertIn("cco-team\tclaude\taccount\tofficial login", result.output)

    def test_show_redacts_account_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"claude": {
                    "cco-team": {"credentials": {"claudeAiOauth": {"accessToken": "secret-token"}}},
                }}},
            }) + "\n")

            result = CliRunner().invoke(aweswitch.cli, ["show", "cco-team"],
                                        env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("<redacted>", result.output)
            self.assertNotIn("secret-token", result.output)

    def test_apply_rejects_account_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"claude": {
                    "cco-team": {"credentials": {"x": 1}},
                }}},
            }) + "\n")

            result = CliRunner().invoke(aweswitch.cli, ["apply", "cco-team"],
                                        env={"AWESWITCH_CONFIG": str(config_file)})

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("accounts are launch-only", result.output)

    # --- apply: codex (config.toml) ---

    def test_write_codex_config_creates_fresh_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"

            aweswitch.write_codex_config(path, "https://zhipu.com/v1", "GLM_KEY", "glm-5.3")

            text = path.read_text()
            self.assertIn('model = "glm-5.3"', text)
            self.assertIn('model_provider = "custom"', text)
            self.assertIn("disable_response_storage = true", text)
            self.assertIn("[model_providers.custom]", text)
            self.assertIn('base_url = "https://zhipu.com/v1"', text)
            self.assertIn('env_key = "GLM_KEY"', text)

    def test_write_codex_config_updates_existing_and_preserves_unrelated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                'model_context_window = 1000000\n'
                'model = "gpt-5.6-luna"\n'
                'model_reasoning_effort = "medium"\n'
                'model_provider = "other"\n'
                '\n'
                '[mcp_servers.fetch]\n'
                'command = "uvx"\n'
                '\n'
                '[model_providers.custom]\n'
                'base_url = "https://old.com/v1"\n'
                '\n'
                '[model_providers.custom.sub]\n'
                'x = 1\n'
                '\n'
                '[projects."/tmp"]\n'
                'trust_level = "trusted"\n'
            )

            aweswitch.write_codex_config(path, "https://zhipu.com/v1", "GLM_KEY", "glm-5.3")

            text = path.read_text()
            self.assertIn('model = "glm-5.3"', text)
            self.assertNotIn('model = "gpt-5.6-luna"', text)
            self.assertIn('model_provider = "custom"', text)
            self.assertNotIn('model_provider = "other"', text)
            # unrelated top-level keys and tables survive untouched
            self.assertIn('model_context_window = 1000000', text)
            self.assertIn('model_reasoning_effort = "medium"', text)
            self.assertIn('[mcp_servers.fetch]', text)
            self.assertIn('[projects."/tmp"]', text)
            # old custom table (and its subtable) replaced with the fresh one
            self.assertNotIn("old.com", text)
            self.assertNotIn("[model_providers.custom.sub]", text)
            self.assertIn('base_url = "https://zhipu.com/v1"', text)
            # exactly one custom table
            self.assertEqual(text.count("[model_providers.custom]"), 1)

    def test_write_codex_config_without_model_leaves_existing_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('model = "gpt-5.6-luna"\n\n[mcp_servers]\n')

            aweswitch.write_codex_config(path, "https://zhipu.com/v1", "GLM_KEY", None)

            text = path.read_text()
            self.assertIn('model = "gpt-5.6-luna"', text)  # profile has no model -> untouched
            self.assertIn('model_provider = "custom"', text)  # inserted before first table

    def test_write_codex_config_inserts_keys_before_first_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('[mcp_servers]\ncommand = "uvx"\n')

            aweswitch.write_codex_config(path, "https://x/v1", "K", "m1")

            lines = path.read_text().splitlines()
            # top-level assignments must precede the first table header
            self.assertLess(lines.index('model_provider = "custom"'),
                            lines.index("[mcp_servers]"))

    def test_write_codex_config_ignores_brackets_inside_multiline_strings(self):
        """Lines inside multi-line strings must not count as table headers, or
        top-level keys get inserted at the wrong place (silently joining a
        table) and custom-block detection goes wrong."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                'model = "gpt-5.6-luna"\n'
                'developer_instructions = """\n'
                "Use rtk skills.\n"
                "[model_providers.custom]\n"     # looks like a header, is string body
                'name = "fake"\n'
                '"""\n'
                '\n'
                '[mcp_servers.fetch]\n'
                'command = "uvx"\n'
            )

            aweswitch.write_codex_config(path, "https://zhipu.com/v1", "GLM_KEY", "glm-5.3")

            text = path.read_text()
            self.assertIn('model = "glm-5.3"', text)
            self.assertIn('name = "fake"', text)      # string body untouched
            self.assertIn("[mcp_servers.fetch]", text)
            # the appended real table (fake one inside the string stays fake)
            self.assertIn('[model_providers.custom]\nname = "custom"\n', text)
            lines = text.splitlines()
            # model key must still be before the FIRST real table
            first_table = min(i for i, l in enumerate(lines) if l.startswith("["))
            self.assertLess(lines.index('model = "glm-5.3"'), first_table)
            try:
                import tomllib  # py3.11+: parse check
            except ModuleNotFoundError:
                tomllib = None
            if tomllib is not None:
                data = tomllib.loads(text)
                self.assertEqual(data["developer_instructions"].count("[model_providers.custom]"), 1)
                self.assertEqual(data["model"], "glm-5.3")
                self.assertEqual(data["model_providers"]["custom"]["base_url"], "https://zhipu.com/v1")

    def _make_apply_config(self):
        return {
            "profiles": {
                "api": {
                    "claude": {
                        "cc-test": {"env": {
                            "ANTHROPIC_BASE_URL": "https://example.test",
                            "ANTHROPIC_AUTH_TOKEN": "${TOKEN}",
                            "ANTHROPIC_MODEL": "model",
                        }},
                    },
                    "codex": {
                        "cx-glm": {"env": {
                            "OPENAI_BASE_URL": "https://zhipu.com/v1",
                            "OPENAI_API_KEY": "${GLM_KEY}",
                            "OPENAI_MODEL": {"glm-5.3": "GLM-5.3", "glm-5.1": "GLM-5.1"},
                        }},
                        "cx-plain": {"env": {
                            "OPENAI_BASE_URL": "https://x/v1",
                            "OPENAI_API_KEY": "sk-plain",
                            "OPENAI_MODEL": ["m-1"],
                        }},
                    },
                    "opencode": {
                        "oc-test": {"env": {
                            "OPENCODE_BASE_URL": "https://example.com/v1",
                            "OPENCODE_API_KEY": "${OC_KEY}",
                            "OPENCODE_MODEL": {"m1": "M1", "m2": "M2"},
                        }},
                    },
                }
            }
        }

    def _apply(self, args, config, tmp, extra_env=None, input=None):
        oc_path = Path(tmp) / "opencode.json"
        if not oc_path.exists():
            oc_path.write_text(json.dumps({"provider": {}}))
        env = {
            "AWESWITCH_CONFIG": str(Path(tmp) / "config.json"),
            "OPENCODE_CONFIG": str(oc_path),
            "TOKEN": "secret",
            "GLM_KEY": "sk-glm",
            **(extra_env or {}),
        }
        (Path(tmp) / "config.json").write_text(json.dumps(config) + "\n")
        result = CliRunner().invoke(aweswitch.cli, args, env=env, input=input)
        return result, oc_path

    def test_apply_codex_profile_writes_config_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_path = Path(tmp) / "config.toml"
            codex_path.write_text('model = "gpt-5.6-luna"\n\n[mcp_servers]\n')

            result, _ = self._apply(
                ["apply", "cx-glm"], self._make_apply_config(), tmp,
                extra_env={"CODEX_CONFIG": str(codex_path)},
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Applied cx-glm", result.output)
            self.assertIn("env_key = GLM_KEY", result.output)
            self.assertIn("Backup:", result.output)
            text = codex_path.read_text()
            self.assertIn('model = "glm-5.3"', text)  # first model from the dict
            self.assertIn('base_url = "https://zhipu.com/v1"', text)
            self.assertIn('env_key = "GLM_KEY"', text)
            self.assertIn("[mcp_servers]", text)
            self.assertIn('model = "gpt-5.6-luna"', codex_path.with_suffix(".toml.bak").read_text())

    def test_apply_codex_pins_and_releases_subagent_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_path = Path(tmp) / "config.toml"
            config = self._make_apply_config()
            config["profiles"]["api"]["codex"]["cx-glm"]["env"]["CODEX_SUBAGENT_MODEL"] = "glm-5.3-flash"

            result, _ = self._apply(
                ["apply", "cx-glm"], config, tmp,
                extra_env={"CODEX_CONFIG": str(codex_path)},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("agents.default_subagent_model = glm-5.3-flash", result.output)
            text = codex_path.read_text()
            self.assertIn("[agents]", text)
            self.assertIn('default_subagent_model = "glm-5.3-flash"', text)

            # Applying a profile without the field releases the pin; the table
            # it created disappears instead of lingering empty.
            result, _ = self._apply(
                ["apply", "cx-plain"], self._make_apply_config(), tmp,
                extra_env={"CODEX_CONFIG": str(codex_path)},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            text = codex_path.read_text()
            self.assertNotIn("default_subagent_model", text)
            self.assertNotIn("[agents]", text)
            self.assertIn("[model_providers.custom]", text)

    def test_apply_codex_preserves_hand_maintained_agents_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_path = Path(tmp) / "config.toml"
            codex_path.write_text(
                '[agents]\n'
                'max_threads = 4\n'
                '\n'
                '[agents.researcher]\n'
                'description = "deep search"\n'
            )
            config = self._make_apply_config()
            config["profiles"]["api"]["codex"]["cx-glm"]["env"]["CODEX_SUBAGENT_MODEL"] = "glm-5.3-flash"

            result, _ = self._apply(
                ["apply", "cx-glm"], config, tmp,
                extra_env={"CODEX_CONFIG": str(codex_path)},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            text = codex_path.read_text()
            self.assertIn('default_subagent_model = "glm-5.3-flash"', text)
            self.assertIn("max_threads = 4", text)
            self.assertIn('[agents.researcher]', text)
            self.assertIn('description = "deep search"', text)

            # Releasing removes only the managed key.
            result, _ = self._apply(
                ["apply", "cx-plain"], self._make_apply_config(), tmp,
                extra_env={"CODEX_CONFIG": str(codex_path)},
            )
            self.assertEqual(result.exit_code, 0, result.output)
            text = codex_path.read_text()
            self.assertNotIn("default_subagent_model", text)
            self.assertIn("max_threads = 4", text)
            self.assertIn('[agents.researcher]', text)

    def test_apply_codex_subagent_reference_dies_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_path = Path(tmp) / "config.toml"
            codex_path.write_text('model = "keep"\n')
            config = self._make_apply_config()
            config["profiles"]["api"]["codex"]["cx-glm"]["env"]["CODEX_SUBAGENT_MODEL"] = "@oc-test/m1"

            result, _ = self._apply(
                ["apply", "cx-glm"], config, tmp,
                extra_env={"CODEX_CONFIG": str(codex_path)},
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("does not support @profile/model", result.output)
            self.assertEqual(codex_path.read_text(), 'model = "keep"\n')

    def test_apply_codex_plain_key_warns_and_uses_openai_env_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_path = Path(tmp) / "config.toml"

            result, _ = self._apply(
                ["apply", "cx-plain"], self._make_apply_config(), tmp,
                extra_env={"CODEX_CONFIG": str(codex_path)},
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("OPENAI_API_KEY is a plain value", result.output)
            self.assertIn('env_key = "OPENAI_API_KEY"', codex_path.read_text())

    def test_apply_opencode_profile_upserts_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            # provider missing -> created
            result, oc_path = self._apply(["apply", "oc-test"], self._make_apply_config(), tmp)
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("oc-test: created (2 models)", result.output)
            prov = json.loads(oc_path.read_text())["provider"]["oc-test"]
            self.assertEqual(sorted(prov["models"]), ["m1", "m2"])

            # provider exists with a stale model -> overwritten to match config
            prov["models"]["stale"] = {"name": "stale"}
            oc_path.write_text(json.dumps({"provider": {"oc-test": prov}}))
            result, oc_path = self._apply(["apply", "oc-test"], self._make_apply_config(), tmp)
            self.assertIn("oc-test: updated (2 models)", result.output)
            self.assertEqual(
                sorted(json.loads(oc_path.read_text())["provider"]["oc-test"]["models"]),
                ["m1", "m2"],
            )

    def test_apply_opencode_flag_applies_all_opencode_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, oc_path = self._apply(["apply", "--opencode"], self._make_apply_config(), tmp)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("oc-test: created (2 models)", result.output)
            self.assertIn("Synced to", result.output)

    def test_apply_without_arguments_applies_opencode_and_skips_empty_zcode(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "zcode.json"
            result, oc_path = self._apply(
                ["apply"], self._make_apply_config(), tmp,
                extra_env={"ZCODE_CONFIG": str(zc_path)})

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("oc-test: created (2 models)", result.output)
            self.assertIn("Synced to", result.output)
            self.assertIn("no zcode profiles found, skipping", result.output)
            self.assertIn("oc-test", json.loads(oc_path.read_text())["provider"])
            # the skipped side was never written
            self.assertFalse(zc_path.exists())

    def test_apply_without_arguments_and_no_bulk_profiles_errors_with_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_apply_config()
            del config["profiles"]["api"]["opencode"]
            result, oc_path = self._apply(
                ["apply"], config, tmp,
                extra_env={"ZCODE_CONFIG": str(Path(tmp) / "zcode.json")})

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("nothing to apply", result.output)
            self.assertIn("--opencode", result.output)
            # nothing was written
            self.assertEqual(json.loads(oc_path.read_text()), {"provider": {}})

    def test_apply_opencode_flag_rejects_profile_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self._apply(["apply", "--opencode", "oc-test"], self._make_apply_config(), tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("pick one", result.output)

    def _write_oc_with_orphans(self, oc_path):
        orphan = aweswitch.build_opencode_provider_entry("https://old.com/v1", "{env:OLD_KEY}")
        orphan["models"] = {"peng1/x": {"name": "x"}, "peng1/y": {"name": "y"}}
        hand_written = {
            "name": "mine",
            "npm": "@ai-sdk/openai-compatible",
            "options": {"apiKey": "sk", "baseURL": "https://mine/v1", "setCacheKey": True},
        }
        oc_path.write_text(json.dumps({"provider": {"oc-old": orphan, "mine": hand_written}}))
        managed_path = oc_path.with_name(".aweswitch-managed-providers.json")
        managed_path.write_text(json.dumps({"providers": ["oc-old"]}) + "\n")

    def test_apply_warns_about_orphaned_aweswitch_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_with_orphans(oc_path)

            result, oc_path = self._apply(["apply", "--opencode"], self._make_apply_config(), tmp)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("orphaned", result.output)
            self.assertIn("oc-old", result.output)
            self.assertIn("--prune orphans", result.output)
            providers = json.loads(oc_path.read_text())["provider"]
            self.assertIn("oc-old", providers)  # warn-only: kept
            self.assertIn("mine", providers)  # identical shape but untracked: never reported

    def test_apply_prune_orphans_removes_only_aweswitch_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_with_orphans(oc_path)

            result, oc_path = self._apply(["apply", "--opencode", "--prune", "orphans"],
                                           self._make_apply_config(), tmp, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'oc-old'", result.output)
            providers = json.loads(oc_path.read_text())["provider"]
            self.assertNotIn("oc-old", providers)
            self.assertIn("oc-test", providers)
            self.assertIn("mine", providers)
            managed = json.loads(
                oc_path.with_name(".aweswitch-managed-providers.json").read_text()
            )["providers"]
            self.assertNotIn("oc-old", managed)
            self.assertIn("oc-test", managed)

    def test_apply_prune_refuses_invalid_managed_provider_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            original = {"provider": {"manual": {
                "name": "manual",
                "npm": "@ai-sdk/openai-compatible",
                "options": {"setCacheKey": True},
            }}}
            oc_path.write_text(json.dumps(original))
            oc_path.with_name(".aweswitch-managed-providers.json").write_text("{broken")

            result, _ = self._apply(
                ["apply", "--opencode", "--prune", "orphans"],
                self._make_apply_config(), tmp,
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("invalid managed-provider JSON", result.output)
            self.assertEqual(json.loads(oc_path.read_text()), original)

    def _write_oc_aweshare_leftovers(self, oc_path):
        """opencode.json as it looks after hand-written aweshare wiring: stale
        aweshare* entries, one unrelated hand-written provider, and the default
        model pointing into the stale one."""
        def entry(models):
            prov = aweswitch.build_opencode_provider_entry("https://hub.test/v1", "sk-old")
            prov["models"] = {mid: {"name": mid} for mid in models}
            return prov

        data = {
            "model": "aweshare-peng/peng1/gpt-5.6-luna",
            "provider": {
                "aweshare": entry(["glm-5.1"]),
                "aweshare2": entry(["glm-5.2"]),
                "aweshare-peng": entry(["peng1/gpt-5.6-luna", "peng1/gpt-5.6-terra"]),
                "aweshare-deepseek": entry(["deepseek-v4"]),
                "aweshare-code": entry(["coder-x"]),
                "mine": entry(["own-m"]),
            },
        }
        oc_path.write_text(json.dumps(data, indent=2) + "\n")
        return data

    def test_apply_prune_named_removes_handwritten_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)

            result, oc_path = self._apply(
                ["apply", "--opencode", "--prune",
                 "aweshare,aweshare2,aweshare-peng,aweshare-deepseek,aweshare-code"],
                self._make_apply_config(), tmp, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            for name in ("aweshare", "aweshare2", "aweshare-peng",
                         "aweshare-deepseek", "aweshare-code"):
                self.assertIn(f"Pruned provider '{name}'", result.output)
            data = json.loads(oc_path.read_text())
            self.assertEqual(sorted(data["provider"]), ["mine", "oc-test"])
            # the default model pointed at a deleted provider -> repaired
            self.assertEqual(data["model"], "oc-test/m1")
            managed = json.loads(
                oc_path.with_name(".aweswitch-managed-providers.json").read_text()
            )["providers"]
            self.assertEqual(managed, ["oc-test"])

    def test_apply_prune_unknown_name_dies_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)
            before = oc_path.read_text()

            result, _ = self._apply(
                ["apply", "--opencode", "--prune", "aweshare,nope"],
                self._make_apply_config(), tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("no provider 'nope'", result.output)
            self.assertIn(
                "Available providers: aweshare, aweshare-code, "
                "aweshare-deepseek, aweshare-peng, aweshare2, mine",
                result.output,
            )
            self.assertEqual(oc_path.read_text(), before)  # guards fire before the sync writes

    def test_apply_named_prune_unknown_name_dies_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)
            before = oc_path.read_text()

            result, _ = self._apply(
                ["apply", "oc-test", "--prune", "nope"],
                self._make_apply_config(), tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("no provider 'nope'", result.output)
            self.assertEqual(oc_path.read_text(), before)

    def test_apply_prune_backed_profile_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)
            data = json.loads(oc_path.read_text())
            data["provider"]["oc-test"] = aweswitch.build_opencode_provider_entry(
                "https://example.com/v1", "{env:OC_KEY}")
            oc_path.write_text(json.dumps(data))
            before = oc_path.read_text()

            result, _ = self._apply(
                ["apply", "--opencode", "--prune", "oc-test"],
                self._make_apply_config(), tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("remove that profile from the config", result.output)
            self.assertEqual(oc_path.read_text(), before)

    def test_apply_prune_all_removes_all_unbacked_and_repairs_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)

            result, oc_path = self._apply(
                ["apply", "--opencode", "--prune", "all"],
                self._make_apply_config(), tmp, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            for name in ("aweshare", "aweshare2", "aweshare-peng",
                         "aweshare-deepseek", "aweshare-code", "mine"):
                self.assertIn(f"Pruned provider '{name}'", result.output)
            data = json.loads(oc_path.read_text())
            self.assertEqual(list(data["provider"]), ["oc-test"])
            self.assertEqual(data["model"], "oc-test/m1")
            managed = json.loads(
                oc_path.with_name(".aweswitch-managed-providers.json").read_text()
            )["providers"]
            self.assertEqual(managed, ["oc-test"])

    def test_apply_prune_all_without_profiles_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)
            before = oc_path.read_text()
            config = self._make_apply_config()
            del config["profiles"]["api"]["opencode"]

            result, _ = self._apply(
                ["apply", "--opencode", "--prune", "all"], config, tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("would delete every provider", result.output)
            self.assertEqual(oc_path.read_text(), before)

    def test_apply_prune_all_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)
            before = oc_path.read_text()

            result, oc_path = self._apply(
                ["apply", "--opencode", "--prune", "all", "--dry-run"],
                self._make_apply_config(), tmp)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Dry run: nothing will be written.", result.output)
            self.assertIn("oc-test: would sync (2 models)", result.output)
            self.assertIn(
                "Would prune provider 'aweshare-peng' (peng1/gpt-5.6-luna, peng1/gpt-5.6-terra)",
                result.output,
            )
            self.assertIn("Would prune provider 'mine' (own-m)", result.output)
            self.assertIn(
                "Default model: aweshare-peng/peng1/gpt-5.6-luna -> oc-test/m1",
                result.output,
            )
            self.assertEqual(oc_path.read_text(), before)
            self.assertFalse(oc_path.with_name(".aweswitch-managed-providers.json").exists())

    def test_apply_dry_run_requires_prune_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self._apply(
                ["apply", "--opencode", "--dry-run"],
                self._make_apply_config(), tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--dry-run previews pruning", result.output)

    def test_apply_prune_orphans_repairs_dangling_default_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_with_orphans(oc_path)
            data = json.loads(oc_path.read_text())
            data["model"] = "oc-old/peng1/x"
            oc_path.write_text(json.dumps(data))

            result, oc_path = self._apply(
                ["apply", "--opencode", "--prune", "orphans"],
                self._make_apply_config(), tmp, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'oc-old'", result.output)
            self.assertEqual(json.loads(oc_path.read_text())["model"], "oc-test/m1")

    def test_apply_prune_keeps_default_model_pointing_at_live_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)
            data = json.loads(oc_path.read_text())
            data["model"] = "mine/own-m"
            oc_path.write_text(json.dumps(data))

            result, oc_path = self._apply(
                ["apply", "--opencode", "--prune", "aweshare,aweshare2"],
                self._make_apply_config(), tmp, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn("Default model:", result.output)
            self.assertEqual(json.loads(oc_path.read_text())["model"], "mine/own-m")

    def test_apply_prune_single_profile_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            self._write_oc_aweshare_leftovers(oc_path)

            result, oc_path = self._apply(
                ["apply", "oc-test", "--prune", "aweshare"],
                self._make_apply_config(), tmp, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'aweshare'", result.output)
            providers = json.loads(oc_path.read_text())["provider"]
            self.assertNotIn("aweshare", providers)
            self.assertIn("mine", providers)
            self.assertIn("oc-test", providers)

    def test_apply_zcode_prune_all_removes_unbacked(self):
        with tempfile.TemporaryDirectory() as tmp:
            zc_path = Path(tmp) / "zcode.json"
            zc_path.write_text(json.dumps({"provider": {
                "zc-old": {"name": "zc-old", "kind": "anthropic",
                           "options": {"baseURL": "https://old.com/v1", "apiKey": "sk-old"}},
                "mine": {"name": "mine", "kind": "openai-compatible",
                         "options": {"apiKey": "sk", "baseURL": "https://mine/v1"}},
            }}))
            config = self._make_apply_config()
            config["profiles"]["api"]["zcode"] = {
                "zc-test": {"env": {
                    "ZCODE_BASE_URL": "https://example.test/v1",
                    "ZCODE_API_KEY": "${TOKEN}",
                    "ZCODE_CHAT_MODEL": "m1",
                }},
            }
            result, oc_path = self._apply(
                ["apply", "--zcode", "--prune", "all"],
                config, tmp, extra_env={"ZCODE_CONFIG": str(zc_path)}, input="y\n")

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Pruned provider 'zc-old'", result.output)
            self.assertIn("Pruned provider 'mine'", result.output)
            providers = json.loads(zc_path.read_text())["provider"]
            self.assertEqual(list(providers), ["zc-test"])

    def test_ensure_opencode_provider_displays_namespaced_ids_in_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            oc_path = Path(tmp) / "opencode.json"
            oc_path.write_text(json.dumps({"provider": {}}))

            with unittest.mock.patch.dict(os.environ, {"OPENCODE_CONFIG": str(oc_path)}):
                aweswitch.ensure_opencode_provider(
                    "https://hub.example/v1", "{env:HUB_KEY}", "oc-hub",
                    {"hub/x": "x", "hub/y": "Custom Y", "plain": "Plain"})

            models = json.loads(oc_path.read_text())["provider"]["oc-hub"]["models"]
            self.assertEqual(
                {mid: m["name"] for mid, m in models.items()},
                {"hub/x": "hub/x", "hub/y": "Custom Y", "plain": "Plain"},
            )

    def test_apply_mixed_providers_in_one_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            codex_path = Path(tmp) / "config.toml"
            result, oc_path = self._apply(
                ["apply", "cc-test", "cx-glm", "oc-test"], self._make_apply_config(), tmp,
                extra_env={"CLAUDE_SETTINGS": str(settings_path), "CODEX_CONFIG": str(codex_path)},
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Applied cc-test", result.output)
            self.assertIn("Applied cx-glm", result.output)
            self.assertIn("oc-test: created", result.output)
            self.assertTrue(settings_path.exists())
            self.assertIn("[model_providers.custom]", codex_path.read_text())
            self.assertIn("oc-test", json.loads(oc_path.read_text())["provider"])

    def test_apply_preflights_all_profiles_before_any_write(self):
        config = self._make_apply_config()
        config["profiles"]["accounts"] = {
            "claude": {"acct": {"credentials": {"x": 1}}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            result, _ = self._apply(
                ["apply", "cc-test", "acct"], config, tmp,
                extra_env={"CLAUDE_SETTINGS": str(settings_path)},
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("accounts are launch-only", result.output)
            self.assertFalse(settings_path.exists())

    def test_apply_rejects_two_codex_profiles(self):
        config = self._make_apply_config()
        config["profiles"]["api"]["codex"]["cx-two"] = dict(config["profiles"]["api"]["codex"]["cx-glm"])
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self._apply(["apply", "cx-glm", "cx-two"], config, tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("apply one codex profile at a time", result.output)

    def test_apply_rejects_two_claude_profiles(self):
        config = self._make_apply_config()
        config["profiles"]["api"]["claude"]["cc-two"] = dict(config["profiles"]["api"]["claude"]["cc-test"])
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = self._apply(["apply", "cc-test", "cc-two"], config, tmp)

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("apply one claude profile at a time", result.output)

    def test_config_backup_creates_backup_and_prints_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text('{"env": {"OLD": "1"}}\n')

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path):
                result = CliRunner().invoke(aweswitch.cli, ["config", "backup"])

            backup_path = settings_path.with_suffix(".json.bak")
            self.assertEqual(result.exit_code, 0)
            self.assertIn(str(backup_path), result.output)
            self.assertEqual(json.loads(backup_path.read_text()), {"env": {"OLD": "1"}})

    def test_config_backup_does_not_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text('{"env": {"NEW": "2"}}\n')
            backup_path = settings_path.with_suffix(".json.bak")
            backup_path.write_text('{"env": {"OLD": "1"}}\n')

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path):
                no_force = CliRunner().invoke(aweswitch.cli, ["config", "backup"])

            self.assertEqual(no_force.exit_code, 0)
            self.assertIn("not overwritten", no_force.output)
            self.assertEqual(json.loads(backup_path.read_text()), {"env": {"OLD": "1"}})

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path):
                forced = CliRunner().invoke(aweswitch.cli, ["config", "backup", "--force"])

            self.assertEqual(forced.exit_code, 0)
            self.assertEqual(json.loads(backup_path.read_text()), {"env": {"NEW": "2"}})

    def test_config_backup_fails_without_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path):
                result = CliRunner().invoke(aweswitch.cli, ["config", "backup"])

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("no settings file found", result.output)

    def test_config_restore_default_uses_bak(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text('{"env": {"NEW": "2"}}\n')
            backup_path = settings_path.with_suffix(".json.bak")
            backup_path.write_text('{"env": {"OLD": "1"}}\n')

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path):
                result = CliRunner().invoke(aweswitch.cli, ["config", "restore"])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(json.loads(settings_path.read_text()), {"env": {"OLD": "1"}})

    def test_config_restore_from_explicit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"
            settings_path.write_text('{"env": {"NEW": "2"}}\n')
            snapshot = Path(tmp) / "settings.json.backup.2026-01-01T00-00-00Z"
            snapshot.write_text('{"env": {"ANCIENT": "0"}}\n')

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path):
                result = CliRunner().invoke(aweswitch.cli, ["config", "restore", str(snapshot)])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(json.loads(settings_path.read_text()), {"env": {"ANCIENT": "0"}})

    def test_config_restore_missing_backup_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "settings.json"

            with unittest.mock.patch("aweswitch.cli.claude_settings_path", return_value=settings_path):
                result = CliRunner().invoke(aweswitch.cli, ["config", "restore", str(Path(tmp) / "missing.json")])

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("no such backup file", result.output)

    def test_redact_masks_account_blobs_whole(self):
        data = {"profiles": {"accounts": {"codex": {
            "cxo-work": {"auth": {"account_id": "acc", "tokens": {"access_token": "t"}}},
        }}}}

        redacted = aweswitch.redact(data)

        self.assertEqual(redacted["profiles"]["accounts"]["codex"]["cxo-work"]["auth"], "<redacted>")

    def test_should_skip_empty_args(self):
        self.assertTrue(update_check._should_skip([]))

    def test_usage_help_visible(self):
        result = CliRunner().invoke(aweswitch.cli, ["usage", "--help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage: aweswitch usage", result.output)
        self.assertIn("--all-codex", result.output)
        self.assertIn("--json", result.output)

    def test_usage_no_selector_shows_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            aweswitch.init_config(config_file)

            result = CliRunner().invoke(
                aweswitch.cli, ["usage"],
                env={"AWESWITCH_CONFIG": str(config_file)},
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No account selector given", result.output)
        self.assertIn("--all-codex", result.output)

    def test_usage_all_codex_selects_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-a": {"auth": {"tokens": {"access_token": "a"}}},
                    "cxo-b": {"auth": {"tokens": {"access_token": "b"}}},
                }}},
            }) + "\n")
            mock_usage = unittest.mock.MagicMock()
            mock_usage.UsageError = type("UsageError", (Exception,), {})
            mock_usage.load_codex_credentials.return_value = {"tokens": {"access_token": "tok"}}
            mock_usage.fetch_codex_usage.return_value = {
                "plan": "free",
                "credits": {"used": 1, "limit": 10},
            }

            with unittest.mock.patch.dict(sys.modules, {"aweswitch.usage": mock_usage}):
                result = CliRunner().invoke(
                    aweswitch.cli, ["usage", "--all-codex"],
                    env={"AWESWITCH_CONFIG": str(config_file)},
                )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("cxo-a", result.output)
        self.assertIn("cxo-b", result.output)
        self.assertIn("free", result.output)
        mock_usage.load_codex_credentials.assert_any_call(
            config_file.parent / "accounts" / "codex" / "cxo-a" / "auth.json",
            {"tokens": {"access_token": "a"}},
        )

    def test_usage_all_codex_exits_usefully_when_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            aweswitch.init_config(config_file)

            result = CliRunner().invoke(
                aweswitch.cli, ["usage", "--all-codex"],
                env={"AWESWITCH_CONFIG": str(config_file)},
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No Codex official accounts found", result.output)

    def test_usage_rejects_api_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {"codex": {
                    "cx-api": {"env": {"OPENAI_BASE_URL": "https://x", "OPENAI_API_KEY": "k"}},
                }}, "accounts": {}},
            }) + "\n")

            result = CliRunner().invoke(
                aweswitch.cli, ["usage", "cx-api"],
                env={"AWESWITCH_CONFIG": str(config_file)},
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("API profile", result.output)

    def test_usage_rejects_claude_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"claude": {
                    "cco-work": {"credentials": {"claudeAiOauth": {}}},
                }}},
            }) + "\n")

            result = CliRunner().invoke(
                aweswitch.cli, ["usage", "cco-work"],
                env={"AWESWITCH_CONFIG": str(config_file)},
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("claude official account", result.output)

    def test_usage_rejects_names_with_all_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            aweswitch.init_config(config_file)

            result = CliRunner().invoke(
                aweswitch.cli, ["usage", "cxo-work", "--all-codex"],
                env={"AWESWITCH_CONFIG": str(config_file)},
            )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("pass account names or --all-codex, not both", result.output)

    def test_usage_success_renders_human_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-work": {"auth": {"tokens": {"access_token": "tok"}}},
                }}},
            }) + "\n")
            mock_usage = unittest.mock.MagicMock()
            mock_usage.UsageError = type("UsageError", (Exception,), {})
            mock_usage.load_codex_credentials.return_value = {"tokens": {"access_token": "tok"}}
            mock_usage.fetch_codex_usage.return_value = {
                "plan": "pro",
                "windows": {"5h": {"used_percentage": 50, "window_minutes": 300, "reset_unix_timestamp": int(time.time()) + 3600}},
                "credits": {"used": 5},
                "tokens": {"used": 1000},
            }

            with unittest.mock.patch.dict(sys.modules, {"aweswitch.usage": mock_usage}):
                result = CliRunner().invoke(
                    aweswitch.cli, ["usage", "cxo-work"],
                    env={"AWESWITCH_CONFIG": str(config_file)},
                )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("cxo-work:", result.output)
        self.assertIn("Plan:", result.output)
        self.assertIn("pro", result.output)
        self.assertIn("Credits:", result.output)
        self.assertIn("tokens:", result.output)
        self.assertIn("resets", result.output)

    def test_usage_visual_progress_bar_rendering(self):
        import time
        now = int(time.time())
        three_days = int(now + 3 * 86400)
        payload = {
            "plan": "plus",
            "windows": {
                "primary": {"used_percentage": 22, "window_minutes": 300, "reset_unix_timestamp": now + 3600},
                "secondary": {"used_percentage": 75, "window_minutes": 10080, "reset_unix_timestamp": three_days},
            },
            "credits": {"has_credits": False, "unlimited": False},
            "token_profile": {
                "lifetime_tokens": 109164593,
                "peak_daily_tokens": 27617967,
                "longest_running_turn_sec": 414,
                "current_streak_days": 7,
                "daily_usage_buckets": [
                    {"start_date": "2026-09-10", "tokens": 968649},
                    {"start_date": "2026-09-11", "tokens": 27617967},
                    {"start_date": "2026-09-12", "tokens": 10594275},
                    {"start_date": "2026-09-13", "tokens": 15232178},
                    {"start_date": "2026-09-14", "tokens": 19625689},
                    {"start_date": "2026-09-15", "tokens": 17003864},
                    {"start_date": "2026-09-16", "tokens": 18121971},
                ],
            },
        }
        out = aweswitch._format_human_usage("cxo-peng", payload)
        self.assertIn("cxo-peng:", out)
        self.assertIn("Plan:", out)
        self.assertIn("plus", out)
        self.assertIn("5h limit", out)
        self.assertIn("Weekly limit", out)
        self.assertIn("78% left", out)
        self.assertIn("25% left", out)
        self.assertIn("resets", out)
        self.assertIn("\u2588", out)
        self.assertIn("Credits:", out)
        self.assertIn("none", out)
        self.assertIn("109.2M lifetime", out)
        self.assertIn("peak 27.6M/day", out)
        self.assertIn("streak 7d", out)
        self.assertIn("longest turn 6m54s", out)
        self.assertIn("Last 7 days:", out)
        self.assertIn("10 Sep - 16 Sep", out)
        self.assertIn("\u2581", out)

    def test_usage_progress_helpers(self):
        bar, remaining = aweswitch._usage_progress(88)
        self.assertEqual(remaining, 12)
        self.assertEqual(bar.count("\u2588"), 2)
        self.assertIsNone(aweswitch._usage_reset_text(None))
        self.assertIsNone(aweswitch._usage_reset_text("nope"))
        self.assertEqual(aweswitch._usage_window_label("primary", {"window_minutes": 300}), "5h limit")
        self.assertEqual(aweswitch._usage_window_label("x", {"window_minutes": 10080}), "Weekly limit")
        self.assertEqual(aweswitch._usage_compact_count(968649), "968.6K")
        self.assertEqual(aweswitch._usage_compact_count(109164593), "109.2M")
        self.assertEqual(aweswitch._usage_compact_count(42), "42")
        self.assertEqual(aweswitch._usage_compact_duration(414), "6m54s")
        self.assertEqual(aweswitch._usage_compact_duration(3720), "1h02m")
        self.assertEqual(aweswitch._usage_credits_text(5), "balance 5")
        self.assertEqual(aweswitch._usage_credits_text({"unlimited": True}), "unlimited")
        self.assertEqual(aweswitch._usage_credits_text({"balance": 12}), "balance 12")
        self.assertEqual(aweswitch._usage_credits_text({"has_credits": False}), "none")
        self.assertIsNone(aweswitch._usage_sparkline([{"tokens": 5}]))
        self.assertEqual(
            aweswitch._usage_sparkline([
                {"tokens": 968649}, {"tokens": 27617967}, {"tokens": 10594275},
                {"tokens": 15232178}, {"tokens": 19625689}, {"tokens": 17003864},
                {"tokens": 18121971},
            ]),
            "\u2581\u2588\u2584\u2585\u2586\u2585\u2586",
        )
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-ok": {"auth": {"tokens": {"access_token": "ok"}}},
                    "cxo-fail": {"auth": {"tokens": {"access_token": "fail"}}},
                }}},
            }) + "\n")
            mock_usage = unittest.mock.MagicMock()
            mock_usage.UsageError = type("UsageError", (Exception,), {})

            def fake_load(path, blob):
                name = path.parent.name
                if name == "cxo-ok":
                    return {"tokens": {"access_token": "ok"}}
                raise mock_usage.UsageError("quota endpoint down")

            mock_usage.load_codex_credentials.side_effect = fake_load
            mock_usage.fetch_codex_usage.return_value = {"plan": "free"}

            with unittest.mock.patch.dict(sys.modules, {"aweswitch.usage": mock_usage}):
                result = CliRunner().invoke(
                    aweswitch.cli, ["usage", "cxo-ok", "cxo-fail"],
                    env={"AWESWITCH_CONFIG": str(config_file)},
                )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("cxo-ok:", result.output)
        self.assertIn("free", result.output)
        self.assertIn("cxo-fail: error: quota endpoint down", result.output)

    def test_usage_json_no_secret_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(json.dumps({
                "profiles": {"api": {}, "accounts": {"codex": {
                    "cxo-work": {"auth": {"tokens": {"access_token": "tok"}}},
                }}},
            }) + "\n")
            mock_usage = unittest.mock.MagicMock()
            mock_usage.UsageError = type("UsageError", (Exception,), {})
            mock_usage.load_codex_credentials.return_value = {"tokens": {"access_token": "tok"}}
            mock_usage.fetch_codex_usage.return_value = {
                "plan": "pro",
                "credits": {"api_key": "secret123", "used": 5},
                "windows": [{"reset": 1700000000}],
            }

            with unittest.mock.patch.dict(sys.modules, {"aweswitch.usage": mock_usage}):
                result = CliRunner().invoke(
                    aweswitch.cli, ["usage", "--json", "cxo-work"],
                    env={"AWESWITCH_CONFIG": str(config_file)},
                )

        self.assertEqual(result.exit_code, 0, result.output)
        parsed = json.loads(result.output)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["account"], "cxo-work")
        self.assertIn("usage", parsed[0])
        self.assertEqual(parsed[0]["usage"]["credits"]["api_key"], "<redacted>")
        self.assertNotIn("access_token", json.dumps(parsed))


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sync_codex_mcp.sh"


def run_sync(tmp_path, *, listed_servers, environment="preview"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "codex.log"
    (bin_dir / "codex").write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$*" >> "$CODEX_LOG"\n'
        'case "$1 $2" in\n'
        "  'mcp get') [ \"${CODEX_CONFIGURED:-0}\" = 1 ] ;;\n"
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    (bin_dir / "terraform").write_text(
        "#!/bin/sh\n"
        'case "$4" in\n'
        "  mcp_url) printf 'https://new-%s.example/mcp\\n' \"${ENVIRONMENT:-unknown}\" ;;\n"
        "  mcp_oauth_client_id) printf 'client-%s\\n' \"${ENVIRONMENT:-unknown}\" ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    for executable in bin_dir.iterdir():
        executable.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CODEX_LOG": str(log),
            "CODEX_CONFIGURED": (
                "1" if f'"name":"family-planner-{environment}"' in listed_servers else "0"
            ),
            "ENVIRONMENT": environment,
            "CODEX_HOME": str(tmp_path / "codex-home"),
        }
    )
    result = subprocess.run(
        ["sh", str(SCRIPT), environment],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result, log.read_text().splitlines()


class SyncCodexMcpTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.tmp_path = Path(self.temp_dir.name)

    def test_replaces_existing_codex_entry_with_deployed_preview_outputs(self):
        result, calls = run_sync(
            self.tmp_path,
            listed_servers='[{"name":"family-planner-preview"}]',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            calls,
            [
                "mcp get family-planner-preview --json",
                "mcp remove family-planner-preview",
                "mcp add family-planner-preview -c mcp_oauth_callback_port=1455 "
                "--url https://new-preview.example/mcp --oauth-client-id client-preview",
            ],
        )
        self.assertIn("codex mcp login family-planner-preview", result.stdout)
        config = tomllib.loads((self.tmp_path / "codex-home" / "config.toml").read_text())
        self.assertEqual(config["mcp_oauth_callback_port"], 1455)

    def test_does_not_remove_a_different_environment_entry(self):
        result, calls = run_sync(
            self.tmp_path,
            listed_servers='[{"name":"family-planner-preview"}]',
            environment="production",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            calls,
            [
                "mcp get family-planner-production --json",
                "mcp add family-planner-production -c mcp_oauth_callback_port=1455 "
                "--url https://new-production.example/mcp --oauth-client-id client-production",
            ],
        )

    def test_persists_port_without_replacing_other_global_codex_settings(self):
        codex_home = self.tmp_path / "codex-home"
        codex_home.mkdir()
        config_path = codex_home / "config.toml"
        config_path.write_text(
            'model = "gpt-6.1-sol"\n'
            "mcp_oauth_callback_port = 58710\n\n"
            '[mcp_servers.other]\nurl = "https://example.test/mcp"\n'
        )

        first, _ = run_sync(self.tmp_path, listed_servers="[]")
        second, _ = run_sync(self.tmp_path, listed_servers="[]")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        config_text = config_path.read_text()
        config = tomllib.loads(config_text)
        self.assertEqual(config["model"], "gpt-6.1-sol")
        self.assertEqual(config["mcp_oauth_callback_port"], 1455)
        self.assertEqual(config["mcp_servers"]["other"]["url"], "https://example.test/mcp")
        self.assertEqual(config_text.count("mcp_oauth_callback_port ="), 1)


if __name__ == "__main__":
    unittest.main()

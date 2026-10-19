#!/usr/bin/env python3
"""Persist Codex's MCP OAuth callback port without replacing other settings."""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
import tomllib
from pathlib import Path


KEY = "mcp_oauth_callback_port"


def config_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "config.toml"
    return Path.home() / ".codex" / "config.toml"


def configure_callback_port(path: Path, port: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text() if path.exists() else ""
    # Refuse to rewrite a malformed config. This keeps deploy from damaging a
    # user's existing Codex settings when the file cannot be parsed safely.
    if original:
        tomllib.loads(original)

    lines = original.splitlines(keepends=True)
    in_table = False
    key_pattern = re.compile(rf"^\s*{re.escape(KEY)}\s*=")
    table_pattern = re.compile(r"^\s*\[\[?.*\]\]\s*(?:#.*)?$")
    insertion_index = len(lines)
    key_index = None

    for index, line in enumerate(lines):
        if table_pattern.match(line):
            in_table = True
            insertion_index = min(insertion_index, index)
        elif not in_table and key_pattern.match(line):
            key_index = index
            break

    setting = f"{KEY} = {port}\n"
    if key_index is not None:
        lines[key_index] = setting
    else:
        lines.insert(insertion_index, setting)

    updated = "".join(lines)
    tomllib.loads(updated)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temp_name = tempfile.mkstemp(prefix=".config.toml.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as config_file:
            config_file.write(updated)
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=1455)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port debe estar entre 1 y 65535")
    configure_callback_port(config_path(), args.port)


if __name__ == "__main__":
    main()

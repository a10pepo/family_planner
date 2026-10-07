"""Require a real labeled GitHub issue reference on pull requests."""

import json
import os
import re
import urllib.request
from pathlib import Path

event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
if "pull_request" not in event:
    print("Issue linkage is checked on pull requests.")
    raise SystemExit(0)
numbers = re.findall(
    r"(?:closes|fixes|resolves|refs)\s+#(\d+)", event["pull_request"].get("body") or "", re.I
)
if not numbers:
    raise SystemExit("PR must reference its issue using Closes #N or Refs #N.")
repo = os.environ["GITHUB_REPOSITORY"]
for number in numbers:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{number}",
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        issue = json.load(response)
    if "pull_request" in issue or not {"issue", "feature"}.intersection(
        label["name"] for label in issue["labels"]
    ):
        raise SystemExit(f"#{number} must be an issue labeled issue or feature.")
print("Issue linkage OK")

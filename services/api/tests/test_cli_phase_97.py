"""Task 97 — CLI-first command layer: new daily-ops commands +
human-readable default output (raw JSON via --json; dry-run stays JSON).
No deploy/merge commands.
"""

import json

import pytest

from app import cli


@pytest.mark.parametrize(
    "command",
    [
        "list-projects",
        "list-tickets",
        "dev-tasks",
        "approvals",
        "events",
        "jobs",
        "providers",
        "cost",
        "worker-run-once",
    ],
)
def test_new_commands_registered(command):
    assert command in cli._COMMANDS


def test_no_deploy_or_merge_commands():
    joined = " ".join(cli._COMMANDS)
    for forbidden in ("deploy", "merge", "push", "force"):
        assert forbidden not in joined


def test_render_human_list_and_dict():
    assert cli.render_human([]) == "(empty)"
    rows = cli.render_human(
        [{"id": "p1", "name": "Proj", "status": "active"}]
    )
    assert "id=p1" in rows and "name=Proj" in rows
    obj = cli.render_human({"enabled": True, "count": 3})
    assert "enabled: True" in obj and "count: 3" in obj
    assert cli.render_human({"error": "boom"}) == "ERROR: boom"


def test_human_default_dryrun_json(capsys):
    # Real result -> human-readable by default; dry-run -> JSON.
    rc = cli.main(["providers", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    # dry-run prints a JSON request envelope (parseable).
    assert json.loads(out)["method"] == "GET"


def test_json_flag_forces_json(capsys):
    cli.main(["list-projects", "--dry-run", "--json"])
    out = capsys.readouterr().out
    assert json.loads(out)["url"].endswith("/projects")

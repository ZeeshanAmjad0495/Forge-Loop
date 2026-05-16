"""Task 84: CLI tests. Fully offline — only the --dry-run path is used."""

import json

import pytest

from app import cli


def test_parser_builds_and_help():
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as e:
        parser.parse_args(["--help"])
    assert e.value.code == 0


def test_resolve_create_project():
    parser = cli.build_parser()
    args = parser.parse_args(
        ["create-project", "--name", "X", "--description", "Y"]
    )
    method, path, body = cli._resolve("create-project", args)
    assert method == "POST"
    assert path == "/projects"
    assert body == {"name": "X", "description": "Y"}


def test_resolve_path_param_substitution():
    parser = cli.build_parser()
    args = parser.parse_args(
        ["create-ticket", "--project", "P1", "--title", "T",
         "--description", "D"]
    )
    method, path, body = cli._resolve("create-ticket", args)
    assert method == "POST"
    assert path == "/projects/P1/tickets"
    assert body == {"title": "T", "description": "D"}


def test_runtime_topic_path():
    parser = cli.build_parser()
    args = parser.parse_args(["runtime", "--topic", "cache"])
    method, path, _ = cli._resolve("runtime", args)
    assert (method, path) == ("GET", "/runtime/cache")


def test_dry_run_sends_nothing(capsys):
    code = cli.main(
        [
            "--dry-run",
            "create-project",
            "--name",
            "Demo",
            "--description",
            "d",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["method"] == "POST"
    assert out["url"].endswith("/projects")
    assert out["body"] == {"name": "Demo", "description": "d"}


def test_login_requires_credentials():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["login"])  # missing required --email/--password


def test_unknown_command_rejected():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["not-a-command"])


def test_request_dry_run_helper_offline():
    # No network: dry_run must short-circuit before urlopen.
    out = cli._request(
        "GET", "/projects", base_url="http://localhost:8080", dry_run=True
    )
    assert out == {
        "dry_run": True,
        "method": "GET",
        "url": "http://localhost:8080/projects",
        "body": None,
    }


# R-D regression: global flags must work AFTER the subcommand (the
# documented/natural order — previously errored "unrecognized arguments").
def test_global_flags_after_subcommand(capsys):
    code = cli.main(
        ["create-project", "--name", "X", "--description", "Y", "--dry-run"]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["url"].endswith("/projects")
    assert out["body"] == {"name": "X", "description": "Y"}


def test_global_flags_before_subcommand_still_work(capsys):
    code = cli.main(
        ["--dry-run", "create-project", "--name", "X", "--description", "Y"]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True


def test_token_and_base_url_after_subcommand(capsys):
    code = cli.main(
        [
            "cost",
            "--project",
            "P1",
            "--base-url",
            "http://example.test:9",
            "--token",
            "tok",
            "--dry-run",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["url"] == "http://example.test:9/projects/P1/cost-report"
    assert out["method"] == "GET"

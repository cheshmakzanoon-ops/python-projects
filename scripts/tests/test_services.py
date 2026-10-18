"""Service management must preserve unrelated containers and local-only access."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "services.py"
spec = importlib.util.spec_from_file_location("services", MODULE)
assert spec and spec.loader
services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(services)


@pytest.mark.parametrize("action", ["up", "down", "status"])
@pytest.mark.parametrize("labels", [None, {}, {"pp.owner": "another-project"}])
def test_matching_name_does_not_authorize_container_mutations(monkeypatch, action, labels):
    calls = []

    def run(*args):
        calls.append(args)
        if args[0] == "ps":
            return "pp-anchor-dev"
        if args[0] == "inspect":
            return json.dumps(labels)
        pytest.fail(f"unowned container was mutated: {args}")

    monkeypatch.setattr(services, "run", run)
    monkeypatch.setattr(sys, "argv", ["services.py", action, "anchor"])
    with pytest.raises(SystemExit, match="refusing to manage"):
        services.main()
    assert [call[0] for call in calls] == ["ps", "inspect"]


def test_down_removes_owned_container_volumes_and_stale_metadata(monkeypatch, tmp_path):
    calls = []
    metadata = tmp_path / ".local/services/anchor.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text('{"url":"postgresql://anchor@127.0.0.1:32768/anchor"}')

    def run(*args):
        calls.append(args)
        return {"ps": "pp-anchor-dev", "inspect": '{"pp.owner":"portfolio"}', "rm": ""}[args[0]]

    monkeypatch.setattr(services, "run", run)
    monkeypatch.setattr(services, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["services.py", "down", "anchor"])
    services.main()
    assert calls[-1] == ("rm", "-f", "-v", "pp-anchor-dev")
    assert not metadata.exists()


def test_up_refuses_public_binding_before_starting_container(monkeypatch):
    calls = []

    def run(*args):
        calls.append(args)
        if args[0] == "ps":
            return "pp-anchor-dev"
        if args[0] == "inspect" and ".Config.Labels" in args[2]:
            return '{"pp.owner":"portfolio"}'
        if args[0] == "inspect" and ".HostConfig.PortBindings" in args[2]:
            return '{"5432/tcp":[{"HostIp":"0.0.0.0","HostPort":"5432"}]}'
        pytest.fail(f"public trust-authenticated database was started: {args}")

    monkeypatch.setattr(services, "run", run)
    monkeypatch.setattr(sys, "argv", ["services.py", "up", "anchor"])
    with pytest.raises(SystemExit, match="loopback"):
        services.main()
    assert [call[0] for call in calls] == ["ps", "inspect", "inspect"]


@pytest.mark.parametrize(
    "bindings",
    [
        None,
        {},
        {"5432/tcp": None},
        {"5432/tcp": []},
        {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5432"}]},
        {"5432/tcp": [{"HostIp": "::", "HostPort": "5432"}]},
        {
            "5432/tcp": [
                {"HostIp": "127.0.0.1", "HostPort": "5432"},
                {"HostIp": "0.0.0.0", "HostPort": "5432"},
            ]
        },
        {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "invalid"}]},
        {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "0"}]},
        {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "65536"}]},
    ],
)
def test_refuses_missing_or_public_trust_database_bindings(monkeypatch, bindings):
    monkeypatch.setattr(services, "run", lambda *args: json.dumps(bindings))
    with pytest.raises(SystemExit, match="port binding"):
        services.database_port("pp-anchor-dev")


def test_reads_single_loopback_binding(monkeypatch):
    monkeypatch.setattr(
        services,
        "run",
        lambda *args: '{"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"32768"}]}',
    )
    assert services.database_port("pp-anchor-dev") == 32768


@pytest.mark.parametrize("port", ["", "0"])
def test_configured_dynamic_port_is_valid_but_not_a_live_connection(monkeypatch, port):
    monkeypatch.setattr(
        services,
        "run",
        lambda *args: json.dumps({"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": port}]}),
    )
    assert services.database_port("pp-anchor-dev", configured=True) == 0
    with pytest.raises(SystemExit, match="invalid.*port binding"):
        services.database_port("pp-anchor-dev")

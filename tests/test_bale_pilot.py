"""Pilot defaults must never prompt for credentials or touch the network."""
import importlib.util
from pathlib import Path


def pilot():
    path = Path(__file__).resolve().parents[1] / "scripts" / "bale_product_pilot.py"
    spec = importlib.util.spec_from_file_location("bale_pilot_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_pilot_is_off_even_with_action_and_origin(monkeypatch, capsys):
    module = pilot()
    def forbidden(*args, **kwargs):
        raise AssertionError("Default pilot must remain offline")
    monkeypatch.setattr(module, "getpass", forbidden)
    monkeypatch.setattr(module, "build_opener", forbidden)
    assert module.main(["--action", "send", "--origin", "http://127.0.0.1:8765"]) == 0
    assert "OFF (no network" in capsys.readouterr().out


def test_live_pilot_rejects_remote_origin_before_credentials(monkeypatch, capsys):
    module = pilot()
    def forbidden(*args, **kwargs):
        raise AssertionError("No credentials for rejected origins")
    monkeypatch.setattr(module, "getpass", forbidden)
    assert module.main(["--allow-live", "--origin", "http://example.test:8765"]) == 2
    assert capsys.readouterr().out.strip() == "pilot_origin_invalid"

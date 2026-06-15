"""Dashboard chat backend configuration and Ollama capability tests."""
import json

from fastapi.testclient import TestClient

from src.dashboard import chat, config as dash_config
from src.dashboard.server import app


def _settings(model="qwen3.5:9b", base_url="http://127.0.0.1:11434"):
    return {
        "provider": "ollama",
        "model": model,
        "base_url": base_url,
        "api_key_env": "",
    }


def test_chat_config_defaults_and_round_trips_atomically(tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    monkeypatch.setattr(dash_config, "CHAT_MODEL", "qwen3.5:9b")
    monkeypatch.setattr(dash_config, "OLLAMA_URL", "http://127.0.0.1:11434")
    client = TestClient(app)

    default = client.get("/api/chat/config")
    assert default.status_code == 200
    assert default.json() == _settings()

    saved = _settings(model="llama3.1:8b", base_url="http://localhost:11434/")
    response = client.put("/api/chat/config", json=saved)

    assert response.status_code == 200
    assert response.json() == _settings(
        model="llama3.1:8b", base_url="http://localhost:11434")
    assert json.loads(path.read_text(encoding="utf-8")) == response.json()
    assert client.get("/api/chat/config").json() == response.json()
    assert not list(tmp_path.glob(".chat_settings.json.*.tmp"))


def test_chat_config_rejects_secrets_and_unsupported_providers(tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    client = TestClient(app)

    with_secret = {**_settings(), "api_key": "do-not-store-this"}
    response = client.put("/api/chat/config", json=with_secret)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_chat_config"
    assert not path.exists()

    external = _settings()
    external["provider"] = "openrouter"
    response = client.put("/api/chat/config", json=external)
    assert response.status_code == 400
    assert "Phase 1" in response.json()["detail"]
    assert not path.exists()


def test_chat_models_lists_installed_ollama_models(tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    chat.save_chat_settings(_settings(model="qwen3.5:9b"))
    seen = {}

    def fake_request(settings, endpoint, payload=None, timeout=30):
        seen.update(settings=settings, endpoint=endpoint, payload=payload, timeout=timeout)
        return {
            "models": [
                {"name": "qwen3.5:9b", "size": 6_000, "details": {"family": "qwen3"}},
                {"model": "llama3.1:8b", "size": 5_000},
            ]
        }

    monkeypatch.setattr(chat, "_ollama_request", fake_request)
    response = TestClient(app).get("/api/chat/models")

    assert response.status_code == 200
    assert response.json()["selected_model"] == "qwen3.5:9b"
    assert [item["name"] for item in response.json()["models"]] == [
        "llama3.1:8b", "qwen3.5:9b"]
    assert seen["endpoint"] == "/api/tags"
    assert seen["payload"] is None
    assert seen["timeout"] == 10


def test_chat_models_reports_malformed_ollama_response(tmp_path, monkeypatch):
    monkeypatch.setattr(
        dash_config, "CHAT_SETTINGS_PATH", tmp_path / "chat_settings.json")
    monkeypatch.setattr(chat, "_ollama_request", lambda *args, **kwargs: [])

    response = TestClient(app).get("/api/chat/models")

    assert response.status_code == 502
    assert response.json()["error"] == "ollama_unavailable"


def test_chat_self_test_emits_and_executes_whitelisted_tool(tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    chat.save_chat_settings(_settings(model="tool-model"))
    executed = []

    def fake_call(messages, settings=None, timeout=300):
        assert settings["model"] == "tool-model"
        assert timeout == 300
        assert "get_model_metrics" in messages[-1]["content"]
        return {
            "message": {
                "tool_calls": [{
                    "function": {"name": "get_model_metrics", "arguments": {}}
                }]
            },
            "eval_count": 20,
            "eval_duration": 1_000_000_000,
        }

    monkeypatch.setattr(chat, "_ollama_call", fake_call)
    monkeypatch.setitem(
        chat.TOOLS, "get_model_metrics",
        {**chat.TOOLS["get_model_metrics"], "fn": lambda: executed.append(True)})

    response = TestClient(app).post("/api/chat/test")

    assert response.status_code == 200
    assert response.json() == {
        "passed": True,
        "provider": "ollama",
        "model": "tool-model",
        "tool": "get_model_metrics",
        "tokens_per_second": 20.0,
        "detail": "tool call emitted and executed",
    }
    assert executed == [True]


def test_chat_self_test_fails_when_model_answers_without_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(
        dash_config, "CHAT_SETTINGS_PATH", tmp_path / "chat_settings.json")
    monkeypatch.setattr(
        chat, "_ollama_call",
        lambda messages, settings=None, timeout=300: {
            "message": {"content": "The metric is..."},
            "eval_count": 3,
            "eval_duration": 1_000_000_000,
        })

    response = TestClient(app).post("/api/chat/test")

    assert response.status_code == 200
    assert response.json()["passed"] is False
    assert response.json()["tool"] is None


def test_ollama_chat_call_uses_persisted_model_and_base_url(tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    chat.save_chat_settings(
        _settings(model="chosen:latest", base_url="http://ollama.local:11434"))
    seen = {}

    def fake_request(settings, endpoint, payload=None, timeout=30):
        seen.update(settings=settings, endpoint=endpoint, payload=payload, timeout=timeout)
        return {"message": {"content": "ok"}}

    monkeypatch.setattr(chat, "_ollama_request", fake_request)

    chat._ollama_call([{"role": "user", "content": "hello"}])

    assert seen["settings"]["base_url"] == "http://ollama.local:11434"
    assert seen["payload"]["model"] == "chosen:latest"
    assert seen["endpoint"] == "/api/chat"

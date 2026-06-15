"""Dashboard chat backend configuration and provider capability tests."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.dashboard import chat, config as dash_config
from src.dashboard.server import app


def _settings(
        model="qwen3.5:9b",
        base_url="http://127.0.0.1:11434",
        provider="ollama",
        api_key_env=""):
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
    }


def test_chat_settings_ui_wires_config_models_and_self_test():
    app_js = (
        Path(__file__).parents[1] / "src" / "dashboard" / "static" / "app.js"
    ).read_text(encoding="utf-8")

    assert "openChatSettings" in app_js
    assert "t('chat_settings')" in app_js
    assert "fetch('/api/chat/config'" in app_js
    assert "getJSON('/api/chat/models')" in app_js
    assert "fetch('/api/chat/test'" in app_js


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_chat_settings_javascript_is_valid():
    app_js = Path(__file__).parents[1] / "src" / "dashboard" / "static" / "app.js"
    subprocess.run(["node", "--check", str(app_js)], check=True)


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


def test_chat_config_supports_external_provider_without_storing_secret(
        tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    client = TestClient(app)

    external = _settings(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        base_url="https://openrouter.ai/api/v1/",
        api_key_env="OPENROUTER_API_KEY",
    )
    response = client.put("/api/chat/config", json=external)

    assert response.status_code == 200
    assert response.json() == {**external, "base_url": external["base_url"].rstrip("/")}
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted == response.json()
    assert "api_key" not in persisted


@pytest.mark.parametrize("external", [
    {**_settings(), "api_key": "do-not-store-this"},
    _settings(provider="anthropic"),
    _settings(
        provider="openrouter",
        base_url="http://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
    ),
    _settings(
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key_env="",
    ),
])
def test_chat_config_rejects_secrets_and_invalid_external_settings(
        tmp_path, monkeypatch, external):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)

    response = TestClient(app).put("/api/chat/config", json=external)

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_chat_config"
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
                {
                    "name": "qwen3.5:9b",
                    "size": 6 * chat.GIB,
                    "details": {"family": "qwen3"},
                },
                {"model": "llama3.1:8b", "size": 4 * chat.GIB},
            ]
        }

    monkeypatch.setattr(chat, "_ollama_request", fake_request)
    monkeypatch.setattr(
        chat, "detect_hardware",
        lambda **kwargs: {
            "total_ram_bytes": 16 * chat.GIB,
            "total_vram_bytes": 8 * chat.GIB,
            "gpu_name": "Test GPU",
            "ram_source": "test",
            "vram_source": "test",
        })
    response = TestClient(app).get("/api/chat/models")

    assert response.status_code == 200
    assert response.json()["selected_model"] == "qwen3.5:9b"
    assert [item["name"] for item in response.json()["models"]] == [
        "qwen3.5:9b", "llama3.1:8b"]
    assert response.json()["recommendation"] == {
        "model": "qwen3.5:9b",
        "fit": "full_gpu",
        "estimated_runtime_bytes": int(
            6 * chat.GIB * chat.MODEL_WEIGHT_MULTIPLIER)
        + chat.MODEL_FIXED_OVERHEAD_BYTES,
    }
    assert response.json()["fit_heuristic"]["system_ram_reserve_bytes"] == 2 * chat.GIB
    assert response.json()["models"][0]["recommended"] is True
    assert response.json()["models"][0]["rank"] == 1
    assert seen["endpoint"] == "/api/tags"
    assert seen["payload"] is None
    assert seen["timeout"] == 10


def test_nvidia_vram_detection_aggregates_devices(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout="GPU One, 8192\nmalformed\nGPU Two, 4096\n",
        )

    monkeypatch.setattr(chat.subprocess, "run", fake_run)

    assert chat._detect_nvidia_vram() == (
        "GPU One, GPU Two",
        12 * 1024 ** 3,
        "nvidia_smi",
    )
    assert seen["command"][0] == "nvidia-smi"
    assert seen["kwargs"]["timeout"] == 3


def test_chat_models_rank_full_partial_cpu_and_insufficient_fits(
        tmp_path, monkeypatch):
    monkeypatch.setattr(
        dash_config, "CHAT_SETTINGS_PATH", tmp_path / "chat_settings.json")
    monkeypatch.setattr(
        chat, "_ollama_request",
        lambda *args, **kwargs: {
            "models": [
                {"name": "too-large:70b", "size": 70 * chat.GIB},
                {"name": "cpu-capable:40b", "size": 40 * chat.GIB},
                {"name": "partial:16b", "size": 16 * chat.GIB},
                {"name": "full:4b", "size": 4 * chat.GIB},
            ]
        })
    monkeypatch.setattr(
        chat, "detect_hardware",
        lambda **kwargs: {
            "total_ram_bytes": 64 * chat.GIB,
            "total_vram_bytes": 8 * chat.GIB,
            "gpu_name": "Test GPU",
            "ram_source": "test",
            "vram_source": "test",
        })

    payload = TestClient(app).get("/api/chat/models").json()

    assert [(model["name"], model["fit"]) for model in payload["models"]] == [
        ("full:4b", "full_gpu"),
        ("partial:16b", "partial_gpu"),
        ("cpu-capable:40b", "cpu"),
        ("too-large:70b", "insufficient"),
    ]
    assert payload["recommendation"]["model"] == "full:4b"
    assert [model["rank"] for model in payload["models"]] == [1, 2, 3, 4]


def test_chat_models_accepts_manual_memory_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(
        dash_config, "CHAT_SETTINGS_PATH", tmp_path / "chat_settings.json")
    monkeypatch.setattr(
        chat, "_ollama_request",
        lambda *args, **kwargs: {"models": []})
    seen = {}

    def fake_detect_hardware(total_ram_bytes=None, total_vram_bytes=None):
        seen.update(ram=total_ram_bytes, vram=total_vram_bytes)
        return {
            "total_ram_bytes": total_ram_bytes,
            "total_vram_bytes": total_vram_bytes,
            "gpu_name": "Manual override",
            "ram_source": "manual",
            "vram_source": "manual",
        }

    monkeypatch.setattr(chat, "detect_hardware", fake_detect_hardware)

    response = TestClient(app).get("/api/chat/models?ram_gb=24&vram_gb=6.5")

    assert response.status_code == 200
    assert seen == {
        "ram": 24 * chat.GIB,
        "vram": int(6.5 * chat.GIB),
    }
    assert response.json()["hardware"]["ram_source"] == "manual"
    assert response.json()["hardware"]["vram_source"] == "manual"


@pytest.mark.parametrize("query", ["ram_gb=0", "vram_gb=-1", "vram_gb=2048"])
def test_chat_models_rejects_invalid_memory_overrides(query):
    response = TestClient(app).get(f"/api/chat/models?{query}")

    assert response.status_code == 422


def test_chat_models_reports_malformed_ollama_response(tmp_path, monkeypatch):
    monkeypatch.setattr(
        dash_config, "CHAT_SETTINGS_PATH", tmp_path / "chat_settings.json")
    monkeypatch.setattr(chat, "_ollama_request", lambda *args, **kwargs: [])

    response = TestClient(app).get("/api/chat/models")

    assert response.status_code == 502
    assert response.json()["error"] == "ollama_unavailable"


def test_chat_models_does_not_query_local_endpoint_for_external_provider(
        tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    chat.save_chat_settings(_settings(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
    ))
    monkeypatch.setattr(
        chat, "_ollama_request",
        lambda *args, **kwargs: pytest.fail("external provider queried Ollama"))

    response = TestClient(app).get("/api/chat/models")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "selected_model": "openai/gpt-4.1-mini",
        "models": [],
    }


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

    monkeypatch.setattr(chat, "_chat_call", fake_call)
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
        chat, "_chat_call",
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


def test_external_chat_call_uses_bearer_key_and_normalizes_response(
        tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-test-key")
    chat.save_chat_settings(_settings(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
    ))
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_metrics",
                            "type": "function",
                            "function": {
                                "name": "get_model_metrics",
                                "arguments": "{}",
                            },
                        }],
                    },
                }],
                "usage": {"completion_tokens": 12},
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        seen.update(request=request, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(chat.urllib.request, "urlopen", fake_urlopen)
    response = chat._chat_call([{"role": "user", "content": "metrics"}])

    request = seen["request"]
    payload = json.loads(request.data)
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer runtime-test-key"
    assert request.get_header("Http-referer") == (
        "https://github.com/SandroHub013/UnaBetting")
    assert seen["timeout"] == 300
    assert payload["model"] == "openai/gpt-4.1-mini"
    assert payload["tool_choice"] == "auto"
    assert any(
        item["function"]["name"] == "get_model_metrics"
        for item in payload["tools"]
    )
    assert response["message"]["tool_calls"][0]["id"] == "call_metrics"


def test_external_self_test_reports_usage_rate_and_executes_tool(
        tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    chat.save_chat_settings(_settings(
        provider="openai",
        model="gpt-4.1-mini",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
    ))
    monkeypatch.setattr(chat, "_chat_call", lambda *args, **kwargs: {
        "message": {
            "tool_calls": [{
                "id": "call_metrics",
                "function": {
                    "name": "get_model_metrics",
                    "arguments": "{}",
                },
            }],
        },
        "usage": {"completion_tokens": 18},
    })
    monkeypatch.setattr(
        chat, "_tokens_per_second",
        lambda response, elapsed: 9.0
        if response["usage"]["completion_tokens"] == 18 and elapsed >= 0
        else None,
    )
    executed = []
    monkeypatch.setitem(
        chat.TOOLS, "get_model_metrics",
        {**chat.TOOLS["get_model_metrics"], "fn": lambda: executed.append(True)})

    response = TestClient(app).post("/api/chat/test")

    assert response.status_code == 200
    assert response.json()["passed"] is True
    assert response.json()["provider"] == "openai"
    assert response.json()["tokens_per_second"] == 9.0
    assert executed == [True]


def test_external_tokens_per_second_uses_completion_usage():
    assert chat._tokens_per_second(
        {"usage": {"completion_tokens": 18}}, elapsed=2.0) == 9.0


def test_external_provider_requires_runtime_api_key(tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    chat.save_chat_settings(_settings(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
    ))

    response = TestClient(app).post("/api/chat/test")

    assert response.status_code == 502
    assert response.json()["error"] == "chat_provider_unavailable"
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_external_websocket_round_trips_tool_call_id(tmp_path, monkeypatch):
    path = tmp_path / "chat_settings.json"
    monkeypatch.setattr(dash_config, "CHAT_SETTINGS_PATH", path)
    chat.save_chat_settings(_settings(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
    ))
    calls = []

    def fake_call(messages, settings=None, timeout=300):
        calls.append(json.loads(json.dumps(messages)))
        if len(calls) == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_metrics",
                        "type": "function",
                        "function": {
                            "name": "get_model_metrics",
                            "arguments": "{}",
                        },
                    }],
                },
            }
        return {"message": {"role": "assistant", "content": "Metrics loaded."}}

    monkeypatch.setattr(chat, "_chat_call", fake_call)
    monkeypatch.setitem(
        chat.TOOLS, "get_model_metrics",
        {**chat.TOOLS["get_model_metrics"], "fn": lambda: {"accuracy": 0.67}})

    with TestClient(app).websocket_connect("/ws/chat") as ws:
        ws.send_text(json.dumps({"text": "Show metrics"}))
        assert json.loads(ws.receive_text()) == {
            "type": "tool", "name": "get_model_metrics", "status": "start"}
        assert json.loads(ws.receive_text()) == {
            "type": "tool", "name": "get_model_metrics", "status": "done"}
        reply = json.loads(ws.receive_text())

    assert reply["type"] == "reply"
    assert reply["text"] == "Metrics loaded."
    tool_message = calls[1][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_metrics"
    assert "tool_name" not in tool_message

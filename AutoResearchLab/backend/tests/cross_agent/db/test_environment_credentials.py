"""Environment-only API credential resolution tests."""

from db.db_settings import _resolve_config


def test_environment_credentials_override_saved_preset(monkeypatch):
    monkeypatch.setenv("MAARS_API_KEY", "environment-secret")
    monkeypatch.setenv("MAARS_MODEL", "gemini-2.5-flash")

    config = _resolve_config(
        {
            "agentMode": {
                "ideaAgent": "llm",
                "planAgent": "mock",
                "taskAgent": "mock",
                "paperAgent": "mock",
            },
            "current": "default",
            "presets": {
                "default": {
                    "label": "Default",
                    "apiKey": "browser-secret",
                    "model": "browser-model",
                }
            },
        }
    )

    assert config["apiKey"] == "environment-secret"
    assert config["model"] == "gemini-2.5-flash"
    assert config["ideaUseMock"] is False

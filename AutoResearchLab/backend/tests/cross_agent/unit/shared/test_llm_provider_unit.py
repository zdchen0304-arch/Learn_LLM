"""Provider-selection tests that do not make external API calls."""

from shared.llm_client import (
    DEEPSEEK_DEFAULT_MODEL,
    _model_for,
    _provider_for,
    merge_phase_config,
)


def test_deepseek_provider_uses_compatible_defaults():
    config = merge_phase_config(
        {"provider": "deepseek", "apiKey": "ignored-for-this-test"},
        "idea",
    )

    assert _provider_for(config) == "deepseek"
    assert _model_for(config, "deepseek") == DEEPSEEK_DEFAULT_MODEL


def test_gemini_provider_remains_default():
    config = merge_phase_config({}, "idea")

    assert _provider_for(config) == "gemini"

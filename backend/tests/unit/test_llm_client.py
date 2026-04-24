import logging

import pytest

from app.core.config import settings
from app.services.llm import llm_client


class _FakeUsage:
    prompt_token_count = 12
    candidates_token_count = 34
    total_token_count = 46


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.usage_metadata = _FakeUsage()


class _FakeModel:
    def __init__(self, response_text: str):
        self._response_text = response_text

    def generate_content(self, prompt: str):
        _ = prompt
        return _FakeResponse(self._response_text)


class _FailingModel:
    def generate_content(self, prompt: str):
        _ = prompt
        raise RuntimeError("model unavailable")


@pytest.mark.asyncio
async def test_gemini_generate_success_logs_summary(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    monkeypatch.setattr(llm_client, "_get_model", lambda: _FakeModel("hello from model"))
    monkeypatch.setattr(settings, "llm_log_payloads", False)

    with caplog.at_level(logging.INFO, logger="app.services.llm.llm_client"):
        response_text = await llm_client.gemini_generate(
            purpose="assessment_questions",
            prompt="Generate quiz questions",
        )

    assert response_text == "hello from model"
    assert "llm_call:" in caplog.text
    assert "'purpose': 'assessment_questions'" in caplog.text
    assert "'ok': True" in caplog.text
    assert "'llm_ms':" in caplog.text
    assert "'usage':" in caplog.text


@pytest.mark.asyncio
async def test_gemini_generate_failure_logs_error_type(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    monkeypatch.setattr(llm_client, "_get_model", lambda: _FailingModel())
    monkeypatch.setattr(settings, "llm_log_payloads", False)

    with caplog.at_level(logging.ERROR, logger="app.services.llm.llm_client"):
        with pytest.raises(RuntimeError, match="model unavailable"):
            await llm_client.gemini_generate(
                purpose="resume_skill_extraction",
                prompt="Extract skills",
            )

    assert "llm_call:" in caplog.text
    assert "'purpose': 'resume_skill_extraction'" in caplog.text
    assert "'ok': False" in caplog.text
    assert "'error_type': 'RuntimeError'" in caplog.text

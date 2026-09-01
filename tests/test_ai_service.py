from app.services.ai_service import AIService, AIResult, UnavailableAIProvider


def test_ai_is_disabled_by_default():
    service = AIService.from_config({
        "AI_ENABLED": False,
        "AI_PROVIDER": "gemini",
        "GEMINI_ENABLED": True,
        "GEMINI_API_KEY": "not-used",
    })

    assert service.is_available() is False
    result = service.generate_text("hello")
    assert result.success is False
    assert result.error == "ai_unavailable"
    assert result.provider == "none"


def test_missing_gemini_key_is_non_blocking():
    service = AIService.from_config({
        "AI_ENABLED": True,
        "AI_PROVIDER": "gemini",
        "GEMINI_ENABLED": True,
        "GEMINI_API_KEY": "",
    })

    assert service.is_available() is False
    assert isinstance(service.provider, UnavailableAIProvider)


def test_unknown_provider_is_non_blocking():
    service = AIService.from_config({
        "AI_ENABLED": True,
        "AI_PROVIDER": "unknown",
    })

    assert service.is_available() is False


def test_empty_prompt_is_rejected():
    service = AIService()
    result = service.generate_text("   ")

    assert isinstance(result, AIResult)
    assert result.success is False
    assert result.error == "empty_prompt"

from app.elevenlabs import extract_error_message, public_error_status


def test_invalid_key_message():
    message = extract_error_message(
        401,
        {"detail": {"status": "invalid_api_key", "message": "Invalid API key"}},
    )
    assert message == "Invalid ElevenLabs API key: Invalid API key"
    assert public_error_status(401) == 401


def test_paid_plan_voice_message():
    message = extract_error_message(
        402,
        {
            "detail": {
                "status": "payment_required",
                "message": "This voice requires a paid subscription.",
            }
        },
    )
    assert message.startswith("ElevenLabs voice is not available on this plan:")
    assert "paid subscription" in message


def test_rate_limit_message():
    message = extract_error_message(429, {"detail": {"message": "Too many requests"}})
    assert message == "ElevenLabs rate limit: Too many requests"
    assert public_error_status(429) == 429

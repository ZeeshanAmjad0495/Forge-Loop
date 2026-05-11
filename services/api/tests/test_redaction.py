from app.utils.redaction import redact_sensitive_text


def test_redacts_bearer_token():
    text = "Error: Authorization: Bearer eyJhbGc.abc123.xyz"
    result = redact_sensitive_text(text)
    assert "eyJhbGc.abc123.xyz" not in result
    assert "Authorization: Bearer [REDACTED]" in result


def test_redacts_api_key_equals():
    result = redact_sensitive_text("request failed: api_key=sk-supersecret")
    assert "sk-supersecret" not in result
    assert "[REDACTED]" in result


def test_redacts_api_key_colon():
    result = redact_sensitive_text("api_key: my-secret-key-value")
    assert "my-secret-key-value" not in result
    assert "[REDACTED]" in result


def test_redacts_api_dash_key():
    result = redact_sensitive_text("api-key=abc123def456")
    assert "abc123def456" not in result
    assert "[REDACTED]" in result


def test_redacts_token_equals():
    result = redact_sensitive_text("token=bearer-abc-xyz")
    assert "bearer-abc-xyz" not in result
    assert "[REDACTED]" in result


def test_redacts_password_equals():
    result = redact_sensitive_text("password=hunter2")
    assert "hunter2" not in result
    assert "[REDACTED]" in result


def test_redacts_secret_equals():
    result = redact_sensitive_text("secret=topsecretvalue123")
    assert "topsecretvalue123" not in result
    assert "[REDACTED]" in result


def test_redacts_sk_style_key():
    result = redact_sensitive_text("provider error: sk-abcdefgh12345678")
    assert "sk-abcdefgh12345678" not in result
    assert "[REDACTED]" in result


def test_plain_message_unchanged():
    text = "Connection refused: unable to reach api.example.com"
    assert redact_sensitive_text(text) == text


def test_empty_string_unchanged():
    assert redact_sensitive_text("") == ""


def test_preserves_surrounding_text():
    text = "HTTP 401: token=bad-token-value while calling endpoint"
    result = redact_sensitive_text(text)
    assert "HTTP 401:" in result
    assert "while calling endpoint" in result
    assert "bad-token-value" not in result

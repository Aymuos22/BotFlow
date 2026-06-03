from app.integrations.meta_whatsapp.signature import is_valid_meta_webhook_body


def test_valid_meta_signature() -> None:
    raw = b'{"hello":"world"}'
    secret = "test_app_secret"
    import hashlib
    import hmac

    expected = (
        "sha256="
        + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    )
    assert is_valid_meta_webhook_body(
        app_secret=secret, raw_body=raw, signature_header=expected
    )


def test_invalid_meta_signature() -> None:
    assert not is_valid_meta_webhook_body(
        app_secret="a",
        raw_body=b"{}",
        signature_header="sha256=deadbeef",
    )

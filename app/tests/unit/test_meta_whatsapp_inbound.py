"""Unit tests for Meta WhatsApp Cloud API inbound parsing."""

from app.integrations.meta_whatsapp.inbound import (
    extract_phone_number_id_from_meta_payload,
    iter_meta_inbound_events,
)


def test_iter_meta_inbound_text_message() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "109876543210"},
                            "messages": [
                                {
                                    "from": "918811223344",
                                    "id": "wamid.abc",
                                    "timestamp": "123",
                                    "type": "text",
                                    "text": {"body": "Hello bot"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    events = list(iter_meta_inbound_events(payload))
    assert len(events) == 1
    e = events[0]
    assert e.phone_number_id == "109876543210"
    assert e.external_message_id == "wamid.abc"
    assert e.text == "Hello bot"
    assert e.customer_phone_e164 == "+918811223344"


def test_extract_phone_number_id() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "555"},
                            "statuses": [],
                        }
                    }
                ]
            }
        ],
    }
    assert extract_phone_number_id_from_meta_payload(payload) == "555"


def test_iter_meta_inbound_audio_message() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "109876543210"},
                            "messages": [
                                {
                                    "from": "918811223344",
                                    "id": "wamid.audio",
                                    "timestamp": "123",
                                    "type": "audio",
                                    "audio": {
                                        "id": "MEDIA_ID",
                                        "mime_type": "audio/ogg",
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }

    events = list(iter_meta_inbound_events(payload))

    assert len(events) == 1
    assert events[0].message_type == "audio"
    assert events[0].media_id == "MEDIA_ID"
    assert events[0].media_mime_type == "audio/ogg"
    assert events[0].text == ""

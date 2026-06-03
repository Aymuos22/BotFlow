"""Unit tests for AiSensy inbound webhook parsing."""

from app.integrations.aisensy.inbound import iter_aisensy_inbound_events


def test_flat_json_extracts_routing_and_customer():
    payload = {
        "messageId": "m1",
        "from": "9198111222333",
        "to": "918888887777",
        "message": "Hello",
    }
    events = list(iter_aisensy_inbound_events(payload))
    assert len(events) == 1
    ev = events[0]
    assert ev.external_message_id == "m1"
    assert ev.customer_phone_e164 == "+9198111222333"
    assert ev.business_routing_key == "whatsapp:+918888887777"
    assert ev.text == "Hello"


def test_meta_envelope_extracts_message():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "+918000000000"},
                            "messages": [
                                {
                                    "from": "9198111222333",
                                    "id": "wamid.x",
                                    "type": "text",
                                    "text": {"body": "Hi"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    events = list(iter_aisensy_inbound_events(payload))
    assert len(events) == 1
    assert events[0].business_routing_key == "whatsapp:+918000000000"
    assert events[0].customer_phone_e164 == "+9198111222333"
    assert events[0].text == "Hi"

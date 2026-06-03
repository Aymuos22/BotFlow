"""Unit tests for naming helpers (Weaviate + Twilio channel keys)."""
import uuid

import pytest

from app.utils.naming import (
    generate_twilio_channel_key,
    generate_weaviate_collection_name,
    is_valid_weaviate_collection_name,
    rotate_twilio_channel_key,
    sanitize_to_slug,
)

FIXED_UUID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


class TestGenerateWeaviateCollectionName:
    def test_deterministic(self):
        name = generate_weaviate_collection_name(FIXED_UUID)
        assert name.startswith("Co")
        assert generate_weaviate_collection_name(FIXED_UUID) == generate_weaviate_collection_name(
            FIXED_UUID
        )

    def test_accepts_string_uuid(self):
        name = generate_weaviate_collection_name(str(FIXED_UUID))
        assert name.startswith("Co")

    def test_unique_per_company(self):
        names = {generate_weaviate_collection_name(uuid.uuid4()) for _ in range(20)}
        assert len(names) == 20


class TestGenerateTwilioChannelKey:
    def test_format(self):
        name = generate_twilio_channel_key(FIXED_UUID)
        assert name.startswith("twilio-")
        assert len(name) > len("twilio-")

    def test_deterministic(self):
        assert generate_twilio_channel_key(FIXED_UUID) == generate_twilio_channel_key(FIXED_UUID)


class TestRotateTwilioChannelKey:
    def test_includes_suffix(self):
        k = rotate_twilio_channel_key(FIXED_UUID, suffix="numchg")
        assert k.startswith(generate_twilio_channel_key(FIXED_UUID))


class TestIsValidWeaviateCollectionName:
    def test_valid(self):
        assert is_valid_weaviate_collection_name("CoABC") is True

    def test_invalid_lowercase_start(self):
        assert is_valid_weaviate_collection_name("coABC") is False


class TestSanitizeToSlug:
    def test_basic(self):
        assert sanitize_to_slug("Hello World!") == "hello-world"

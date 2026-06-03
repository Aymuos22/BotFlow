"""GET /api/v1/meta/languages — public language catalog for UIs."""
import pytest


@pytest.mark.asyncio
@pytest.mark.api
async def test_meta_languages_returns_catalog(client):
    r = await client.get("/api/v1/meta/languages")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert isinstance(data, list)
    codes = {row["code"] for row in data}
    assert codes == {"english", "hindi", "hinglish"}
    for row in data:
        assert "label" in row and "description" in row

from types import SimpleNamespace


def test_convert_to_retrieve_items_normalizes_fields(app_module):
    raw_items = [
        {
            "id": "mem-1",
            "content": "Call mom",
            "score": "0.85",
            "metadata": {"layer": "semantic", "type": "explicit"},
            "persona_tags": '["identity", "family"]',
            "emotional_signature": '{"mood": "calm"}',
            "importance": "0.6",
        },
        {
            "id": "mem-2",
            "content": "Quarterly report",
            "score": 0.7,
            "metadata": {
                "layer": "long-term",
                "type": "explicit",
                "persona_tags": ["professional"],
                "emotional_signature": {"mood": "focused"},
                "importance": 0.9,
            },
        },
    ]

    items = app_module._convert_to_retrieve_items(raw_items)

    assert [item.id for item in items] == ["mem-1", "mem-2"]
    assert items[0].persona_tags == ["identity", "family"]
    assert items[0].emotional_signature == {"mood": "calm"}
    assert items[0].importance == 0.6
    assert items[1].persona_tags == ["professional"]
    assert items[1].importance == 0.9
    assert items[1].layer == "long-term"


def test_get_identity_prefers_header_token(app_module, monkeypatch):
    claims = {"sub": "user-1", "email": "user@example.com"}
    monkeypatch.setattr(app_module, "verify_cf_access_token", lambda token: claims)
    monkeypatch.setattr(
        app_module,
        "extract_token_from_headers",
        lambda headers: headers.get("cf-access-jwt-assertion"),
    )

    request = SimpleNamespace(cookies={})
    identity = app_module.get_identity(
        cf_access_jwt_assertion="token-abc", request=request
    )

    assert identity == claims


def test_get_identity_falls_back_to_cookie(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "extract_token_from_headers", lambda headers: None)
    monkeypatch.setattr(
        app_module, "verify_cf_access_token", lambda token: {"sub": "cookie-user"}
    )

    request = SimpleNamespace(cookies={"CF_Authorization": "cookie-token"})
    identity = app_module.get_identity(
        request=request, cf_authorization_cookie="cookie-token"
    )

    assert identity["sub"] == "cookie-user"

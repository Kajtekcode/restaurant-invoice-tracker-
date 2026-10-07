from src.parser import parse_grok_response


def test_valid_json_returns_dict_with_seller_and_ingredients():
    raw = (
        '{"seller": "ABC Sp. z o.o.", '
        '"ingredients": [{"name": "Kukurydza kolby 2,5kg Oerlemans"}]}'
    )
    parsed = parse_grok_response(raw)
    assert isinstance(parsed, dict)
    assert parsed["seller"] == "ABC Sp. z o.o."
    assert parsed["ingredients"][0]["name"] == "Kukurydza kolby 2,5kg Oerlemans"


def test_garbage_string_returns_none():
    assert parse_grok_response("not json at all") is None

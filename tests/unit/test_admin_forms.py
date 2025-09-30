from src.api.main import parse_int_list, parse_optional_float, parse_str_list


def test_parse_optional_float_handles_empty_values():
    assert parse_optional_float(None) is None
    assert parse_optional_float("") is None
    assert parse_optional_float("   ") is None


def test_parse_optional_float_parses_numbers():
    assert parse_optional_float("0.25") == 0.25
    assert parse_optional_float(" 1.0 ") == 1.0


def test_parse_int_list_returns_none_for_empty():
    assert parse_int_list(None) is None
    assert parse_int_list("") is None
    assert parse_int_list(" , ") is None


def test_parse_int_list_parses_values():
    assert parse_int_list("1") == [1]
    assert parse_int_list("2,3, 4") == [2, 3, 4]


def test_parse_str_list_returns_none_for_empty():
    assert parse_str_list(None) is None
    assert parse_str_list("") is None
    assert parse_str_list("\n , ") is None


def test_parse_str_list_splits_on_commas_and_newlines():
    assert parse_str_list("a,b") == ["a", "b"]
    assert parse_str_list("Sticker One\nSticker Two") == ["Sticker One", "Sticker Two"]
    assert parse_str_list("Sticker One,\nSticker Two") == ["Sticker One", "Sticker Two"]

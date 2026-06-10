from pdf_extractor.options import parse_pages_spec


def test_parse_pages_spec_none() -> None:
    assert parse_pages_spec(None) is None
    assert parse_pages_spec("") is None


def test_parse_pages_spec_single_and_range() -> None:
    assert parse_pages_spec("1,3-5,8") == {1, 3, 4, 5, 8}


def test_parse_pages_spec_rejects_zero() -> None:
    try:
        parse_pages_spec("0")
    except ValueError as exc:
        assert "1-based" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

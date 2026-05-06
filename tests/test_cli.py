from crypto_research_agent.cli import build_parser


def test_parser_query_required():
    parser = build_parser()
    args = parser.parse_args(["bitcoin", "ETF"])
    assert args.query == ["bitcoin", "ETF"]


def test_parser_test_mode_flag():
    parser = build_parser()
    args = parser.parse_args(["x", "--test"])
    assert args.test is True


def test_parser_thesis_string():
    parser = build_parser()
    args = parser.parse_args(["x", "--thesis", "my thesis"])
    assert args.thesis == "my thesis"


def test_parser_max_age_int():
    parser = build_parser()
    args = parser.parse_args(["x", "--max-age", "30"])
    assert args.max_age == 30


def test_parser_parallel_default_one():
    parser = build_parser()
    args = parser.parse_args(["x"])
    assert args.parallel == 1

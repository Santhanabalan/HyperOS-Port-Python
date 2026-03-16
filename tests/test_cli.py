import pytest

from src.app.cli import parse_args


def test_parse_args_expands_comma_separated_phases():
    args = parse_args(["--stock", "stock.zip", "--phases", "system,apk", "framework"])

    assert args.phases == ["system", "apk", "framework"]


def test_parse_args_rejects_invalid_phase():
    with pytest.raises(SystemExit):
        parse_args(["--stock", "stock.zip", "--phases", "system,invalid"])

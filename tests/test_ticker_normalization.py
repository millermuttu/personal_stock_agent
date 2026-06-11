import pytest

from backend.models.schemas import AnalysisRequest, normalize_indian_ticker


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("RELIANCE", "RELIANCE.NS"),
        ("reliance", "RELIANCE.NS"),
        ("  tcs  ", "TCS.NS"),
        ("INFY.NS", "INFY.NS"),
        ("infy.ns", "INFY.NS"),
        ("500325.BO", "500325.BO"),
        ("tatamotors.bo", "TATAMOTORS.BO"),
    ],
)
def test_normalize_indian_ticker(raw, expected):
    assert normalize_indian_ticker(raw) == expected


def test_analysis_request_normalizes_to_nse():
    request = AnalysisRequest(ticker="hdfcbank", timeframe="short")
    assert request.ticker == "HDFCBANK.NS"


def test_analysis_request_preserves_explicit_suffix():
    request = AnalysisRequest(ticker="reliance.bo", timeframe="long")
    assert request.ticker == "RELIANCE.BO"

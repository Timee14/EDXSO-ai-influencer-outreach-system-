"""
Unit tests for the influencer filtering module.
"""

import pytest
import numpy as np
import pandas as pd
from src.filter import evaluate_influencer, filter_influencers, is_valid_email, is_valid_niche


@pytest.fixture
def valid_influencer_row():
    """Returns a valid micro-influencer profile meeting all criteria."""
    return pd.Series({
        "Channel Name": "STEM Lab for Kids",
        "URL": "https://www.youtube.com/channel/UC12345",
        "Subscriber Count": 25000,
        "Estimated Engagement Rate (%)": 4.8,
        "Recent Video Title": "Fun Science Experiments at Home",
        "Email": "contact@stemlabkids.com",
        "Niche": "STEM"
    })


def test_valid_influencer_passes(valid_influencer_row):
    """Test that a fully qualified influencer passes evaluation."""
    result = evaluate_influencer(valid_influencer_row)
    assert result["Status"] == "Pass"
    assert result["Reason"] == "Qualified"


@pytest.mark.parametrize("niche", ["Education", "STEM", "Parenting", "EdTech", "Study Tips"])
def test_valid_niches_pass(valid_influencer_row, niche):
    """Test that all acceptable niche categories pass."""
    row = valid_influencer_row.copy()
    row["Niche"] = niche
    result = evaluate_influencer(row)
    assert result["Status"] == "Pass"


def test_macro_influencer_fails(valid_influencer_row):
    """Test that channels with >= 100,000 subscribers fail."""
    row = valid_influencer_row.copy()
    row["Subscriber Count"] = 150000
    result = evaluate_influencer(row)
    assert result["Status"] == "Fail"
    assert "Subscriber count too high" in result["Reason"]


def test_nano_influencer_fails(valid_influencer_row):
    """Test that channels with <= 5,000 subscribers fail (lower bound)."""
    row = valid_influencer_row.copy()
    row["Subscriber Count"] = 4500
    result = evaluate_influencer(row)
    assert result["Status"] == "Fail"
    assert "Subscriber count too low" in result["Reason"]


def test_boundary_subscriber_counts(valid_influencer_row):
    """Test exact boundary subscriber counts (5,000 and 100,000 are not strictly between)."""
    row_low = valid_influencer_row.copy()
    row_low["Subscriber Count"] = 5000
    res_low = evaluate_influencer(row_low)
    assert res_low["Status"] == "Fail"
    assert "Subscriber count too low" in res_low["Reason"]

    row_high = valid_influencer_row.copy()
    row_high["Subscriber Count"] = 100000
    res_high = evaluate_influencer(row_high)
    assert res_high["Status"] == "Fail"
    assert "Subscriber count too high" in res_high["Reason"]


def test_low_engagement_fails(valid_influencer_row):
    """Test that engagement rate < 2.5% fails."""
    row = valid_influencer_row.copy()
    row["Estimated Engagement Rate (%)"] = 1.8
    result = evaluate_influencer(row)
    assert result["Status"] == "Fail"
    assert "Low engagement" in result["Reason"]


@pytest.mark.parametrize("missing_email", ["Not Found", "NOT FOUND", "", "   ", None, np.nan])
def test_missing_email_fails(valid_influencer_row, missing_email):
    """Test various representations of missing or invalid emails."""
    row = valid_influencer_row.copy()
    row["Email"] = missing_email
    result = evaluate_influencer(row)
    assert result["Status"] == "Fail"
    assert "Email missing" in result["Reason"]


@pytest.mark.parametrize("invalid_niche", ["Gaming", "Crypto Trading", "Beauty & Makeup", "Automotive", None, np.nan])
def test_invalid_niche_fails(valid_influencer_row, invalid_niche):
    """Test that unrelated niches fail."""
    row = valid_influencer_row.copy()
    row["Niche"] = invalid_niche
    result = evaluate_influencer(row)
    assert result["Status"] == "Fail"
    assert "Invalid niche" in result["Reason"]


def test_multiple_simultaneous_failures():
    """Test an influencer profile that triggers all failure conditions at once."""
    bad_row = pd.Series({
        "Subscriber Count": 250000,          # Macro (>100k)
        "Estimated Engagement Rate (%)": 0.8, # Low engagement (<2.5%)
        "Email": "Not Found",                # Missing email
        "Niche": "Crypto Trading"            # Invalid niche
    })
    result = evaluate_influencer(bad_row)
    assert result["Status"] == "Fail"
    reason = result["Reason"]
    assert "Subscriber count too high" in reason
    assert "Low engagement" in reason
    assert "Email missing" in reason
    assert "Invalid niche" in reason
    # Verify separator
    assert " | " in reason


def test_filter_influencers_dataframe():
    """Test batch DataFrame filtering."""
    df = pd.DataFrame([
        {
            "Channel Name": "Pass Channel",
            "Subscriber Count": 20000,
            "Estimated Engagement Rate (%)": 3.5,
            "Email": "test@edxso.com",
            "Niche": "Education"
        },
        {
            "Channel Name": "Fail Channel",
            "Subscriber Count": 2000,
            "Estimated Engagement Rate (%)": 1.0,
            "Email": "Not Found",
            "Niche": "Gaming"
        }
    ])
    filtered = filter_influencers(df)
    assert len(filtered) == 2
    assert filtered.iloc[0]["Status"] == "Pass"
    assert filtered.iloc[0]["Reason"] == "Qualified"
    assert filtered.iloc[1]["Status"] == "Fail"
    assert "Subscriber count too low" in filtered.iloc[1]["Reason"]

"""
Unit tests for the AI personalization engine.
"""

import json
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from openai import OpenAIError
from src.ai_generator import generate_outreach, batch_generate_outreach, get_openai_client


@pytest.fixture
def sample_influencer_row():
    return pd.Series({
        "Channel Name": "Study With Sarah",
        "Recent Video Title": "Top 5 Note Taking Apps for 2026",
        "Niche": "Education",
        "Status": "Pass"
    })


def test_missing_api_key_raises_value_error():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="OpenAI API key not found"):
            get_openai_client(api_key=None)


def test_generate_outreach_success(sample_influencer_row):
    """Test successful generation and JSON parsing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    
    expected_email = (
        "Hi Sarah, loved your breakdown in 'Top 5 Note Taking Apps for 2026'! "
        "At EDXSO, we've built an all-in-one digital learning platform that helps students streamline their study workflow. "
        "We would love to sponsor a dedicated UGC integration in your upcoming video. "
        "Let me know if you're open to discussing rates and details!"
    )
    expected_dm = "Hey Sarah! Loved your note-taking video. Would love to collaborate on a paid partnership for EDXSO. Let me know if interested!"

    mock_choice.message.content = json.dumps({
        "email_pitch": expected_email,
        "instagram_dm": expected_dm
    })
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    result = generate_outreach(sample_influencer_row, client=mock_client)

    assert isinstance(result, pd.Series)
    assert result["Generated_Email"] == expected_email
    assert result["Generated_DM"] == expected_dm

    # Verify model and json_object format were passed
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["response_format"] == {"type": "json_object"}


def test_generate_outreach_handles_api_error(sample_influencer_row):
    """Test graceful error handling on OpenAI API error."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = OpenAIError("Rate limit exceeded")

    result = generate_outreach(sample_influencer_row, client=mock_client)

    assert "ERROR" in result["Generated_Email"]
    assert "ERROR" in result["Generated_DM"]


def test_generate_outreach_handles_invalid_json(sample_influencer_row):
    """Test fallback when response contains malformed JSON."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Not a JSON response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    result = generate_outreach(sample_influencer_row, client=mock_client)

    assert "ERROR" in result["Generated_Email"]
    assert "ERROR" in result["Generated_DM"]


def test_batch_generate_outreach_respects_status():
    """Test that batch generation skips disqualified rows when only_passed=True."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "email_pitch": "Sample Email",
        "instagram_dm": "Sample DM"
    })
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    df = pd.DataFrame([
        {
            "Channel Name": "Pass Channel",
            "Recent Video Title": "Learn Python",
            "Niche": "STEM",
            "Status": "Pass"
        },
        {
            "Channel Name": "Fail Channel",
            "Recent Video Title": "Gaming Highlights",
            "Niche": "Gaming",
            "Status": "Fail"
        }
    ])

    result_df = batch_generate_outreach(df, client=mock_client, only_passed=True)

    assert len(result_df) == 2
    assert result_df.iloc[0]["Generated_Email"] == "Sample Email"
    assert result_df.iloc[0]["Generated_DM"] == "Sample DM"
    assert result_df.iloc[1]["Generated_Email"] == "N/A - Disqualified"
    assert result_df.iloc[1]["Generated_DM"] == "N/A - Disqualified"

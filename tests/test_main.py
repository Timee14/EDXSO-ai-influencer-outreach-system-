"""
Unit tests for the end-to-end pipeline orchestrator.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from main import run_pipeline


@pytest.fixture
def mock_pipeline_data():
    return pd.DataFrame([
        {
            "Channel Name": "Physics Kids",
            "URL": "https://youtube.com/c/physicskids",
            "Subscriber Count": 30000,
            "Estimated Engagement Rate (%)": 4.5,
            "Recent Video Title": "Electromagnetism in 10 Minutes",
            "Email": "physics@kidslearning.org",
            "Niche": "STEM"
        }
    ])


def test_run_pipeline_end_to_end(tmp_path, mock_pipeline_data):
    raw_csv = tmp_path / "raw_influencers.csv"
    mock_pipeline_data.to_csv(raw_csv, index=False)

    tracker_csv = tmp_path / "edxso_outreach_tracker.csv"

    with patch("src.tracker.OutreachTracker.DEFAULT_TRACKER_PATH", str(tracker_csv)):
        with patch("src.ai_generator.generate_outreach") as mock_ai:
            mock_ai.return_value = pd.Series({
                "Generated_Email": "Hi! Let's collaborate with EDXSO.",
                "Generated_DM": "Hey! EDXSO collab?"
            })

            tracker_result = run_pipeline(
                raw_data_path=str(raw_csv),
                force_discovery=False,
                dry_run=True
            )

            assert not tracker_result.empty
            assert len(tracker_result) == 1
            assert tracker_result.iloc[0]["Channel Name"] == "Physics Kids"
            assert tracker_result.iloc[0]["Send_Status"] == "Sent"

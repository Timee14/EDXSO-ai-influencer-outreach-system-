"""
Unit tests for the discovery module.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from src.discovery import extract_email, YouTubeDiscoveryClient, discover_influencers


def test_extract_email():
    # Valid emails in various texts
    assert extract_email("Contact me at creator@example.com for sponsorships.") == "creator@example.com"
    assert extract_email("Business inquiries: collab.partner+edxso@gmail.com") == "collab.partner+edxso@gmail.com"
    assert extract_email("hello.world@sub.domain.co.uk!") == "hello.world@sub.domain.co.uk"
    
    # Text without email
    assert extract_email("Subscribe to my channel for more study tips!") is None
    assert extract_email("") is None
    assert extract_email(None) is None


def test_missing_api_key_raises_value_error():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="YouTube API key not found"):
            YouTubeDiscoveryClient(api_key=None)


def test_engagement_rate_and_dataframe_generation(tmp_path):
    # Mock YouTube client behavior
    mock_service = MagicMock()
    
    # Mock channel details response
    mock_channels = mock_service.channels().list().execute
    mock_channels.return_value = {
        "items": [
            {
                "id": "UC123456",
                "snippet": {
                    "title": "Study Hacks 101",
                    "description": "Welcome to my channel! Inquiries: study@edxso.com"
                },
                "statistics": {
                    "subscriberCount": "10000",
                    "hiddenSubscriberCount": False
                },
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": "UU123456"
                    }
                }
            }
        ]
    }

    # Mock playlist items response
    mock_playlist_items = mock_service.playlistItems().list().execute
    mock_playlist_items.return_value = {
        "items": [
            {
                "snippet": {"title": "10 Productivity Tools for Students"},
                "contentDetails": {"videoId": "vid123"}
            }
        ]
    }

    # Mock video statistics response (Avg views = 2000 => Engagement Rate = (2000/10000)*100 = 20.0%)
    mock_videos = mock_service.videos().list().execute
    mock_videos.return_value = {
        "items": [
            {"statistics": {"viewCount": "2000"}}
        ]
    }

    with patch("src.discovery.build", return_value=mock_service):
        client = YouTubeDiscoveryClient(api_key="fake_key")
        records = client.fetch_channel_data(["UC123456"])
        
        assert len(records) == 1
        record = records[0]
        assert record["Channel Name"] == "Study Hacks 101"
        assert record["URL"] == "https://www.youtube.com/channel/UC123456"
        assert record["Subscriber Count"] == 10000
        assert record["Estimated Engagement Rate (%)"] == 20.0
        assert record["Recent Video Title"] == "10 Productivity Tools for Students"
        assert record["Email"] == "study@edxso.com"

        # Verify DataFrame generation and CSV export
        csv_path = tmp_path / "raw_influencers.csv"
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False)
        
        assert csv_path.exists()
        loaded_df = pd.read_csv(csv_path)
        assert len(loaded_df) == 1
        assert "Estimated Engagement Rate (%)" in loaded_df.columns

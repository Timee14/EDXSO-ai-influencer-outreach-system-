"""
Unit tests for the outreach sending and tracking layer.
"""

import smtplib
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from src.tracker import OutreachTracker


@pytest.fixture
def sample_qualified_df():
    return pd.DataFrame([
        {
            "Channel Name": "Physics Explorer",
            "Email": "creator1@physics.edu",
            "URL": "https://youtube.com/c/physics1",
            "Recent Video Title": "Quantum Computing 101",
            "Generated_Email": "Hi Physics Explorer, let's collaborate with EDXSO!",
            "Generated_DM": "Hey, love your quantum video! EDXSO collab?",
            "Status": "Pass"
        },
        {
            "Channel Name": "Math Prodigy",
            "Email": "creator2@math.org",
            "URL": "https://youtube.com/c/math2",
            "Recent Video Title": "Calculus Made Easy",
            "Generated_Email": "Hi Math Prodigy, let's collaborate with EDXSO!",
            "Generated_DM": "Hey, love your calculus video! EDXSO collab?",
            "Status": "Pass"
        }
    ])


def test_tracker_initialization_empty_file(tmp_path):
    tracker_file = tmp_path / "edxso_outreach_tracker.csv"
    tracker = OutreachTracker(tracker_path=str(tracker_file))
    assert len(tracker.sent_emails) == 0
    assert tracker.tracker_df.empty


def test_tracker_initialization_existing_file(tmp_path):
    tracker_file = tmp_path / "edxso_outreach_tracker.csv"
    existing_df = pd.DataFrame([
        {
            "Channel Name": "Old Creator",
            "Email": "old_creator@example.com",
            "Send_Status": "Sent"
        },
        {
            "Channel Name": "Failed Creator",
            "Email": "failed@example.com",
            "Send_Status": "Failed"
        }
    ])
    existing_df.to_csv(tracker_file, index=False)

    tracker = OutreachTracker(tracker_path=str(tracker_file))
    assert "old_creator@example.com" in tracker.sent_emails
    assert "failed@example.com" not in tracker.sent_emails
    assert len(tracker.sent_emails) == 1


def test_send_actual_email_missing_credentials(monkeypatch):
    monkeypatch.delenv("SENDER_EMAIL", raising=False)
    monkeypatch.delenv("SENDER_PASSWORD", raising=False)

    tracker = OutreachTracker()
    success = tracker.send_actual_email(
        recipient="test@example.com",
        name="Test Creator",
        body="Hello!"
    )
    assert success is False


def test_send_actual_email_success(monkeypatch):
    monkeypatch.setenv("SENDER_EMAIL", "partner@edxso.com")
    monkeypatch.setenv("SENDER_PASSWORD", "mock_app_password")

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP_SSL", return_value=mock_smtp_instance) as mock_smtp_class:
        mock_smtp_instance.__enter__.return_value = mock_smtp_instance

        tracker = OutreachTracker()
        success = tracker.send_actual_email(
            recipient="creator@example.com",
            name="Science Kid",
            body="Hello Science Kid!"
        )

        assert success is True
        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 465)
        mock_smtp_instance.login.assert_called_once_with("partner@edxso.com", "mock_app_password")
        mock_smtp_instance.sendmail.assert_called_once()


def test_send_actual_email_smtp_failure(monkeypatch):
    monkeypatch.setenv("SENDER_EMAIL", "partner@edxso.com")
    monkeypatch.setenv("SENDER_PASSWORD", "mock_app_password")

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP_SSL", return_value=mock_smtp_instance):
        mock_smtp_instance.__enter__.return_value = mock_smtp_instance
        mock_smtp_instance.sendmail.side_effect = smtplib.SMTPException("Authentication failed")

        tracker = OutreachTracker()
        success = tracker.send_actual_email(
            recipient="creator@example.com",
            name="Science Kid",
            body="Hello!"
        )
        assert success is False


def test_log_and_send_with_duplicate_prevention(tmp_path, sample_qualified_df, monkeypatch):
    tracker_file = tmp_path / "edxso_outreach_tracker.csv"
    monkeypatch.setenv("SENDER_EMAIL", "partner@edxso.com")
    monkeypatch.setenv("SENDER_PASSWORD", "mock_password")

    # Pre-populate tracker with creator1
    pre_df = pd.DataFrame([
        {
            "Channel Name": "Physics Explorer",
            "Email": "creator1@physics.edu",
            "Send_Status": "Sent"
        }
    ])
    pre_df.to_csv(tracker_file, index=False)

    with patch.object(OutreachTracker, "send_actual_email", return_value=True) as mock_send:
        tracker = OutreachTracker(tracker_path=str(tracker_file))
        assert "creator1@physics.edu" in tracker.sent_emails

        updated_df = tracker.log_and_send(sample_qualified_df)

        # creator1 should be skipped as duplicate; creator2 should be sent
        mock_send.assert_called_once_with(
            recipient="creator2@math.org",
            name="Math Prodigy",
            body="Hi Math Prodigy, let's collaborate with EDXSO!"
        )

        assert "creator2@math.org" in tracker.sent_emails
        assert tracker_file.exists()

        # Check saved CSV records
        saved_csv = pd.read_csv(tracker_file)
        assert len(saved_csv) == 3  # 1 old + 1 duplicate skipped log + 1 newly sent log
        duplicate_entry = saved_csv[saved_csv["Email"] == "creator1@physics.edu"].iloc[-1]
        assert duplicate_entry["Send_Status"] == "Skipped - Duplicate"

        new_entry = saved_csv[saved_csv["Email"] == "creator2@math.org"].iloc[0]
        assert new_entry["Send_Status"] == "Sent"
        assert pd.notna(new_entry["Timestamp"])

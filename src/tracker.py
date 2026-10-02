"""
EDXSO Outreach Sending & Tracking Layer
---------------------------------------
Implements duplicate-prevention tracking and real SMTP email dispatch via Gmail SSL (Port 465).
Persists outreach logs to outputs/edxso_outreach_tracker.csv.
"""

import os
import smtplib
import logging
from datetime import datetime, timezone
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Set
from dotenv import load_dotenv
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class OutreachTracker:
    """Manages duplicate prevention, outbound SMTP email dispatch, and campaign logging."""

    DEFAULT_TRACKER_PATH = "outputs/edxso_outreach_tracker.csv"
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 465

    def __init__(self, tracker_path: Optional[str] = None):
        """
        Initializes the OutreachTracker and builds the set of previously sent emails.

        Args:
            tracker_path: Custom path to tracker CSV. Defaults to outputs/edxso_outreach_tracker.csv.
        """
        self.tracker_path = Path(tracker_path or self.DEFAULT_TRACKER_PATH)
        self.sent_emails: Set[str] = set()
        self.tracker_df = self._load_tracker()

    def _load_tracker(self) -> pd.DataFrame:
        """
        Loads existing tracker CSV if present and builds the set of previously sent emails.

        Returns:
            Pandas DataFrame of tracker records.
        """
        if self.tracker_path.exists():
            try:
                df = pd.read_csv(self.tracker_path)
                if "Email" in df.columns:
                    # Collect successfully sent emails (or all recorded emails with Status == 'Sent')
                    if "Send_Status" in df.columns:
                        sent_mask = df["Send_Status"].str.lower() == "sent"
                        emails = df.loc[sent_mask, "Email"].dropna().str.strip().str.lower()
                    else:
                        emails = df["Email"].dropna().str.strip().str.lower()
                    self.sent_emails = set(emails)
                logger.info(
                    "Loaded %d existing records from %s (%d previously sent emails).",
                    len(df), self.tracker_path, len(self.sent_emails)
                )
                return df
            except Exception as e:
                logger.warning("Failed to parse existing tracker file at %s: %s. Initializing new tracker.", self.tracker_path, e)

        # Initialize new empty DataFrame schema
        return pd.DataFrame(columns=[
            "Channel Name", "Email", "URL", "Recent Video Title",
            "Generated_Email", "Generated_DM", "Send_Status", "Timestamp", "Error_Message"
        ])

    def send_actual_email(
        self,
        recipient: str,
        name: str,
        body: str,
        subject: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None
    ) -> bool:
        """
        Sends an email using smtplib and email.mime over SSL (smtp.gmail.com:465).

        Args:
            recipient: Target recipient email address.
            name: Influencer / Channel name.
            body: Personalized outreach email body.
            subject: Email subject line.
            sender_email: Sender's Gmail address (defaults to SENDER_EMAIL env var).
            sender_password: Sender's Gmail app password (defaults to SENDER_PASSWORD env var).

        Returns:
            True if sent successfully, False otherwise.
        """
        email_from = sender_email or os.getenv("SENDER_EMAIL")
        email_password = sender_password or os.getenv("SENDER_PASSWORD")

        if not email_from or not email_password:
            logger.error("Missing SENDER_EMAIL or SENDER_PASSWORD in environment variables.")
            return False

        if not recipient or "@" not in recipient:
            logger.error("Invalid recipient email address: '%s'", recipient)
            return False

        email_subject = subject or f"Collaboration with EDXSO x {name}"

        # Build MIME Message
        message = MIMEMultipart("alternative")
        message["Subject"] = email_subject
        message["From"] = f"EDXSO Partnerships <{email_from}>"
        message["To"] = recipient

        # Attach plain text body
        text_part = MIMEText(body, "plain", "utf-8")
        message.attach(text_part)

        try:
            with smtplib.SMTP_SSL(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.login(email_from, email_password)
                server.sendmail(email_from, [recipient], message.as_string())

            logger.info("Successfully sent email to %s (%s)", name, recipient)
            return True

        except smtplib.SMTPException as e:
            logger.error("SMTP error sending email to %s (%s): %s", name, recipient, e)
            return False
        except Exception as e:
            logger.error("Unexpected error sending email to %s (%s): %s", name, recipient, e)
            return False

    def log_and_send(
        self,
        qualified_df: pd.DataFrame,
        dry_run: bool = False
    ) -> pd.DataFrame:
        """
        Iterates over qualified influencers, dispatches emails (skipping duplicates),
        logs timestamps and statuses, and saves back to tracker CSV.

        Args:
            qualified_df: DataFrame containing qualified influencers with email bodies.
            dry_run: If True, simulates sending without calling SMTP server.

        Returns:
            Updated tracker DataFrame.
        """
        if qualified_df.empty:
            logger.info("No records provided to log_and_send.")
            return self.tracker_df

        new_entries = []

        for _, row in qualified_df.iterrows():
            # If row has Status column, process only Passed influencers
            status = row.get("Status", "Pass")
            if status != "Pass":
                continue

            channel_name = row.get("Channel Name", "Creator")
            raw_email = str(row.get("Email", "")).strip()
            normalized_email = raw_email.lower()
            url = row.get("URL", "")
            recent_video = row.get("Recent Video Title", "")
            generated_email = row.get("Generated_Email", "")
            generated_dm = row.get("Generated_DM", "")

            # 1. Duplicate Check
            if not raw_email or normalized_email in {"not found", "nan", "none", ""}:
                send_status = "Skipped - Missing Email"
                err_msg = "No valid email address found in profile"
            elif normalized_email in self.sent_emails:
                logger.info("Skipping duplicate email for %s (%s)", channel_name, raw_email)
                send_status = "Skipped - Duplicate"
                err_msg = "Email was already contacted previously"
            else:
                # 2. Dispatch Email
                if dry_run:
                    logger.info("[DRY RUN] Simulating email dispatch to %s (%s)", channel_name, raw_email)
                    success = True
                    err_msg = ""
                else:
                    success = self.send_actual_email(
                        recipient=raw_email,
                        name=channel_name,
                        body=generated_email
                    )
                    err_msg = "" if success else "SMTP transmission failed"

                if success:
                    send_status = "Sent"
                    self.sent_emails.add(normalized_email)
                else:
                    send_status = "Failed"

            timestamp = datetime.now(timezone.utc).isoformat()

            new_entries.append({
                "Channel Name": channel_name,
                "Email": raw_email,
                "URL": url,
                "Recent Video Title": recent_video,
                "Generated_Email": generated_email,
                "Generated_DM": generated_dm,
                "Send_Status": send_status,
                "Timestamp": timestamp,
                "Error_Message": err_msg
            })

        if new_entries:
            new_df = pd.DataFrame(new_entries)
            self.tracker_df = pd.concat([self.tracker_df, new_df], ignore_index=True)

            # Ensure parent output directory exists and save CSV
            self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
            self.tracker_df.to_csv(self.tracker_path, index=False, encoding="utf-8")
            logger.info("Updated tracker saved with %d total records at %s", len(self.tracker_df), self.tracker_path)

        return self.tracker_df

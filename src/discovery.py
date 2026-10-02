"""
EDXSO Influencer Discovery Module
----------------------------------
Searches for micro-influencers in the EdTech/Study niche using the YouTube Data API v3,
extracts channel metrics (subscribers, engagement rate, recent video, email),
and saves the dataset to data/raw_influencers.csv.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Regular expression pattern to extract email addresses
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def extract_email(text: Optional[str]) -> Optional[str]:
    """
    Extracts the first valid email address from a given text string using regex.

    Args:
        text: Input string (e.g., channel description or video description).

    Returns:
        Extracted email string, or None if no valid email is found.
    """
    if not text:
        return None
    matches = EMAIL_REGEX.findall(text)
    if matches:
        # Strip trailing punctuation if any matched improperly
        email = matches[0].strip(".,;:()")
        return email
    return None


class YouTubeDiscoveryClient:
    """Client for querying YouTube Data API v3 to discover niche creators."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the YouTube client.

        Args:
            api_key: YouTube Data API v3 key. If omitted, fetched from YOUTUBE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "YouTube API key not found. Please set YOUTUBE_API_KEY in your .env file."
            )
        self.youtube = build("youtube", "v3", developerKey=self.api_key)

    def search_channels(
        self,
        queries: List[str],
        target_count: int = 50
    ) -> List[str]:
        """
        Searches for unique channel IDs across multiple search terms.

        Args:
            queries: List of search query strings (e.g. ['edtech tools', 'study tips']).
            target_count: Maximum number of unique channel IDs to collect.

        Returns:
            List of unique channel IDs.
        """
        discovered_channel_ids = set()

        for query in queries:
            if len(discovered_channel_ids) >= target_count:
                break

            logger.info("Searching for query: '%s'", query)
            page_token = None

            while len(discovered_channel_ids) < target_count:
                try:
                    response = self.youtube.search().list(
                        q=query,
                        type="channel",
                        part="id,snippet",
                        maxResults=min(50, target_count - len(discovered_channel_ids)),
                        pageToken=page_token
                    ).execute()

                    items = response.get("items", [])
                    if not items:
                        break

                    for item in items:
                        channel_id = item.get("id", {}).get("channelId")
                        if channel_id:
                            discovered_channel_ids.add(channel_id)

                    page_token = response.get("nextPageToken")
                    if not page_token:
                        break

                except HttpError as e:
                    logger.error("HTTP error during search for query '%s': %s", query, e)
                    break

        channel_list = list(discovered_channel_ids)[:target_count]
        logger.info("Discovered %d unique channels.", len(channel_list))
        return channel_list

    def get_recent_video_details(
        self,
        uploads_playlist_id: str,
        max_videos: int = 5
    ) -> tuple[Optional[str], List[int]]:
        """
        Fetches the most recent video title and view counts of recent videos for a channel.

        Args:
            uploads_playlist_id: ID of the channel's uploads playlist.
            max_videos: Number of recent videos to sample for average views.

        Returns:
            Tuple of (recent_video_title, list_of_view_counts).
        """
        if not uploads_playlist_id:
            return None, []

        try:
            playlist_items = self.youtube.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="snippet,contentDetails",
                maxResults=max_videos
            ).execute().get("items", [])

            if not playlist_items:
                return None, []

            recent_video_title = playlist_items[0]["snippet"].get("title")
            video_ids = [
                item["contentDetails"]["videoId"]
                for item in playlist_items
                if "contentDetails" in item and "videoId" in item["contentDetails"]
            ]

            if not video_ids:
                return recent_video_title, []

            video_response = self.youtube.videos().list(
                id=",".join(video_ids),
                part="statistics"
            ).execute().get("items", [])

            views = [
                int(v.get("statistics", {}).get("viewCount", 0))
                for v in video_response
            ]
            return recent_video_title, views

        except HttpError as e:
            logger.warning("Error fetching recent videos for playlist %s: %s", uploads_playlist_id, e)
            return None, []

    def fetch_channel_data(self, channel_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieves detailed metadata, statistics, recent videos, and contact info for channels.

        Args:
            channel_ids: List of channel IDs to query.

        Returns:
            List of dictionaries containing formatted influencer data.
        """
        influencer_data: List[Dict[str, Any]] = []

        # Batch channel details queries in chunks of 50 (YouTube API limit)
        for i in range(0, len(channel_ids), 50):
            batch_ids = channel_ids[i:i + 50]
            try:
                response = self.youtube.channels().list(
                    id=",".join(batch_ids),
                    part="snippet,statistics,contentDetails"
                ).execute()

                for item in response.get("items", []):
                    ch_id = item.get("id")
                    snippet = item.get("snippet", {})
                    statistics = item.get("statistics", {})
                    content_details = item.get("contentDetails", {})

                    channel_name = snippet.get("title", "Unknown")
                    description = snippet.get("description", "")
                    channel_url = f"https://www.youtube.com/channel/{ch_id}"

                    # Subscriber count
                    subscribers = int(statistics.get("subscriberCount", 0)) if not statistics.get("hiddenSubscriberCount", False) else 0

                    # Fetch recent video details & view counts
                    uploads_playlist_id = content_details.get("relatedPlaylists", {}).get("uploads")
                    recent_title, recent_views = self.get_recent_video_details(uploads_playlist_id, max_videos=5)

                    # Calculate Estimated Engagement Rate: ((Avg Views / Subscribers) * 100)
                    if subscribers > 0 and recent_views:
                        avg_views = sum(recent_views) / len(recent_views)
                        engagement_rate = round((avg_views / subscribers) * 100, 2)
                    else:
                        engagement_rate = 0.0

                    # Extract email from channel description
                    extracted_email = extract_email(description)

                    influencer_data.append({
                        "Channel Name": channel_name,
                        "URL": channel_url,
                        "Subscriber Count": subscribers,
                        "Estimated Engagement Rate (%)": engagement_rate,
                        "Recent Video Title": recent_title or "N/A",
                        "Email": extracted_email or "Not Found"
                    })

            except HttpError as e:
                logger.error("HTTP error fetching channel details: %s", e)

        return influencer_data


def discover_influencers(
    queries: Optional[List[str]] = None,
    target_count: int = 50,
    output_path: str = "data/raw_influencers.csv"
) -> pd.DataFrame:
    """
    Main pipeline function to discover influencers and save results.

    Args:
        queries: Search queries for niche targeting.
        target_count: Target number of influencer channels.
        output_path: Path to save the resulting CSV file.

    Returns:
        Pandas DataFrame of discovered influencers.
    """
    if queries is None:
        queries = ["edtech tools", "study tips", "study with me", "edtech tutorials", "student productivity"]

    client = YouTubeDiscoveryClient()
    channel_ids = client.search_channels(queries=queries, target_count=target_count)

    if not channel_ids:
        logger.warning("No channels found. Creating an empty DataFrame.")
        df = pd.DataFrame(columns=[
            "Channel Name", "URL", "Subscriber Count",
            "Estimated Engagement Rate (%)", "Recent Video Title", "Email"
        ])
    else:
        records = client.fetch_channel_data(channel_ids)
        df = pd.DataFrame(records)

    # Ensure output directory exists
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_file, index=False, encoding="utf-8")
    logger.info("Saved %d records to %s", len(df), out_file.resolve())
    return df


if __name__ == "__main__":
    discover_influencers()

"""
EDXSO AI Personalization Engine
--------------------------------
Generates hyper-personalized outreach content (Email Pitch & Instagram DM)
for qualified micro-influencers using OpenAI's gpt-4o-mini model.
"""

import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv
import pandas as pd
from openai import OpenAI, OpenAIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    """
    Initializes and returns the OpenAI client.

    Args:
        api_key: Optional explicit API key. Defaults to OPENAI_API_KEY environment variable.

    Returns:
        Configured OpenAI client instance.
    """
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")
    return OpenAI(api_key=key)


def generate_outreach(
    row: pd.Series,
    client: Optional[OpenAI] = None,
    model: str = "gpt-4o-mini"
) -> pd.Series:
    """
    Generates personalized Email and Instagram DM outreach copies for a qualified influencer.

    Args:
        row: Pandas Series with influencer details (e.g. Channel Name, Recent Video Title, Niche).
        client: Optional OpenAI client instance.
        model: Model name to use (default: gpt-4o-mini).

    Returns:
        Pandas Series with index ['Generated_Email', 'Generated_DM'].
    """
    channel_name = row.get("Channel Name") or row.get("channel_name") or "Creator"
    recent_video = row.get("Recent Video Title") or row.get("recent_video_title") or "your recent content"
    niche = row.get("Niche") or row.get("niche") or "EdTech/Learning"

    system_prompt = (
        "You are an expert influencer marketing manager at EDXSO, an innovative digital learning platform. "
        "Your goal is to craft high-converting, personalized outreach messages for micro-influencer partnerships.\n"
        "You must respond strictly in valid JSON format with two keys: 'email_pitch' and 'instagram_dm'."
    )

    user_prompt = f"""Influencer Details:
- Channel Name: {channel_name}
- Niche: {niche}
- Recent Video Title: "{recent_video}"

Instructions:
1. Email Pitch (Strictly 60-90 words):
   - Propose a paid UGC (user-generated content) collaboration for EDXSO's digital learning platform.
   - Naturally reference their recent video title "{recent_video}" to demonstrate genuine interest.
   - Professional, value-driven tone with a clear call-to-action to connect.

2. Instagram DM (Strictly 15-30 words):
   - Casual, direct, and concise outreach mentioning a potential paid collaboration with EDXSO.

Respond with JSON format:
{{
  "email_pitch": "<email pitch text>",
  "instagram_dm": "<instagram dm text>"
}}"""

    try:
        if client is None:
            client = get_openai_client()

        response = client.chat.completions.create(
            model=model,
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw_content = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_content)

        generated_email = parsed.get("email_pitch", "").strip()
        generated_dm = parsed.get("instagram_dm", "").strip()

        if not generated_email or not generated_dm:
            raise ValueError("Incomplete response received from LLM.")

        return pd.Series({
            "Generated_Email": generated_email,
            "Generated_DM": generated_dm
        })

    except (OpenAIError, ValueError, json.JSONDecodeError, KeyError) as e:
        logger.error("Error generating outreach for '%s': %s", channel_name, e)
        return pd.Series({
            "Generated_Email": f"ERROR: Failed to generate email ({type(e).__name__})",
            "Generated_DM": f"ERROR: Failed to generate DM ({type(e).__name__})"
        })


def batch_generate_outreach(
    df: pd.DataFrame,
    client: Optional[OpenAI] = None,
    only_passed: bool = True
) -> pd.DataFrame:
    """
    Generates outreach messages for qualified rows in a DataFrame.

    Args:
        df: DataFrame containing influencer data.
        client: Optional OpenAI client instance.
        only_passed: If True, only generates for rows where Status == 'Pass'.

    Returns:
        DataFrame with added 'Generated_Email' and 'Generated_DM' columns.
    """
    if df.empty:
        return df.assign(
            Generated_Email=pd.Series(dtype="str"),
            Generated_DM=pd.Series(dtype="str")
        )

    result_df = df.copy()
    generated_emails = []
    generated_dms = []

    for _, row in result_df.iterrows():
        status = row.get("Status", "Pass")
        if only_passed and status != "Pass":
            generated_emails.append("N/A - Disqualified")
            generated_dms.append("N/A - Disqualified")
        else:
            outreach = generate_outreach(row, client=client)
            generated_emails.append(outreach["Generated_Email"])
            generated_dms.append(outreach["Generated_DM"])

    result_df["Generated_Email"] = generated_emails
    result_df["Generated_DM"] = generated_dms
    return result_df

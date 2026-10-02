"""
EDXSO Influencer Filtering Module
----------------------------------
Evaluates discovered influencers against EDXSO micro-influencer qualification criteria:
1. Follower/Subscriber Count: Strictly between 5,000 and 100,000.
2. Engagement Rate: >= 2.5%.
3. Email: Must be present, non-empty, and not "Not Found".
4. Niche: Must be related to Education, STEM, or Parenting.
"""

from typing import Any, List, Optional
import math
import pandas as pd

# Target niches allowed for EDXSO outreach
VALID_NICHES = {"education", "stem", "parenting", "edtech", "study", "learning", "science", "technology"}


def is_valid_email(email: Any) -> bool:
    """Checks if an email is present and valid."""
    if email is None:
        return False
    if isinstance(email, float) and math.isnan(email):
        return False
    email_str = str(email).strip()
    if not email_str or email_str.lower() in {"not found", "none", "nan", "null", "n/a"}:
        return False
    return "@" in email_str


def is_valid_niche(niche: Any) -> bool:
    """Checks if the niche matches Education, STEM, or Parenting domains."""
    if niche is None:
        return False
    if isinstance(niche, float) and math.isnan(niche):
        return False
    
    niche_lower = str(niche).strip().lower()
    if not niche_lower:
        return False

    # Check for primary niches: Education, STEM, Parenting
    target_keywords = ["education", "stem", "parenting", "edtech", "study", "math", "science", "coding"]
    return any(keyword in niche_lower for keyword in target_keywords)


def evaluate_influencer(row: pd.Series) -> pd.Series:
    """
    Evaluates a single influencer row against EDXSO selection criteria.

    Pass Criteria:
    - Followers/Subscribers: Strictly between 5,000 and 100,000 (5,000 < count < 100,000)
    - Engagement Rate: >= 2.5%
    - Email: Present, non-empty, and not 'Not Found'
    - Niche: Related to Education, STEM, or Parenting

    Args:
        row: Pandas Series representing an influencer profile.

    Returns:
        Pandas Series with index ['Status', 'Reason'].
    """
    reasons: List[str] = []

    # 1. Follower / Subscriber Count check
    # Check 'Subscriber Count' or 'Followers' or 'subscriber_count'
    sub_keys = ["Subscriber Count", "Followers", "subscriber_count", "subscribers"]
    sub_val = None
    for k in sub_keys:
        if k in row and pd.notna(row[k]):
            sub_val = row[k]
            break

    try:
        sub_count = float(sub_val) if sub_val is not None else 0.0
    except (ValueError, TypeError):
        sub_count = 0.0

    if sub_count <= 5000:
        reasons.append("Subscriber count too low (<= 5,000)")
    elif sub_count >= 100000:
        reasons.append("Subscriber count too high (>= 100,000)")

    # 2. Engagement Rate check
    eng_keys = ["Estimated Engagement Rate (%)", "Engagement Rate", "engagement_rate", "Estimated Engagement Rate"]
    eng_val = None
    for k in eng_keys:
        if k in row and pd.notna(row[k]):
            eng_val = row[k]
            break

    try:
        eng_rate = float(eng_val) if eng_val is not None else 0.0
    except (ValueError, TypeError):
        eng_rate = 0.0

    if eng_rate < 2.5:
        reasons.append("Low engagement (< 2.5%)")

    # 3. Email check
    email_val = row.get("Email") if "Email" in row else row.get("email")
    if not is_valid_email(email_val):
        reasons.append("Email missing")

    # 4. Niche check
    niche_val = row.get("Niche") if "Niche" in row else row.get("niche")
    if not is_valid_niche(niche_val):
        reasons.append("Invalid niche (must be Education, STEM, or Parenting)")

    # Decision
    if not reasons:
        return pd.Series({"Status": "Pass", "Reason": "Qualified"})
    else:
        return pd.Series({"Status": "Fail", "Reason": " | ".join(reasons)})


def filter_influencers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the evaluation logic to an entire DataFrame and appends 'Status' and 'Reason'.

    Args:
        df: Input DataFrame containing influencer data.

    Returns:
        DataFrame with added 'Status' and 'Reason' columns.
    """
    if df.empty:
        return df.assign(Status=pd.Series(dtype="str"), Reason=pd.Series(dtype="str"))

    eval_df = df.apply(evaluate_influencer, axis=1)
    result_df = df.copy()
    result_df["Status"] = eval_df["Status"]
    result_df["Reason"] = eval_df["Reason"]
    return result_df

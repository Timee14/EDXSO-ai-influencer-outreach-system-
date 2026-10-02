"""
EDXSO Automated Micro-Influencer Outreach System - Main Pipeline Orchestrator
----------------------------------------------------------------------------
Executes the end-to-end workflow:
1. Discovery: Fetches niche creators via YouTube Data API v3 (if raw data doesn't exist).
2. Filtering: Evaluates creators against EDXSO qualification criteria.
3. AI Personalization: Generates tailored Email & Instagram DM copy via OpenAI gpt-4o-mini.
4. Sending & Tracking: Dispatches emails via Gmail SMTP (SSL 465) and logs history to prevent duplicates.
"""

import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.discovery import discover_influencers
from src.filter import filter_influencers
from src.ai_generator import batch_generate_outreach
from src.tracker import OutreachTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("EDXSO-Pipeline")


def run_pipeline(
    raw_data_path: str = "data/raw_influencers.csv",
    force_discovery: bool = False,
    dry_run: bool = False,
    target_discovery_count: int = 50
) -> pd.DataFrame:
    """
    Executes the automated influencer outreach pipeline.

    Args:
        raw_data_path: Path to raw influencer CSV.
        force_discovery: Force re-running YouTube discovery even if file exists.
        dry_run: If True, simulates email sending without triggering SMTP.
        target_discovery_count: Number of channels to discover if discovery is run.

    Returns:
        Updated tracker DataFrame.
    """
    print("\n" + "=" * 70)
    print(" 🚀 STARTING EDXSO MICRO-INFLUENCER OUTREACH PIPELINE")
    print("=" * 70)

    # Step 0: Load environment variables
    load_dotenv()

    raw_file = Path(raw_data_path)

    # Step 1: Data Discovery
    print("\n[STEP 1/4] Checking Influencer Discovery Data...")
    if force_discovery or not raw_file.exists():
        logger.info("Raw data not found or discovery forced. Initiating YouTube API Discovery...")
        try:
            raw_df = discover_influencers(
                target_count=target_discovery_count,
                output_path=str(raw_file)
            )
            logger.info("Discovery complete. Discovered %d channels.", len(raw_df))
        except Exception as e:
            logger.error("Discovery failed: %s", e)
            print(f"❌ Error during discovery: {e}")
            return pd.DataFrame()
    else:
        logger.info("Loading existing raw data from %s", raw_file.resolve())
        raw_df = pd.read_csv(raw_file)
        logger.info("Loaded %d raw influencer records.", len(raw_df))

    if raw_df.empty:
        logger.warning("No influencer records to process. Exiting pipeline.")
        return pd.DataFrame()

    # Step 2: Filtering & Qualification
    print("\n[STEP 2/4] Applying Qualification & Filtering Logic...")
    filtered_df = filter_influencers(raw_df)
    
    passed_mask = filtered_df["Status"] == "Pass"
    passed_df = filtered_df[passed_mask].copy()
    failed_count = len(filtered_df) - len(passed_df)

    logger.info("Evaluation results: %d Passed | %d Failed", len(passed_df), failed_count)

    if passed_df.empty:
        logger.warning("No influencers met the qualification criteria.")
        print("\nPipeline finished with 0 qualified candidates.")
        return pd.DataFrame()

    print(f"✅ Found {len(passed_df)} qualified micro-influencer(s).")

    # Step 3: AI Personalization Engine
    print("\n[STEP 3/4] Generating AI Personalized Outreach Copies (gpt-4o-mini)...")
    try:
        outreach_ready_df = batch_generate_outreach(passed_df, only_passed=True)
        logger.info("Successfully generated personalized messages for %d influencer(s).", len(outreach_ready_df))
    except Exception as e:
        logger.error("Failed during AI outreach generation: %s", e)
        print(f"❌ AI Generation Error: {e}")
        return pd.DataFrame()

    # Step 4: Dispatch & Tracking Layer
    print("\n[STEP 4/4] Outbound Dispatch & Duplicate-Prevention Tracking...")
    if dry_run:
        print("⚠️  DRY RUN MODE ENABLED: Simulating email dispatch...")

    tracker = OutreachTracker()
    updated_tracker_df = tracker.log_and_send(outreach_ready_df, dry_run=dry_run)

    print("\n" + "=" * 70)
    print(" 🎉 PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
    print(f" 📁 Tracker Log Saved: {tracker.tracker_path.resolve()}")
    print("=" * 70 + "\n")

    return updated_tracker_df


def parse_args():
    parser = argparse.ArgumentParser(description="EDXSO Automated Micro-Influencer Outreach System")
    parser.add_argument(
        "--raw-path",
        default="data/raw_influencers.csv",
        help="Path to raw influencer CSV (default: data/raw_influencers.csv)"
    )
    parser.add_argument(
        "--force-discovery",
        action="store_true",
        help="Force re-discovery of channels from YouTube API even if CSV exists"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate email sending without connecting to live SMTP server"
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=50,
        help="Target number of channels to discover (default: 50)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        raw_data_path=args.raw_path,
        force_discovery=args.force_discovery,
        dry_run=args.dry_run,
        target_discovery_count=args.target_count
    )

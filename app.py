"""
EDXSO Micro-Influencer Outreach System - Interactive Web Dashboard
-----------------------------------------------------------------
Streamlit web application running on http://localhost:8501
Provides real-time UI, interactive data exploration, AI copy editing, and 1-click dispatch.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import streamlit as st

# Load modules
from src.discovery import discover_influencers
from src.filter import filter_influencers
from src.ai_generator import generate_outreach, batch_generate_outreach
from src.tracker import OutreachTracker

# Page Configuration
st.set_page_config(
    page_title="EDXSO Influencer Outreach Hub",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366F1 0%, #A855F7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #64748B;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 1.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 1.05rem;
        padding-top: 0.8rem;
        padding-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Load environment
load_dotenv()

# Session State Initialization
if "raw_df" not in st.session_state:
    raw_path = Path("data/raw_influencers.csv")
    if raw_path.exists():
        st.session_state.raw_df = pd.read_csv(raw_path)
    else:
        st.session_state.raw_df = pd.DataFrame()

if "filtered_df" not in st.session_state:
    if not st.session_state.raw_df.empty:
        st.session_state.filtered_df = filter_influencers(st.session_state.raw_df)
    else:
        st.session_state.filtered_df = pd.DataFrame()

if "outreach_df" not in st.session_state:
    st.session_state.outreach_df = pd.DataFrame()

tracker = OutreachTracker()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/graduation-cap.png", width=64)
    st.title("EDXSO Admin")
    st.caption("Micro-Influencer Growth Engine")
    st.divider()

    st.subheader("🔑 Credentials Status")
    yt_val = os.getenv("YOUTUBE_API_KEY", "").strip()
    openai_val = os.getenv("OPENAI_API_KEY", "").strip()
    email_val = os.getenv("SENDER_EMAIL", "").strip()
    pwd_val = os.getenv("SENDER_PASSWORD", "").strip()

    yt_status = "✅ Connected" if yt_val else "❌ Missing"
    openai_status = "✅ Connected" if openai_val else "❌ Missing"
    smtp_status = "✅ Connected" if (email_val and pwd_val) else "⚠️ Missing"

    st.write(f"**YouTube API:** {yt_status}")
    st.write(f"**OpenAI API:** {openai_status}")
    st.write(f"**Gmail SMTP:** {smtp_status}")

    with st.expander("⚙️ Enter / Update API Keys", expanded=(not yt_val or not openai_val)):
        new_yt_key = st.text_input("YouTube Data API Key", value=yt_val, type="password", help="From Google Cloud Console")
        new_openai_key = st.text_input("OpenAI API Key", value=openai_val, type="password", help="From platform.openai.com")
        new_email = st.text_input("Gmail Address", value=email_val, help="Your sending Gmail address")
        new_pwd = st.text_input("Gmail App Password", value=pwd_val, type="password", help="16-character App Password from myaccount.google.com/apppasswords")

        if st.button("💾 Save Credentials", use_container_width=True, type="primary"):
            env_content = f"""# YouTube Data API v3 Key
YOUTUBE_API_KEY={new_yt_key.strip()}

# OpenAI API Key
OPENAI_API_KEY={new_openai_key.strip()}

# Gmail SMTP Credentials
SENDER_EMAIL={new_email.strip()}
SENDER_PASSWORD={new_pwd.strip()}
"""
            with open(".env", "w", encoding="utf-8") as f:
                f.write(env_content)
            
            # Update current runtime environment
            os.environ["YOUTUBE_API_KEY"] = new_yt_key.strip()
            os.environ["OPENAI_API_KEY"] = new_openai_key.strip()
            os.environ["SENDER_EMAIL"] = new_email.strip()
            os.environ["SENDER_PASSWORD"] = new_pwd.strip()
            
            st.success("Credentials saved to .env!")
            st.rerun()

    st.divider()
    st.subheader("⚙️ Pipeline Controls")
    dry_run = st.checkbox("Dry Run Mode (Simulate Send)", value=True, help="Prevents sending real emails over SMTP.")
    target_count = st.slider("Target Discovery Count", min_value=10, max_value=100, value=50, step=10)
    
    st.divider()
    if st.button("🚀 Run Full Pipeline", type="primary", use_container_width=True):
        if not os.getenv("YOUTUBE_API_KEY"):
            st.error("❌ Please provide a YouTube API Key in the sidebar first!")
        elif not os.getenv("OPENAI_API_KEY"):
            st.error("❌ Please provide an OpenAI API Key in the sidebar first!")
        else:
            with st.spinner("Executing End-to-End Pipeline..."):
                try:
                    # Step 1: Discovery
                    if st.session_state.raw_df.empty:
                        st.session_state.raw_df = discover_influencers(target_count=target_count)
                    
                    # Step 2: Filtering
                    st.session_state.filtered_df = filter_influencers(st.session_state.raw_df)
                    passed = st.session_state.filtered_df[st.session_state.filtered_df["Status"] == "Pass"]
                    
                    # Step 3: AI Generation
                    if not passed.empty:
                        st.session_state.outreach_df = batch_generate_outreach(passed, only_passed=True)
                        
                        # Step 4: Tracking & Dispatch
                        tracker.log_and_send(st.session_state.outreach_df, dry_run=dry_run)
                        st.success("🎉 Full pipeline executed successfully!")
                        st.rerun()
                    else:
                        st.warning("No qualified influencers passed the criteria.")
                except Exception as e:
                    st.error(f"Pipeline Error: {e}")

# ----------------- MAIN CONTENT -----------------
st.markdown('<div class="main-header">🎓 EDXSO Automated Micro-Influencer Outreach Hub</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Discover, qualify, personalize, and pitch YouTube creators in EdTech, STEM, and Education.</div>', unsafe_allow_html=True)

tabs = st.tabs([
    "🔍 1. Discovery",
    "🎯 2. Qualification & Filtering",
    "🤖 3. AI Outreach Studio",
    "📨 4. Dispatch & Tracker"
])

# ----------------- TAB 1: DISCOVERY -----------------
with tabs[0]:
    st.header("Influencer Discovery")
    col1, col2 = st.columns([3, 1])
    with col1:
        query_input = st.text_input(
            "Search Keywords (comma separated)",
            value="edtech tools, study tips, student productivity, learning methods"
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("🔎 Fetch Channels", type="primary", use_container_width=True):
            queries = [q.strip() for q in query_input.split(",") if q.strip()]
            with st.spinner(f"Querying YouTube Data API for {target_count} channels..."):
                try:
                    df = discover_influencers(queries=queries, target_count=target_count)
                    st.session_state.raw_df = df
                    st.session_state.filtered_df = filter_influencers(df)
                    st.success(f"Discovered {len(df)} channels successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Discovery Error: {e}")

    if not st.session_state.raw_df.empty:
        df = st.session_state.raw_df
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Channels", len(df))
        has_email = len(df[df["Email"].str.contains("@", na=False)])
        m2.metric("Channels with Email", has_email, f"{round(has_email/len(df)*100, 1)}%")
        avg_subs = int(df["Subscriber Count"].mean()) if "Subscriber Count" in df else 0
        m3.metric("Avg Subscribers", f"{avg_subs:,}")
        avg_eng = round(df["Estimated Engagement Rate (%)"].mean(), 2) if "Estimated Engagement Rate (%)" in df else 0
        m4.metric("Avg Engagement", f"{avg_eng}%")

        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "URL": st.column_config.LinkColumn("YouTube Channel"),
                "Estimated Engagement Rate (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "Subscriber Count": st.column_config.NumberColumn(format="%d")
            },
            hide_index=True
        )
    else:
        st.info("No raw discovery data yet. Click 'Fetch Channels' above or check your YouTube API key.")

# ----------------- TAB 2: FILTERING -----------------
with tabs[1]:
    st.header("Qualification & Filtering Engine")
    st.markdown("""
    **Criteria Rules:**
    - 👥 **Subscribers:** Strictly between **5,000** and **100,000**.
    - 📈 **Engagement Rate:** $\ge$ **2.5%**.
    - ✉️ **Email:** Valid contact email present.
    - 🏷️ **Niche:** Education, STEM, or Parenting.
    """)

    if not st.session_state.raw_df.empty:
        if st.button("⚡ Re-Evaluate Influencers"):
            st.session_state.filtered_df = filter_influencers(st.session_state.raw_df)
            st.rerun()

        f_df = st.session_state.filtered_df
        if not f_df.empty:
            passed_df = f_df[f_df["Status"] == "Pass"]
            failed_df = f_df[f_df["Status"] == "Fail"]

            k1, k2, k3 = st.columns(3)
            k1.metric("✅ Qualified Creators", len(passed_df))
            k2.metric("❌ Disqualified", len(failed_df))
            k3.metric("🎯 Pass Rate", f"{round(len(passed_df)/len(f_df)*100, 1)}%")

            view_mode = st.radio("Display:", ["All Candidates", "Qualified Only (Pass)", "Disqualified Only (Fail)"], horizontal=True)

            if view_mode == "Qualified Only (Pass)":
                display_df = passed_df
            elif view_mode == "Disqualified Only (Fail)":
                display_df = failed_df
            else:
                display_df = f_df

            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "URL": st.column_config.LinkColumn("Channel URL"),
                    "Estimated Engagement Rate (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "Subscriber Count": st.column_config.NumberColumn(format="%d")
                },
                hide_index=True
            )
    else:
        st.info("Please discover channels in Tab 1 first.")

# ----------------- TAB 3: AI OUTREACH STUDIO -----------------
with tabs[2]:
    st.header("AI Personalization Studio (gpt-4o-mini)")
    st.caption("Crafts tailored UGC pitch emails (60–90 words) and casual Instagram DMs (15–30 words).")

    passed_candidates = (
        st.session_state.filtered_df[st.session_state.filtered_df["Status"] == "Pass"]
        if not st.session_state.filtered_df.empty
        else pd.DataFrame()
    )

    if passed_candidates.empty:
        st.warning("No qualified influencers to generate outreach for. Please qualify candidates in Tab 2.")
    else:
        if st.button("✨ Generate AI Outreach Copies for All Qualified", type="primary"):
            with st.spinner("Generating personalized copies via OpenAI gpt-4o-mini..."):
                try:
                    st.session_state.outreach_df = batch_generate_outreach(passed_candidates, only_passed=True)
                    st.success(f"Generated outreach copies for {len(st.session_state.outreach_df)} creators!")
                    st.rerun()
                except Exception as e:
                    st.error(f"OpenAI Error: {e}")

        if not st.session_state.outreach_df.empty:
            for idx, row in st.session_state.outreach_df.iterrows():
                with st.expander(f"👤 {row.get('Channel Name', 'Creator')} | ✉️ {row.get('Email', 'N/A')}", expanded=(idx == 0)):
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.markdown("**📧 Email Pitch (Target: 60-90 words)**")
                        email_text = st.text_area(
                            "Email Body",
                            value=row.get("Generated_Email", ""),
                            height=150,
                            key=f"email_{idx}"
                        )
                        word_count = len(email_text.split())
                        st.caption(f"Word count: {word_count} words")

                    with c2:
                        st.markdown("**💬 Instagram DM (Target: 15-30 words)**")
                        dm_text = st.text_area(
                            "DM Body",
                            value=row.get("Generated_DM", ""),
                            height=150,
                            key=f"dm_{idx}"
                        )
                        dm_word_count = len(dm_text.split())
                        st.caption(f"Word count: {dm_word_count} words")

                    if st.button("🔄 Regenerate for this creator", key=f"regen_{idx}"):
                        with st.spinner("Regenerating..."):
                            single_outreach = generate_outreach(row)
                            st.session_state.outreach_df.at[idx, "Generated_Email"] = single_outreach["Generated_Email"]
                            st.session_state.outreach_df.at[idx, "Generated_DM"] = single_outreach["Generated_DM"]
                            st.rerun()

# ----------------- TAB 4: TRACKER & DISPATCH -----------------
with tabs[3]:
    st.header("Outbound Dispatch & Audit Tracker")
    st.caption("Real-time log of sent emails and automatic duplicate prevention.")

    if not st.session_state.outreach_df.empty:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.info(f"Ready to dispatch outreach to {len(st.session_state.outreach_df)} qualified candidates.")
        with c2:
            if st.button("🚀 Send Outreach Emails", type="primary", use_container_width=True):
                with st.spinner("Dispatching via Gmail SSL SMTP..."):
                    updated_tracker = tracker.log_and_send(st.session_state.outreach_df, dry_run=dry_run)
                    st.success("Dispatch process finished! See updated logs below.")
                    st.rerun()

    # Load and display tracker table
    tracker_df = tracker._load_tracker()
    if not tracker_df.empty:
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Total Contacted", len(tracker_df))
        sent_count = len(tracker_df[tracker_df["Send_Status"] == "Sent"])
        t2.metric("✅ Successfully Sent", sent_count)
        dup_count = len(tracker_df[tracker_df["Send_Status"] == "Skipped - Duplicate"])
        t3.metric("🔁 Skipped Duplicates", dup_count)
        fail_count = len(tracker_df[tracker_df["Send_Status"] == "Failed"])
        t4.metric("❌ Failed", fail_count)

        st.subheader("Audit Log")
        st.dataframe(tracker_df, use_container_width=True, hide_index=True)

        # Download Tracker CSV
        csv_data = tracker_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Tracker CSV",
            data=csv_data,
            file_name="edxso_outreach_tracker.csv",
            mime="text/csv"
        )
    else:
        st.info("No emails dispatched yet. Run dispatch or execute the pipeline to view tracking history.")

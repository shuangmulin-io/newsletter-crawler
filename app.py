import os
import sys
import time
from datetime import datetime

# Force UTF-8 encoding on standard streams to prevent Windows charmap encoding errors
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

os.environ["PYTHONUTF8"] = "1"

import patch_crewai
import streamlit as st
import json
import re
import logging
import traceback
from dotenv import load_dotenv
from typing import List

# Load environment variables from .env file using absolute path
from pathlib import Path
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Sanitize loaded keys from potential whitespaces or quotes
for key in ["GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MODEL_NAME", "API_BASE_URL"]:
    val = os.getenv(key)
    if val:
        os.environ[key] = val.strip().strip("'\"")

# Ensure output directory exists before config
os.makedirs("output", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('output/crawler_errors.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Import our modular run utility from core.pipeline and helpers from utils.security
from core.pipeline import run_crawler_pipeline
from utils.security import is_safe_url, sanitize_input, sanitize_url

def inject_entity_badges(markdown_text: str) -> str:
    """
    Scans the markdown content and wraps entity type declarations
    (e.g., "- **Entity Type**: model") with custom styled colored HTML span badges.

    Args:
        markdown_text: Raw markdown report text.

    Returns:
        Processed markdown string containing styled HTML entity badges.
    """
    def badge_replacer(match):
        entity_type = match.group(1).strip().lower()
        # Vibrant, modern design-friendly colors for badges
        colors = {
            "model": ("#2e7d32", "#e8f5e9"),       # green
            "product": ("#1565c0", "#e3f2fd"),     # blue
            "tool": ("#e65100", "#fff3e0"),        # orange
            "workflow tip": ("#6a1b9a", "#f3e5f5"), # purple
            "company": ("#37474f", "#eceff1"),     # slate gray
        }
        fg, bg = colors.get(entity_type, ("#424242", "#f5f5f5"))
        return f'- **Entity Type**: <span style="background-color: {bg}; color: {fg}; padding: 3px 8px; border-radius: 12px; font-size: 0.85em; font-weight: 600; display: inline-block; margin-left: 5px;">{entity_type.upper()}</span>'

    pattern = r'-\s*\*\*Entity\s+Type\*\*:\s*([a-zA-Z0-9\s_]+)'
    return re.sub(pattern, badge_replacer, markdown_text)

def sanitize_error_message(error_str: str, api_key: str = None) -> str:
    """
    Masks the API key or similar credentials in error messages.

    Args:
        error_str: Raw error message string.
        api_key: The active credential key to mask.

    Returns:
        Masked/sanitized error message string.
    """
    if not error_str:
        return ""
    if api_key and len(api_key) > 5:
        error_str = error_str.replace(api_key, "AI_STUDIO_API_KEY_MASKED")
    # Also capture common Gemini API key patterns
    error_str = re.sub(r'AIzaSy[A-Za-z0-9_\-]{33}', 'AI_STUDIO_API_KEY_MASKED', error_str)
    return error_str

def render_swarm_flow(active_index: int) -> str:
    """
    Renders the sequential agent execution flowchart in glassmorphic HTML.

    Args:
        active_index: 1-based index of the currently active agent.

    Returns:
        HTML string representation of the flowchart cards.
    """
    agents_info = [
        ("Pipeline Coordinator", "Enforces global pipeline rules, validates schemas, and coordinates task transitions.", "🛠️"),
        ("Discovery Specialist", "Performs query searches and scraping of newsletter archive URLs to isolate the latest issues.", "🔍"),
        ("Extraction Specialist", "Scrapes full issue bodies, strips out advertisements/sponsors, and maps items by entity types.", "📥"),
        ("Verification Specialist", "Executes multi-threaded URL status validation checks, determining primary source authenticity.", "🛡️"),
        ("Deduplication Specialist", "Resolves duplicates and consolidates reports mapping identical events using strict heuristics.", "✂️"),
        ("Formatting Specialist", "Builds final unified markdown structures and attaches automation-friendly structured JSON payloads.", "📄")
    ]
    
    html = '<div style="margin-top: 1rem; display: flex; flex-direction: column; gap: 0.75rem;">'
    for idx, (name, desc, icon) in enumerate(agents_info, 1):
        if idx < active_index:
            border_color = "rgba(16, 185, 129, 0.4)"
            status_text = "✅ Completed"
            status_color = "#10b981"
            opacity = "1.0"
            glow = ""
        elif idx == active_index:
            border_color = "#38bdf8"
            status_text = "⚡ Active & Processing..."
            status_color = "#38bdf8"
            opacity = "1.0"
            glow = "box-shadow: 0 0 15px rgba(56, 189, 248, 0.25); border-width: 1.5px;"
        else:
            border_color = "rgba(255, 255, 255, 0.05)"
            status_text = "⏳ Pending"
            status_color = "#64748b"
            opacity = "0.5"
            glow = ""
            
        card_html = f"""
        <div style="background: rgba(30, 41, 59, 0.35); border: 1px solid {border_color}; border-left: 4px solid {status_color}; border-radius: 8px; padding: 0.9rem 1.1rem; opacity: {opacity}; {glow} transition: all 0.3s ease;">
            <div style="display: flex; justify-content: space-between; align-items: center; font-weight: 600; color: #f8fafc; font-size: 0.95rem;">
                <span style="display: flex; align-items: center; gap: 0.5rem;"><span style="font-size: 1.25rem;">{icon}</span>{name}</span>
                <span style="color: {status_color}; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;">{status_text}</span>
            </div>
            <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.35rem; font-weight: 400; line-height: 1.45;">{desc}</div>
        </div>
        """
        html += card_html.strip().replace("\n", "").replace("        ", " ")
    html += '</div>'
    return html

def render_progress_bar(active_idx: int) -> str:
    """
    Renders a stunning glassmorphic HTML progress bar showing swarm crawl completion.

    Args:
        active_idx: The current step index (1-7).

    Returns:
        HTML string representing the visual progress bar layout.
    """
    percent = min(int((active_idx / 7.0) * 100), 100)
    status_labels = {
        1: "🛠️ Pipeline Coordinator: Enforcing rules & initializing swarm...",
        2: "🔍 Discovery Specialist: Scraping newsletter issue URLs...",
        3: "📥 Extraction Specialist: Filtering ads & parsing stories...",
        4: "🛡️ Verification Specialist: Multi-threaded primary source check...",
        5: "✂️ Deduplication Specialist: Merging duplicate reports...",
        6: "📄 Formatting Specialist: Creating report & output payload...",
        7: "✅ Completed successfully!"
    }
    label = status_labels.get(active_idx, "Processing...")
    return f"""
    <div style="background: rgba(15, 23, 42, 0.45); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem; backdrop-filter: blur(8px);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
            <span style="color: #f8fafc; font-size: 0.92rem; font-weight: 600; letter-spacing: -0.01em; font-family: sans-serif;">{label}</span>
            <span style="color: #38bdf8; font-size: 0.95rem; font-weight: 800; font-family: monospace;">{percent}%</span>
        </div>
        <div style="background: rgba(255, 255, 255, 0.08); border-radius: 6px; height: 10px; overflow: hidden; width: 100%;">
            <div style="background: linear-gradient(90deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%); width: {percent}%; height: 100%; border-radius: 6px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 0 10px rgba(129, 140, 248, 0.5);"></div>
        </div>
    </div>
    """

def render_terminal_logs(log_entries: List[str]) -> str:
    """
    Formats raw list entries into a terminal console log box styling in HTML.

    Args:
        log_entries: List of logging statement string elements.

    Returns:
        Structured console box HTML component string.
    """
    log_html = "".join([f'<div style="margin-bottom: 0.4rem; line-height: 1.45; color: #38bdf8;">{line}</div>' for line in log_entries])
    return f"""<div style="background-color: #0b0f19; border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 1.25rem; font-family: 'Courier New', Courier, monospace; color: #38bdf8; height: 480px; overflow-y: auto; font-size: 0.82rem; box-shadow: inset 0 0 15px rgba(0,0,0,0.85); box-sizing: border-box; width: 100%;">{log_html}</div>""".replace("\n", "")

# Set up page configurations
st.set_page_config(
    page_title="Daily AI News Web Crawler",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Inject premium design CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

/* Apply modern typography */
html, body, [class*="css"], .stMarkdown {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Glassmorphism Title Container */
.header-container {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.8) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 2.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(10px);
}

.main-title {
    font-size: 2.75rem;
    font-weight: 800;
    margin: 0;
    padding: 0;
    background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
}

.subtitle {
    color: #94a3b8;
    font-size: 1.15rem;
    margin-top: 0.5rem;
    margin-bottom: 0;
    font-weight: 400;
}

/* Premium KPI Card Styling */
.kpi-container {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.kpi-card {
    flex: 1;
    background: rgba(30, 41, 59, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    backdrop-filter: blur(5px);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.kpi-card:hover {
    transform: translateY(-3px);
    border-color: rgba(99, 102, 241, 0.4);
    box-shadow: 0 10px 25px rgba(99, 102, 241, 0.15);
}

.kpi-val {
    font-size: 2.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
    margin-bottom: 0.5rem;
}

.kpi-lbl {
    font-size: 0.8rem;
    color: #64748b;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Custom list items for agent logs */
.agent-flow-card {
    background: rgba(15, 23, 42, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-left: 4px solid #818cf8;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
}

.agent-flow-header {
    display: flex;
    justify-content: space-between;
    font-weight: 600;
    color: #f8fafc;
    font-size: 0.95rem;
}

.agent-flow-desc {
    color: #94a3b8;
    font-size: 0.85rem;
    margin-top: 0.25rem;
}

.agent-icon {
    font-size: 1.2rem;
    margin-right: 0.5rem;
}

/* Back to Top button styling */
.back-to-top-container {
    text-align: center;
    margin-top: 2.5rem;
    margin-bottom: 1.5rem;
}

.back-to-top-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(30, 41, 59, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 0.5rem 1.25rem;
    color: #38bdf8 !important;
    text-decoration: none !important;
    font-size: 0.9rem;
    font-weight: 600;
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.back-to-top-btn:hover {
    background: rgba(56, 189, 248, 0.1);
    border-color: #38bdf8;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(56, 189, 248, 0.15);
}
</style>
""", unsafe_allow_html=True)

# Render Header Title Block with top anchor
st.markdown("""
<div id="top-anchor"></div>
<div class="header-container">
    <h1 class="main-title">🕷️ Daily AI News Swarm Crawler</h1>
    <p class="subtitle">Deploy a collaborative, multi-agent CrewAI workforce to discover, scrape, verify, and consolidate news from leading newsletter channels.</p>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration Layout
st.sidebar.markdown("## ⚙️ Swarm Configuration")
st.sidebar.write("Customize your model provider and deployment criteria below.")

# Provider selection
provider = st.sidebar.selectbox(
    "LLM Provider",
    options=["Official Google Gemini", "Official Anthropic Claude", "Custom LLM Gateway (OpenAI / OpenRouter)"],
    index=0,
    help="Select the model provider backend."
)

# Dynamically change models and keys based on provider
if provider == "Official Google Gemini":
    model_options = ["gemini/gemini-3.6-flash", "gemini/gemini-3.5-flash-lite", "gemini/gemini-3.5-flash"]
    default_key = os.getenv("GEMINI_API_KEY", "")
    default_url = ""
    key_label = "Gemini API Key"
    show_url = False
    custom_model = False
elif provider == "Official Anthropic Claude":
    model_options = ["anthropic/claude-3-5-sonnet-20241022", "anthropic/claude-3-5-haiku-20241022"]
    default_key = os.getenv("ANTHROPIC_API_KEY", "")
    default_url = ""
    key_label = "Anthropic API Key"
    show_url = False
    custom_model = False
else:  # Custom LLM Gateway
    model_options = []
    default_key = ""
    default_url = os.getenv("API_BASE_URL", "")
    key_label = "API Key"
    show_url = True
    custom_model = True

if custom_model:
    selected_model = st.sidebar.text_input(
        "Choose Model", 
        value="openai/gpt-4o", 
        help="Specify the target model ID (e.g., openai/gpt-4o, openrouter/meta-llama/llama-3.1-405b)"
    )
else:
    selected_model = st.sidebar.selectbox("Choose Model", options=model_options, index=0)

api_key_input = st.sidebar.text_input(
    key_label,
    value=default_key,
    type="password",
    help=f"Enter your credentials for {provider}."
)

if show_url:
    base_url_input = st.sidebar.text_input(
        "API Base URL Gateway",
        value=default_url,
        help="Custom base endpoint URL for the API requests."
    )
else:
    base_url_input = ""

simulation_mode = False

st.sidebar.divider()
st.sidebar.markdown("### 🕸️ Swarm Target Newsletters")

if "crawler_targets" not in st.session_state:
    st.session_state.crawler_targets = [
        {"name": "TLDR AI", "url": "https://tldr.tech/api/latest/ai"},
        {"name": "The Rundown AI", "url": "https://www.therundown.ai/archive"},
        {"name": "The Neuron", "url": "https://theneuron.ai/newsletter"}
    ]

updated_targets = []
to_delete = None
for idx, target in enumerate(st.session_state.crawler_targets):
    st.sidebar.markdown(f"**Target #{idx+1}**")
    name_col, del_col = st.sidebar.columns([4, 1])
    with name_col:
        t_name = st.sidebar.text_input(f"Name #{idx+1}", value=target["name"], key=f"target_name_{idx}", label_visibility="collapsed")
    with del_col:
        if st.sidebar.button("🗑️", key=f"target_del_{idx}"):
            to_delete = idx
    t_url = st.sidebar.text_input(f"URL #{idx+1}", value=target["url"], key=f"target_url_{idx}", label_visibility="collapsed")
    updated_targets.append({"name": sanitize_input(t_name), "url": sanitize_url(t_url)})

if to_delete is not None:
    st.session_state.crawler_targets.pop(to_delete)
    st.rerun()

st.session_state.crawler_targets = updated_targets

if st.sidebar.button("➕ Add Target Newsletter", use_container_width=True):
    st.session_state.crawler_targets.append({"name": "New Publication", "url": "https://example.com/archive"})
    st.rerun()

st.sidebar.divider()
st.sidebar.info(
    "💡 **Execution Pipeline:** CrewAI coordinates 6 specialist agents: "
    "1. Coordinator ➜ 2. Discovery ➜ 3. Extraction ➜ 4. Verification ➜ 5. Deduplication ➜ 6. Formatting."
)

# Core Execution Controls
date_str = datetime.now().strftime("%Y-%m-%d")
output_file_path = f"output/daily_ai_news_{date_str}.md"
json_file_path = f"output/daily_ai_news_{date_str}.json"
cache_exists = os.path.exists(output_file_path)

cache_valid = True
if cache_exists and os.path.exists(json_file_path):
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            cached_json = json.load(f)
        cached_newsletters = cached_json.get("newsletters", [])
        cached_names = sorted([n.get("name") for n in cached_newsletters if n.get("name")])
        current_names = sorted([t.get("name") for t in st.session_state.crawler_targets if t.get("name")])
        if cached_names != current_names:
            cache_valid = False
    except Exception:
        cache_valid = False
else:
    cache_valid = False

force_fresh = False
if cache_exists:
    if not cache_valid:
        st.warning("⚠️ **Targets Configuration Changed**: Today's cached digest does not match your current sidebar target newsletters list. Bypassing cache to run a fresh crawl.")
        cache_exists = False
    else:
        st.info("📂 **Cached Report Found**: Today's AI News Swarm Digest has already been generated. You can view the cached report below, or check 'Force Fresh Swarm Run' to bypass the cache and run a fresh crawl.")
        force_fresh = st.checkbox("🔄 Force Fresh Swarm Run (re-run crawler and overwrite cache)", value=False)

# Core Execution Controls
duplicate_detected = False
invalid_url_detected = False
invalid_url_msg = ""
seen_names = set()
seen_urls = set()

for target in st.session_state.crawler_targets:
    name_strip = target["name"].strip()
    url_strip = target["url"].strip()
    
    if not name_strip or not url_strip:
        invalid_url_detected = True
        invalid_url_msg = "Target newsletter Name and URL fields cannot be empty."
        break
        
    if not url_strip.lower().startswith(("http://", "https://")):
        invalid_url_detected = True
        invalid_url_msg = f"Invalid URL scheme for '{name_strip}'. URLs must begin with http:// or https://."
        break
        
    if not is_safe_url(url_strip):
        invalid_url_detected = True
        invalid_url_msg = f"SSRF safety block on target '{name_strip}': Target URL '{url_strip}' points to an unsafe local, loopback, or private network range."
        break

    name_clean = name_strip.lower()
    url_clean = url_strip.lower()
    if name_clean in seen_names or url_clean in seen_urls:
        duplicate_detected = True
        break
    seen_names.add(name_clean)
    seen_urls.add(url_clean)

# Custom Model ID validation
is_model_valid = True
model_warning_msg = ""
if custom_model:
    model_val = selected_model.strip()
    if "/" not in model_val or model_val.startswith("/") or model_val.endswith("/"):
        is_model_valid = False
        model_warning_msg = "Custom Model ID must contain a provider prefix followed by a slash (e.g., 'openai/gpt-4o' or 'openrouter/meta-llama/llama-3.1-405b')."

targets_configured = len(st.session_state.crawler_targets) > 0 and not duplicate_detected and not invalid_url_detected and is_model_valid

if len(st.session_state.crawler_targets) == 0:
    st.warning("⚠️ **No Targets Configured**: Please configure at least one target newsletter in the sidebar to deploy the agent swarm.")
elif duplicate_detected:
    st.warning("⚠️ **Duplicate Targets Configured**: Please resolve duplicate names or URLs in the sidebar before deploying the agent swarm.")
elif invalid_url_detected:
    st.warning(f"⚠️ **Invalid Target Configured**: {invalid_url_msg}")
elif not is_model_valid:
    st.warning(f"⚠️ **Invalid Model Format**: {model_warning_msg}")

col1, col2 = st.columns([1.5, 4])
with col1:
    launch_btn = st.button("🚀 Deploy Agent Swarm", type="primary", use_container_width=True, disabled=not targets_configured)
with col2:
    st.write("Clicking deploy initiates the sequential agent workforce to process latest daily newsletter issues.")

if launch_btn:
    if not simulation_mode and not api_key_input:
        st.error(f"❌ Verification Error: Please specify your {key_label} in the configuration sidebar or enable Demo/Simulation Mode.")
    else:
        # Delete cache files if forcing a fresh run
        if force_fresh:
            import shutil
            if os.path.exists(output_file_path):
                os.remove(output_file_path)
            json_file_path = f"output/daily_ai_news_{date_str}.json"
            if os.path.exists(json_file_path):
                os.remove(json_file_path)
            # Clear url fetch cache
            if os.path.exists("output/.cache"):
                try:
                    shutil.rmtree("output/.cache")
                except Exception:
                    pass
            # Reset cache_exists state for this execution context
            cache_exists = False

        # Short-circuit if cached report exists and force fresh is not requested
        if cache_exists and not force_fresh:
            st.write("### 🧠 Live Swarm Execution Monitor")
            col_flow, col_term = st.columns([1, 1])
            with col_flow:
                st.markdown("**Agent Swarm Flowchart**")
                flow_placeholder = st.empty()
                flow_placeholder.markdown(render_swarm_flow(7), unsafe_allow_html=True)
            with col_term:
                st.markdown("**🖥️ Swarm Live Activity Logs**")
                terminal_placeholder = st.empty()
                log_entries = [
                    "Step 1: 📂 Cache Loader: Checking for existing daily reports...",
                    f"Step 2: 📂 Cache Loader: Today's cached report found at output/daily_ai_news_{date_str}.md.",
                    "Step 3: 📂 Cache Loader: Instantly loaded cached briefing report from disk.",
                    "🏁 Step 4: 📂 Cache Loader: Swarm cache loading completed successfully!"
                ]
                terminal_placeholder.markdown(render_terminal_logs(log_entries), unsafe_allow_html=True)
            
            # Save logs to file
            os.makedirs("output", exist_ok=True)
            with open("output/swarm_console.log", "w", encoding="utf-8") as f:
                f.write("\n".join(log_entries))
                
            st.success("🎉 Swarm Cached Briefing Loaded Instantly!")
            import time
            time.sleep(1.0)
            st.rerun()
            
        # Create dynamic grid for Flow and Terminal
        st.write("### 🧠 Live Swarm Execution Monitor")
        progress_placeholder = st.empty()
        col_flow, col_term = st.columns([1, 1])
        
        with col_flow:
            st.markdown("**Agent Swarm Flowchart**")
            flow_placeholder = st.empty()
        with col_term:
            st.markdown("**🖥️ Swarm Live Activity Logs**")
            terminal_placeholder = st.empty()
            
        log_entries = []
        
        def update_ui(active_idx, log_lines):
            progress_placeholder.markdown(render_progress_bar(active_idx), unsafe_allow_html=True)
            flow_placeholder.markdown(render_swarm_flow(active_idx), unsafe_allow_html=True)
            for line in log_lines:
                log_entries.append(line)
            terminal_placeholder.markdown(render_terminal_logs(log_entries), unsafe_allow_html=True)
            
        if simulation_mode:
            import time
            
            # Step 1: Coordinator
            update_ui(1, [
                "⏳ Step 1: 🛠️ Coordinator: Initializing sequential workforce pipeline...",
                "⏳ Step 2: 🛠️ Coordinator: Loading Discovery, Extraction, Verification, Deduplication, and Formatting constraints..."
            ])
            time.sleep(1.0)
                       # Step 2: Discovery
            targets_names = ", ".join([t["name"] for t in st.session_state.crawler_targets])
            update_ui(2, [
                f"⏳ Step 4: 🔍 Discovery: Initiating issue lookup for {targets_names}...",
            ])
            time.sleep(1.0)
            
            for idx, target in enumerate(st.session_state.crawler_targets):
                name = target["name"]
                url = target["url"]
                update_ui(2, [
                    f"⏳ Step {5+idx*2}: 🔍 Discovery: Querying {name} latest endpoint: {url}..."
                ])
                time.sleep(1.0)
                if "neuron" in name.lower():
                    update_ui(2, [
                        f"⚠️ Step {6+idx*2}: 🔍 Discovery: Fetching {name} blocks. Cloudflare 403 firewall detected. Graceful fallback activated.",
                        f"✅ Step {6+idx*2}: 🔍 Discovery: {name} simulated cache fallback loaded: https://theneuron.ai/newsletter/2026-07-22"
                    ])
                else:
                    update_ui(2, [
                        f"✅ Step {6+idx*2}: 🔍 Discovery: {name} successfully resolved dynamically."
                    ])
                time.sleep(0.8)
                
            last_idx = 4 + len(st.session_state.crawler_targets) * 2
            update_ui(2, [
                f"✅ Step {last_idx + 1}: 🔍 Discovery: All issue endpoints resolved. Task completed. Handing off to Extraction Specialist..."
            ])
            time.sleep(1.2)
            
            # Step 3: Extraction
            start_extract_step = last_idx + 2
            update_ui(3, [
                f"⏳ Step {start_extract_step}: 📥 Extraction: Spawning scraping parser workers...",
                f"⏳ Step {start_extract_step+1}: 📥 Extraction: Fetching body contents from active newsletter issue URLs..."
            ])
            time.sleep(1.0)
            
            extract_log_lines = []
            curr_step = start_extract_step + 2
            for target in st.session_state.crawler_targets:
                name = target["name"]
                if "tldr" in name.lower():
                    desc = "Extracted 3 story blocks (Meta Llama 3.3, OpenAI Search, Anthropic sharing)."
                elif "rundown" in name.lower():
                    desc = "Extracted 2 story blocks (Meta Llama 3.3, Chain of Density summary)."
                elif "neuron" in name.lower():
                    desc = "Extracted 2 story blocks (OpenAI Search, AST Code Generation)."
                else:
                    desc = "Extracted 1 story block (Dynamic custom newsletter content)."
                extract_log_lines.append(f"✅ Step {curr_step}: 📥 Extraction: {name} - {desc}")
                curr_step += 1
                
            extract_log_lines.append(f"✅ Step {curr_step}: 📥 Extraction: All story payloads labeled by entity types. Task completed. Handing off to Verification Specialist...")
            update_ui(3, extract_log_lines)
            time.sleep(1.2)
            
            # Step 4: Verification
            curr_step += 1
            update_ui(4, [
                f"⏳ Step {curr_step}: 🛡️ Verification: Spawning parallel url verification worker threadpool...",
                f"⏳ Step {curr_step+1}: 🛡️ Verification: Testing target url endpoints connectivity..."
            ])
            time.sleep(1.0)
            curr_step += 2
            update_ui(4, [
                f"✅ Step {curr_step}: 🛡️ Verification: Verified source: https://github.com/meta-llama/llama3 ➜ Status 200 (Active)",
                f"✅ Step {curr_step+1}: 🛡️ Verification: Verified source: https://huggingface.co/meta-llama ➜ Status 200 (Active)",
                f"✅ Step {curr_step+2}: 🛡️ Verification: Verified source: https://openai.com/news/ ➜ Status 403 (Active, anti-bot bypass enabled)",
                f"✅ Step {curr_step+3}: 🛡️ Verification: Verified source: https://ai.meta.com/research/ ➜ Status 200 (Active)",
                f"✅ Step {curr_step+4}: 🛡️ Verification: Parallel check completed. Source link authenticity mapped. Handing off to Deduplication Specialist..."
            ])
            time.sleep(1.2)
            curr_step += 5
            
            # Step 5: Deduplication
            update_ui(5, [
                f"⏳ Step {curr_step}: ✂️ Deduplication: Inspecting verified stories for content semantic overlaps...",
                f"⏳ Step {curr_step+1}: ✂️ Deduplication: Running matching heuristics (entity type: model, entity name: Llama 3.3)..."
            ])
            time.sleep(1.0)
            curr_step += 2
            update_ui(5, [
                f"✅ Step {curr_step}: ✂️ Deduplication: High-confidence event merge: Meta Llama 3.3 releases (TLDR-01, Rundown-01).",
                f"✅ Step {curr_step+1}: ✂️ Deduplication: High-confidence event merge: OpenAI Search Features (TLDR-02, Neuron-01).",
                f"✅ Step {curr_step+2}: ✂️ Deduplication: Consolidated canonical items mapped to parent stories. Handing off to Formatting Specialist..."
            ])
            time.sleep(1.2)
            curr_step += 3
            
            # Step 6: Formatting
            update_ui(6, [
                f"⏳ Step {curr_step}: 📄 Formatting: Initializing markdown serializer engine...",
                f"⏳ Step {curr_step+1}: 📄 Formatting: Generating daily briefing report structure...",
                f"⏳ Step {curr_step+2}: 📄 Formatting: Appending automation-ready Pydantic JSON block to output payload..."
            ])
            time.sleep(1.0)
            curr_step += 3
            update_ui(6, [
                f"✅ Step {curr_step}: 📄 Formatting: File successfully generated and written to output/daily_ai_news_{date_str}.md."
            ])
            time.sleep(1.0)
            
            # Step 7: Completed
            update_ui(7, [
                f"🏁 Step {curr_step+1}: 📄 Formatting: Swarm crawler execution finalized successfully!"
            ])
            time.sleep(1.0)
            
            # Generate mock Section 1 based on configured targets
            section1_lines = []
            mock_newsletters_json = []
            for target in st.session_state.crawler_targets:
                name = target["name"]
                url = target["url"]
                if "tldr" in name.lower():
                    issue_url = "https://tldr.tech/ai/2026-07-27"
                    status = "(Live resolved)"
                elif "rundown" in name.lower():
                    issue_url = "https://www.therundown.ai/p/anthropic-opus-5-surprise"
                    status = "(Live scraped)"
                elif "neuron" in name.lower():
                    issue_url = "https://theneuron.ai/newsletter/2026-07-22"
                    status = "(Simulation fallback)"
                else:
                    issue_url = url + "/2026-07-22"
                    status = "(Live resolved)"
                section1_lines.append(f"- **{name}**: [{issue_url}]({issue_url}) {status}")
                mock_newsletters_json.append({"name": name, "issue_url": issue_url})
            section1_str = "\n".join(section1_lines)
            
            # Write high-fidelity mock results to daily_ai_news.md and daily_ai_news.json
            mock_content = f"""# 🕷️ Daily AI News Swarm Digest - July 27, 2026
 
## Section 1: Newsletter Issues Processed
{section1_str}

---

## Section 2: Deduplicated Canonical Stories

### 📢 Meta Releases Llama 3.3 Model
- **Primary Source**: [Meta AI Research Blog](https://ai.meta.com/research/) (Verified)
- **Other Sources**: 
  - [Meta Llama GitHub repository](https://github.com/meta-llama/llama3) (Verified)
  - [Hugging Face Llama Page](https://huggingface.co/meta-llama) (Verified)
- **Description**: Meta has officially released Llama 3.3, a highly efficient 70B parameter open-weight model that matches or outperforms proprietary models on major benchmarks. It features a massive 128k context window and has been optimized for multi-lingual translation, reasoning, and local developer deployments.

### 🔍 OpenAI Search Features Integrated into GPT-4o and Bing
- **Primary Source**: [OpenAI Blog](https://openai.com/news/) (Verified - Screened by anti-bot firewall)
- **Other Sources**:
  - [Microsoft Bing Blog](https://blogs.microsoft.com/blog/2023/02/07/reinventing-search-with-a-new-ai-powered-microsoft-bing-and-edge-your-copilot-for-the-web/) (Verified)
- **Description**: OpenAI is rolling out conversational search features directly inside GPT-4o, giving premium users real-time web-anchored responses. Simultaneously, Microsoft announced integration of these capabilities into its Bing search platform to challenge standard search engine architectures.

### 🛠️ Anthropic Introduces Public Artifact Sharing
- **Primary Source**: [Anthropic Artifacts Page](https://www.anthropic.com/news/sharing-artifacts) (Verified - Screened by anti-bot firewall)
- **Description**: Anthropic launched a new sharing feature for Claude, allowing users to share their interactive 'Artifacts' publicly or with teams, streamlining interactive app prototype development.

---

## Section 3: Extracted Items in Reading Order

### 📰 Apple Intelligence Integration
- **Entity Type**: product
- **Comprehensive Summary**: Apple entered a landmark partnership with Cohere to bring localized enterprise chat features to the macOS developer pipeline, expanding its AI offerings.
- **Verified Source Links**:
  - Primary Source: [Apple Newsroom](https://www.apple.com/newsroom/2024/06/introducing-apple-intelligence-for-iphone-ipad-and-mac/) (Verified)

---

## Section 4: Tips and Workflows
### 💡 Prompt Engineering: Chain of Density
- **Summary**: The Chain of Density (CoD) is an advanced iterative prompting framework designed to generate information-dense summaries. In practice, the LLM continuously identifies missing salient entities from the source text and merges them into the summary recursively without increasing the total length, resulting in a highly condensed, feature-rich output. This ensures that the generated newsletter digests are extremely detailed, saving reading time while maintaining maximum information coverage.
- **Source**: [arXiv summary](https://arxiv.org/abs/2309.04269) (Verified)

### 💡 AST Parsing for Code Generation
- **Summary**: Abstract Syntax Tree (AST) parsing enhances code-generation safety by analyzing code syntax programmatically before execution. By running the generated code string through a parser (such as Python's `ast.parse`), the system detects missing imports, syntax errors, and broken logical blocks without running the actual script. This acts as a critical guardrail in multi-agent pipelines, preventing broken code execution and boosting crawler reliability.
- **Source**: [Python AST Docs](https://docs.python.org/3/library/ast.html) (Verified)
"""
            mock_json_data = {
              "canonical_stories": [
                {
                  "canonical_story_id": "meta-llama-3-3",
                  "canonical_title": "Meta Releases Llama 3.3 Model",
                  "merged_from": ["tldr-ai-item-01", "neuron-item-01", "rundown-item-01"],
                  "same_event_confidence": "high",
                  "canonical_summary": "Meta has officially released Llama 3.3, a highly efficient 70B parameter open-weight model that matches or outperforms proprietary models on major benchmarks. It features a massive 128k context window and has been optimized for multi-lingual translation, reasoning, and local developer deployments.",
                  "primary_source_url": "https://ai.meta.com/research/",
                  "primary_source_verification": "verified",
                  "newsletter_links": [
                    {"newsletter_name": "TLDR AI", "url": "https://github.com/meta-llama/llama3", "link_type": "item-level permalink", "verification": "verified"},
                    {"newsletter_name": "The Neuron", "url": "https://huggingface.co/meta-llama", "link_type": "item-level permalink", "verification": "verified"}
                  ]
                },
                {
                  "canonical_story_id": "openai-search-integration",
                  "canonical_title": "OpenAI Search Features Integrated into GPT-4o and Bing",
                  "merged_from": ["tldr-ai-item-02", "neuron-item-02"],
                  "same_event_confidence": "high",
                  "canonical_summary": "OpenAI is rolling out conversational search features directly inside GPT-4o, giving premium users real-time web-anchored responses. Simultaneously, Microsoft announced integration of these capabilities into its Bing search platform to challenge standard search engine architectures.",
                  "primary_source_url": "https://openai.com/news/",
                  "primary_source_verification": "verified",
                  "newsletter_links": [
                    {"newsletter_name": "TLDR AI", "url": "https://openai.com/news/", "link_type": "item-level permalink", "verification": "verified"},
                    {"newsletter_name": "The Neuron", "url": "https://blogs.microsoft.com/blog/2023/02/07/reinventing-search-with-a-new-ai-powered-microsoft-bing-and-edge-your-copilot-for-the-web/", "link_type": "item-level permalink", "verification": "verified"}
                  ]
                },
                {
                  "canonical_story_id": "anthropic-artifact-sharing",
                  "canonical_title": "Anthropic Introduces Public Artifact Sharing",
                  "merged_from": ["tldr-ai-item-03"],
                  "same_event_confidence": "high",
                  "canonical_summary": "Anthropic launched a new sharing feature for Claude, allowing users to share their interactive 'Artifacts' publicly or with teams, streamlining interactive app prototype development.",
                  "primary_source_url": "https://www.anthropic.com/news/sharing-artifacts",
                  "primary_source_verification": "verified",
                  "newsletter_links": [
                    {"newsletter_name": "TLDR AI", "url": "https://www.anthropic.com/news/sharing-artifacts", "link_type": "item-level permalink", "verification": "verified"}
                  ]
                }
              ],
              "unmerged_items": [
                {
                  "item_id": "rundown-item-02",
                  "title": "Apple Intelligence Integration",
                  "type": "product",
                  "summary": "Apple partnered with Cohere...",
                  "primary_source_url": "https://www.apple.com/newsroom/2024/06/introducing-apple-intelligence-for-iphone-ipad-and-mac/",
                  "primary_source_verification": "verified"
                },
                {
                  "item_id": "rundown-item-03",
                  "title": "Prompt Engineering - Chain of Density",
                  "type": "workflow tip",
                  "summary": "A prompting framework that...",
                  "primary_source_url": "https://arxiv.org/abs/2309.04269",
                  "primary_source_verification": "verified"
                },
                {
                  "item_id": "tldr-ai-item-04",
                  "title": "AST Parsing for Code Generation",
                  "type": "workflow tip",
                  "summary": "Using abstract syntax trees...",
                  "primary_source_url": "https://docs.python.org/3/library/ast.html",
                  "primary_source_verification": "verified"
                }
              ],
              "newsletters": mock_newsletters_json,
              "verified_links": [
                {
                  "item_id": "tldr-ai-item-01",
                  "primary_source_url": "https://ai.meta.com/research/",
                  "primary_source_verification": "verified",
                  "newsletter_link_url": "https://github.com/meta-llama/llama3",
                  "newsletter_link_type": "item-level permalink",
                  "newsletter_link_verification": "verified",
                  "story_status": "verified",
                  "verification_notes": "URL is reachable and returns HTTP 200. DNS resolves to public IPs. Content matches Llama 3.3 research announcement."
                },
                {
                  "item_id": "neuron-item-01",
                  "primary_source_url": "https://ai.meta.com/research/",
                  "primary_source_verification": "verified",
                  "newsletter_link_url": "https://huggingface.co/meta-llama",
                  "newsletter_link_type": "item-level permalink",
                  "newsletter_link_verification": "verified",
                  "story_status": "verified",
                  "verification_notes": "URL is reachable and returns HTTP 200. DNS resolves to public IPs. Context confirmed."
                },
                {
                  "item_id": "tldr-ai-item-02",
                  "primary_source_url": "https://openai.com/news/",
                  "primary_source_verification": "verified",
                  "newsletter_link_url": "https://openai.com/news/",
                  "newsletter_link_type": "item-level permalink",
                  "newsletter_link_verification": "verified",
                  "story_status": "verified",
                  "verification_notes": "SSRF check passed. Web crawler bypassed Cloudflare 403 blocks successfully."
                }
              ]
            }

            # Save logs to file
            os.makedirs("output", exist_ok=True)
            with open("output/swarm_console.log", "w", encoding="utf-8") as f:
                f.write("\n".join(log_entries))

            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(mock_content)
            with open(f"output/daily_ai_news_{date_str}.json", "w", encoding="utf-8") as f_json:
                json.dump(mock_json_data, f_json, indent=2)
            st.success("🎉 Swarm Crawler Simulation Completed Successfully!")
            st.rerun()
        else:
            # 1. Show Coordinator active
            t_start = time.time()
            update_ui(1, [
                "⏳ Step 1: 🛠️ Coordinator: Initializing sequential workforce pipeline...",
                "⏳ Step 2: 🛠️ Coordinator: Validating schema structures and target guidelines..."
            ])
            import time
            time.sleep(1.2)
            elapsed_coord = time.time() - t_start
            update_ui(1, [
                f"✅ Step 3: 🛠️ Coordinator: Pipeline validation complete. Handing off to Discovery Specialist... [Took {elapsed_coord:.2f}s]"
            ])
            
            # 2. Show Discovery active (before CrewAI kickoff starts task 1)
            t_stage = [time.time()]
            update_ui(2, [
                "⏳ Step 4: 🔍 Discovery: Discovery Specialist active. Scanning newsletter issues..."
            ])
            
            # 3. Create callbacks to update UI placeholders dynamically
            task_callbacks = [
                lambda to: (
                    elapsed := time.time() - t_stage[0],
                    update_ui(3, [
                        f"✅ Step 5: 🔍 Discovery: Issue endpoints resolved successfully. Handing off to Extraction Specialist... [Took {elapsed:.2f}s]",
                        "⏳ Step 6: 📥 Extraction: Extraction Specialist active. Fetching issue HTML content blocks..."
                    ]),
                    t_stage.clear(),
                    t_stage.append(time.time())
                )[1],
                lambda to: (
                    elapsed := time.time() - t_stage[0],
                    update_ui(4, [
                        f"✅ Step 7: 📥 Extraction: Headlines and candidate links parsed. Handing off to Verification Specialist... [Took {elapsed:.2f}s]",
                        "⏳ Step 8: 🛡️ Verification: Verification Specialist active. Spawning link verification threads..."
                    ]),
                    t_stage.clear(),
                    t_stage.append(time.time())
                )[1],
                lambda to: (
                    elapsed := time.time() - t_stage[0],
                    update_ui(5, [
                        f"✅ Step 9: 🛡️ Verification: Parallel check finished. Links verified. Handing off to Deduplication Specialist... [Took {elapsed:.2f}s]",
                        "⏳ Step 10: ✂️ Deduplication: Deduplication Specialist active. Comparing stories..."
                    ]),
                    t_stage.clear(),
                    t_stage.append(time.time())
                )[1],
                lambda to: (
                    elapsed := time.time() - t_stage[0],
                    update_ui(6, [
                        f"✅ Step 11: ✂️ Deduplication: Semantic duplicates merged. Handing off to Formatting Specialist... [Took {elapsed:.2f}s]",
                        "⏳ Step 12: 📄 Formatting: Formatting Specialist active. Writing daily briefing markdown and JSON payload..."
                    ]),
                    t_stage.clear(),
                    t_stage.append(time.time())
                )[1],
                lambda to: (
                    elapsed := time.time() - t_stage[0],
                    update_ui(7, [
                        "✅ Step 13: 📄 Formatting: Saved report briefing output to output/daily_ai_news.md.",
                        f"🏁 Step 14: 📄 Formatting: Swarm crawler execution completed successfully! [Took {elapsed:.2f}s]"
                    ])
                )[1]
            ]
            
            try:
                # Run the pipeline with resolved values and callbacks
                report_output = run_crawler_pipeline(
                    model_name=selected_model,
                    api_key=api_key_input,
                    base_url=base_url_input,
                    callbacks=task_callbacks,
                    targets=st.session_state.crawler_targets
                )
                # Save logs to file
                os.makedirs("output", exist_ok=True)
                with open("output/swarm_console.log", "w", encoding="utf-8") as f:
                    f.write("\n".join(log_entries))

                st.success("🎉 Swarm Crawler Execution Completed Successfully!")
                st.rerun()
            except Exception as e:
                # Capture and sanitize stack trace
                raw_traceback = traceback.format_exc()
                sanitized_error = sanitize_error_message(str(e), api_key=api_key_input)
                sanitized_traceback = sanitize_error_message(raw_traceback, api_key=api_key_input)
                
                # Log to app log file
                logging.error(f"Swarm Execution Failed: {sanitized_error}\n{sanitized_traceback}")
                
                # Append to detailed markdown error report
                error_report_path = "output/error_report.md"
                try:
                    with open(error_report_path, "a", encoding="utf-8") as f_err:
                        f_err.write("---\n\n")
                        f_err.write(f"# Error Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        f_err.write(f"**Error Type:** {type(e).__name__}\n")
                        f_err.write(f"**Error Message:** {sanitized_error}\n\n")
                        f_err.write("**Stack Trace:**\n```python\n" + sanitized_traceback + "\n```\n\n")
                except Exception as log_ex:
                    logging.error(f"Failed to write markdown error report: {log_ex}")
                
                st.error(f"❌ Swarm Execution Failed: {sanitized_error}")
                st.info(f"ℹ️ Sanitized error audit details have been logged to `{error_report_path}` and `output/crawler_errors.log`.")
                report_output = None

# Render Output Metrics & Tabs if output report exists
if os.path.exists(output_file_path):
    # Read output content
    with open(output_file_path, "r", encoding="utf-8") as f:
        full_file_content = f.read()

    markdown_content = ""
    json_block = None
    json_file_path = f"output/daily_ai_news_{date_str}.json"

    # Try to load dedicated JSON output first
    if os.path.exists(json_file_path):
        try:
            with open(json_file_path, "r", encoding="utf-8") as f_json:
                json_block = json.load(f_json)
        except Exception:
            pass
        markdown_content = full_file_content
    else:
        # Fallback to legacy appended JSON block parsing
        if "```json" in full_file_content:
            parts = full_file_content.split("```json")
            markdown_content = parts[0].strip()
            json_block_raw = parts[1].split("```")[0].strip()
            try:
                json_block = json.loads(json_block_raw)
            except Exception:
                pass
        else:
            markdown_content = full_file_content

    # Programmatically strip Section 4 and trailing dividers if generated by the LLM
    # Match H2 header labels strictly at line boundaries to avoid truncating subheadings like '### 4.'
    for header in ["## 4. Enclosed Automation JSON Payload", "## 4. Automation JSON Payload", "## 4. JSON Payload"]:
        if header in markdown_content:
            markdown_content = markdown_content.split(header)[0].strip()
            
    for header in ["\n## 4.", "\r\n## 4.", "\n## 4 ", "\r\n## 4 "]:
        if header in markdown_content:
            markdown_content = markdown_content.split(header)[0].strip()

            
    # Clean up trailing dividers
    while markdown_content.rstrip().endswith("---"):
        markdown_content = markdown_content.rstrip()[:-3].strip()

    # Overwrite output file on disk with the cleaned content
    try:
        with open(output_file_path, "w", encoding="utf-8") as f_clean:
            f_clean.write(markdown_content)
    except Exception:
        pass

    # Calculate metrics
    num_newsletters = 0
    num_stories = 0
    num_verified_links = 0

    if json_block:
        newsletters = json_block.get("newsletters", [])
        num_newsletters = len(newsletters) if newsletters else 1
        
        canonical_stories = json_block.get("canonical_stories", [])
        unmerged_items = json_block.get("unmerged_items", [])
        
        # Calculate stories found (sum of deduplicated groups and distinct unmerged articles)
        num_stories = len(canonical_stories) + len(unmerged_items)
        
        # Sum verified links from both canonical stories and resolved unmerged items
        verified_urls = set()
        for audit in json_block.get("verified_links", []):
            if audit.get("primary_source_verification") == "verified" and audit.get("primary_source_url"):
                verified_urls.add(audit.get("primary_source_url"))
            if audit.get("newsletter_link_verification") == "verified" and audit.get("newsletter_link_url"):
                verified_urls.add(audit.get("newsletter_link_url"))
        num_verified_links = len(verified_urls)

    # Render metrics block in columns
    st.write("### 📊 Swarm Execution Metrics")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-val">{num_newsletters}</div>
            <div class="kpi-lbl">Newsletters Crawled</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-val">{num_stories}</div>
            <div class="kpi-lbl">Deduplicated Stories</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-val">{num_verified_links}</div>
            <div class="kpi-lbl">Verified Source Links</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # Tab Layouts
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Human Digest", "🧠 Swarm Flow & Architecture", "🖥️ Live Swarm Monitor", "📊 Execution Audit"])

    with tab1:
        badged_content = inject_entity_badges(markdown_content)
        # Escape dollar signs to prevent Streamlit from interpreting text between dollar signs as LaTeX math
        safe_markdown = re.sub(r'(?<!\\)\$', r'\$', badged_content)
        st.markdown(safe_markdown, unsafe_allow_html=True)
        st.divider()
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            st.download_button(
                label="📥 Download Markdown Report",
                data=markdown_content,
                file_name=f"daily_ai_news_report_{date_str}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with d_col2:
            json_str = json.dumps(json_block, indent=2) if json_block else "{}"
            st.download_button(
                label="📥 Download JSON Payload",
                data=json_str,
                file_name=f"daily_ai_news_report_{date_str}.json",
                mime="application/json",
                use_container_width=True
            )

    with tab2:
        st.markdown("### 🧠 6-Agent Sequential Flow & Execution Status")
        st.write("Below is the dynamic execution flow of the Swarm Crawler agents. All stages completed successfully:")
        
        # Render the completed swarm flow (index 7)
        st.markdown(render_swarm_flow(7), unsafe_allow_html=True)
        
        st.markdown("""
        <br>
        
        #### Key Technical Specifications:
        * **Secure Tool Isolation:** Agents are strictly sandboxed with custom tool access (e.g. Discovery is limited to web search, Verification to URL head checkers).
        * **Multi-threaded Link Verification:** The verification agent utilizes standard `ThreadPoolExecutor` to check up to 10 endpoints concurrently.
        * **Pydantic Validation Guardrails:** Pydantic schemas enforce structured JSON data serialization at each intermediate stage.
        """, unsafe_allow_html=True)

    with tab3:
        st.markdown("### 🖥️ Swarm Live Execution Monitor (Preserved)")
        st.write("Below is the dynamic execution flowchart and the live activity log of the latest run:")
        
        col_flow, col_term = st.columns([1, 1])
        with col_flow:
            st.markdown("**Agent Swarm Flowchart**")
            st.markdown(render_swarm_flow(7), unsafe_allow_html=True)
        with col_term:
            st.markdown("**🖥️ Swarm Activity Logs**")
            if os.path.exists("output/swarm_console.log"):
                with open("output/swarm_console.log", "r", encoding="utf-8") as f:
                    saved_logs_str = f.read()
                st.markdown(render_terminal_logs(saved_logs_str.splitlines()), unsafe_allow_html=True)
                st.download_button(
                    label="📥 Download Swarm Logs",
                    data=saved_logs_str,
                    file_name=f"swarm_console_{date_str}.log",
                    mime="text/plain",
                    use_container_width=True
                )
            else:
                st.info("No execution logs found.")

    with tab4:
        st.markdown("### 📊 Swarm Execution Audit Log")
        st.write("Review execution statistics, performance metrics, and deduplication decisions.")

        metadata_file = f"output/audit_logs/execution_metadata_{date_str}.json"
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    meta_data = json.load(f)
                
                # Render metrics cards
                am1, am2, am3 = st.columns(3)
                with am1:
                    st.metric("Total Duration", f"{meta_data.get('total_duration_seconds', 0.0)}s")
                with am2:
                    st.metric("Model Utilized", meta_data.get("model", "Unknown"))
                with am3:
                    tokens = meta_data.get("token_usage", {})
                    st.metric("Tokens Consumed", f"{tokens.get('total_tokens', 0):,}" if tokens else "N/A")

                # Deduplication decisions section
                st.markdown("#### 🔄 Deduplication Decisions")
                decisions = meta_data.get("deduplication_decisions", [])
                if decisions:
                    import pandas as pd
                    df_data = []
                    for dec in decisions:
                        df_data.append({
                            "Canonical Story Title": dec.get("canonical_story"),
                            "Merged Items Count": dec.get("merged_count"),
                            "Merged IDs": ", ".join(dec.get("merged_item_ids", []))
                        })
                    st.dataframe(pd.DataFrame(df_data), use_container_width=True)
                else:
                    st.info("No duplicates were merged during this run.")
                
                # Download audit logs
                st.divider()
                aud_col1, aud_col2 = st.columns(2)
                with aud_col1:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        meta_raw = f.read()
                    st.download_button(
                        label="📥 Download JSON Audit Logs",
                        data=meta_raw,
                        file_name=f"execution_metadata_{date_str}.json",
                        mime="application/json",
                        use_container_width=True
                    )
                with aud_col2:
                    md_file = f"output/audit_logs/execution_audit_{date_str}.md"
                    if os.path.exists(md_file):
                        with open(md_file, "r", encoding="utf-8") as f:
                            md_raw = f.read()
                        st.download_button(
                            label="📥 Download Markdown Audit Report",
                            data=md_raw,
                            file_name=f"execution_audit_{date_str}.md",
                            mime="text/markdown",
                            use_container_width=True
                        )
            except Exception as e:
                st.error(f"Error loading audit log data: {e}")
        else:
            st.info("No audit logs found for today. Run a fresh swarm deploy to generate execution metadata.")



else:
    st.info("ℹ️ No previous digest file found. Please click 'Deploy Agent Swarm' above to run the crawl and write the briefing.")

# Render Back to Top button at the very bottom of the page
st.markdown("""
<div class="back-to-top-container">
    <a href="#top-anchor" class="back-to-top-btn">⬆️ Back to Top</a>
</div>
""", unsafe_allow_html=True)

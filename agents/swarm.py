import os
from datetime import datetime
from typing import Union, List, Dict, Any, Optional, Callable
from crewai import Agent, Task, Crew, Process, LLM

# Import schemas and tools from the modular layout
from core.schemas import (
    DiscoveryAgentOutput,
    ExtractionAgentOutput,
    VerificationAgentOutput,
    DeduplicationAgentOutput
)
from utils.web_tools import (
    search_web,
    fetch_url,
    verify_links_in_bulk,
    calculate_semantic_similarity
)

def create_crawler_crew(
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    callbacks: Optional[List[Callable[[Any], Any]]] = None,
    targets: Optional[List[Dict[str, str]]] = None
) -> Crew:
    """
    Assembles and configures the 6-agent crawling crew with dynamic LLM configuration.

    Args:
        model_name: The target model provider and ID (e.g. 'gemini/gemini-flash-lite-latest').
        api_key: The authenticated API key for requests.
        base_url: Optional custom base gateway URL.
        callbacks: Optional list of UI callback update hooks for execution milestones.
        targets: Optional list of dictionaries containing 'name' and 'url' configuration keys.

    Returns:
        A fully constructed CrewAI Crew instance ready for execution.
    """
    import utils.web_tools as web_tools
    if targets:
        web_tools.set_dynamic_targets(targets)
        
    # Use environment variables as default fallbacks
    resolved_model = model_name or os.getenv("MODEL_NAME", "gemini/gemini-flash-lite-latest")
    
    # Resolve API Key
    resolved_key = api_key
    if not resolved_key:
        if resolved_model.startswith("gemini/"):
            resolved_key = os.getenv("GEMINI_API_KEY")
        elif resolved_model.startswith("anthropic/"):
            resolved_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            resolved_key = os.getenv("OPENAI_API_KEY")
            
    if not resolved_key:
        raise ValueError(
            f"API Key not found for model '{resolved_model}'. "
            "Please ensure you configure the correct API Key in your sidebar or in the .env file."
        )

    # Set the api key for web tools (e.g. for search tool if needed)
    web_tools.set_api_key(resolved_key)

    # Resolve Base URL
    resolved_url = base_url if (base_url and base_url.strip()) else os.getenv("API_BASE_URL")

    # Initialize LLM with custom model, base url, and credentials
    llm_params = {
        "model": resolved_model,
        "temperature": 0.1,
        "api_key": resolved_key
    }
    if resolved_url:
        llm_params["base_url"] = resolved_url

    llm = LLM(**llm_params)

    # ==========================================
    # 1. AGENTS DEFINITION
    # ==========================================

    coordinator = Agent(
        role="Pipeline Coordinator",
        goal="Orchestrate news crawling pipeline following strict routing order and constraints.",
        backstory=(
            "You are the pipeline coordinator. Order of specialists: 1.Discovery, 2.Extraction, 3.Verification, "
            "4.Deduplication, 5.Formatting. Rules: Never invent URLs. Clickable Markdown links in final output. "
            "No bare URLs. Deduplicate only after full extraction. Preserve reading order."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        tools=[]
    )

    discovery_agent = Agent(
        role="Discovery Specialist",
        goal="Identify the latest direct issue URLs for TLDR AI, The Neuron, and The Rundown AI.",
        backstory=(
            "You are the Discovery Agent. Find only the latest single issue URL for the specified newsletters. "
            "Verify direct issue paths. Do not extract story contents. Do not guess or invent URLs. Return a JSON dictionary. "
            "Your output must consist ONLY of raw, clean JSON starting with { and ending with }. "
            "Do NOT wrap the JSON in markdown code blocks (do NOT use triple backticks like ```json ... ```)."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        tools=[search_web]
    )

    extraction_agent = Agent(
        role="Extraction Specialist",
        goal="Extract content blocks in reading order from fetched newsletters, labeling entity types.",
        backstory=(
            "You are the Extraction Agent. You MUST fetch the content of all discovered newsletter URLs. "
            "To do this, call the fetch_url tool passing a JSON list of ALL discovered newsletter URLs (e.g. `[\"url1\", \"url2\", \"url3\"]`) as a single argument. "
            "Do NOT make separate fetch_url calls for each URL. Make exactly one fetch_url call with the list of URLs. "
            "Extract headlines, summaries, and candidate links from the returned combined content for all newsletters. "
            "CRITICAL: The summary for each item must be a detailed, high-quality description that is exactly 3-4 full lines or sentences long. "
            "Exclude ads/sponsor text. Label primary entity types: model, product, company announcement, tool, etc. "
            "Preserve reading order indices. You must return your output as a single JSON dictionary containing "
            "the 'extracted_newsletters' key wrapping the list of extracted newsletters. "
            "Your output must consist ONLY of raw, clean JSON starting with { and ending with }. "
            "Do NOT wrap the JSON in markdown code blocks (do NOT use triple backticks like ```json ... ```)."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        tools=[fetch_url]
    )

    verification_agent = Agent(
        role="Verification Specialist",
        goal="Verify extracted links and map their authentication statuses.",
        backstory=(
            "You are the Verification Agent. Take candidate links and pass them to the verify_links_in_bulk tool. "
            "Do not run sequential searches. Directly map verified outputs back to their item schemas. "
            "Your output must consist ONLY of raw, clean JSON starting with { and ending with }. "
            "Do NOT wrap the JSON in markdown code blocks (do NOT use triple backticks like ```json ... ```)."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        tools=[verify_links_in_bulk]
    )

    deduplication_agent = Agent(
        role="Deduplication Specialist",
        goal="Merge items referring to identical events with high confidence, keeping others separate.",
        backstory=(
            "You are the Deduplication Agent. Merge items representing the exact same announcement, release, or change. "
            "Compare the titles, summaries, and source URLs across all newsletters to detect duplicate stories (for example: OpenAI Hugging Face sandbox escape, Llama 3.3 release, or the open weights letter). "
            "Never merge different products. Only merge same entity type/named entity. "
            "Use the 'Calculate Semantic Similarity' tool to compute semantic similarities between story summaries to inform your merging decisions. "
            "Your output must consist ONLY of raw, clean JSON starting with { and ending with }. "
            "Do NOT wrap the JSON in markdown code blocks (do NOT use triple backticks like ```json ... ```)."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        tools=[calculate_semantic_similarity]
    )

    formatter_agent = Agent(
        role="Formatting Specialist",
        goal="Convert structured verified outputs into clean human-readable Markdown.",
        backstory=(
            "You are the Formatter Agent. Convert outputs into polished Markdown. Every verifiable link must be a clickable Markdown "
            "link of the format [label](https://url). No bare URLs. Keep stories separate. Do NOT append any JSON block at the end."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        tools=[]
    )

    # ==========================================
    # 2. TASKS DEFINITION
    # ==========================================

    targets_list_str = "\n".join([f"- {t['name']}" for t in targets]) if targets else "- TLDR AI\n- The Neuron\n- The Rundown AI"
    discovery_task = Task(
        description=(
            f"Search the web using search_web to find the direct latest issue URL for:\n"
            f"{targets_list_str}\n"
            f"Fill out and return Discovery Schema.\n"
            f"IMPORTANT: You MUST use the exact URLs returned by the `search_web` tool as the `issue_url` in the output schema. "
            f"Do NOT invent, construct, guess, or modify the URLs (do NOT append dates or sub-paths like `/p/` or `/p/latest-issue`). Use the search tool's URL outputs verbatim.\n"
            f"IMPORTANT: Output ONLY a raw JSON string matching the expected schema. "
            f"Do NOT wrap it in markdown code blocks or any other formatting."
        ),
        expected_output="Discovered newsletter issue URLs matching the Discovery Schema.",
        agent=discovery_agent,
        output_pydantic=DiscoveryAgentOutput,
        callback=callbacks[0] if (callbacks and len(callbacks) > 0) else None
    )

    extraction_task = Task(
        description=(
            "Fetch the content of the discovered newsletter URLs using fetch_url.\n"
            "CRITICAL: Call fetch_url exactly ONCE passing a JSON array of ALL discovered newsletter URLs as the `url` argument. "
            "For example: `[\"https://tldr.tech/ai/2026-07-27\", \"https://theneuron.ai/newsletter/2026-07-22\", \"https://www.therundown.ai/p/anthropic-opus-5-surprise\"]`.\n"
            "Do NOT call fetch_url multiple times. Pass all URLs in a single tool call.\n"
            "From the returned combined content, extract headlines, summaries, evidence snippets, and candidate links in exact reading order for each newsletter. "
            "CRITICAL SUMMARY INSTRUCTION: For each item, write a highly detailed summary that is exactly 3 to 4 full sentences (or 3-4 lines) long. Ensure it provides adequate context, explanation of the technology/event, and its overall significance. Do NOT write short single-sentence summaries.\n"
            "Label items with primary entity types (e.g., model, product, tool). Skip ads.\n\n"
            "STRICT OUTPUT STRUCTURE: Output your response as a single valid JSON dictionary matching the Extraction Schema. "
            "It must start with { and contain 'extracted_newsletters' as the root key wrapping the array of extracted newsletters.\n"
            "IMPORTANT: Output ONLY a raw JSON string matching the expected schema. "
            "Do NOT wrap it in markdown code blocks or any other formatting."
        ),
        expected_output="Substantive news blocks extracted in reading order matching the Extraction Schema.",
        agent=extraction_agent,
        context=[discovery_task],
        output_pydantic=ExtractionAgentOutput,
        callback=callbacks[1] if (callbacks and len(callbacks) > 1) else None
    )

    verification_task = Task(
        description=(
            "Collect candidate links from the extracted items. Call verify_links_in_bulk to check their status. "
            "Map results back to each item. Determine primary source verification statuses. Return Verification Schema.\n"
            "IMPORTANT: Output ONLY a raw JSON string matching the expected schema. "
            "Do NOT wrap it in markdown code blocks or any other formatting."
        ),
        expected_output="Verified link data matching the Verification Schema.",
        agent=verification_agent,
        context=[extraction_task],
        output_pydantic=VerificationAgentOutput,
        callback=callbacks[2] if (callbacks and len(callbacks) > 2) else None
    )

    deduplication_task = Task(
        description=(
            "Compare all extracted and verified items. Merge items with high confidence referring to the same underlying event, announcement, or release "
            "of the same entity type and name (e.g. Meta Drops Llama 3.3, Llama 3.3 release, etc., or the OpenAI/Hugging Face sandbox escape, or the open letter on open weights). "
            "Check titles, summaries, and source URLs to identify matches, even if they use different source URLs or headlines.\n"
            "Return Deduplication Schema.\n"
            "IMPORTANT: Output ONLY a raw JSON string matching the expected schema. "
            "Do NOT wrap it in markdown code blocks or any other formatting."
        ),
        expected_output="Consolidated canonical stories and unmerged separate items matching Deduplication Schema.",
        agent=deduplication_agent,
        context=[extraction_task, verification_task],
        output_pydantic=DeduplicationAgentOutput,
        callback=callbacks[3] if (callbacks and len(callbacks) > 3) else None
    )

    date_str = datetime.now().strftime("%Y-%m-%d")
    formatting_task = Task(
        description=(
            "Generate the final daily newsletter report from the preceding stages.\n"
            "Format the report using markdown H2 headings strictly for the four sections:\n"
            "## Section 1: Newsletter Issues Processed\n"
            "For each processed newsletter, list it as a bullet point exactly in the format: "
            "'- **[Newsletter Name](URL)** (Published: YYYY-MM-DD) - [Read Issue](URL)'. Ensure the links are clean markdown and never bare URLs.\n"
            "## Section 2: Deduplicated Canonical Stories\n"
            "For each canonical story, report the details here using an H3 heading prefixed with an emoji (e.g. '### 📢 Title') WITHOUT any numbering (do NOT write '1.', '2.', etc. in the heading). Include the canonical summary, primary source, and the specific newsletter sources they were merged from.\n"
            "## Section 3: Extracted Items in Reading Order\n"
            "For each extracted item, report the details here using an H3 heading prefixed with an emoji (e.g. '### 📰 Title') WITHOUT any numbering. Resolve and report ONLY the unmerged/unique items here (those that were NOT merged into any canonical story in the deduplication stage). "
            "For each item, output exactly the following bullet points on separate lines:\n"
            "- **Entity Type**: [entity type]\n"
            "- **Summary**: [comprehensive summary]\n"
            "- **Verified Source Links**:\n"
            "  - [Source Label](URL)\n"
            "Do NOT include any items here that were duplicates/merged under Section 2.\n"
            "## Section 4: Tips and Workflows\n"
            "For each extracted item from the extraction stage whose type is 'workflow tip', list it here using an H3 heading prefixed with an emoji (e.g. '### 💡 Title') WITHOUT any numbering. Include a comprehensive, detailed, and high-quality summary of the tip that is exactly 3-4 full lines or sentences long. It must explain the core concept, its practical application, the specific benefits it offers to developers/AI engineers, and actionable steps or code-level suggestions on how to implement it. Include the primary source and the newsletter source it came from.\n"
            "Do NOT write any header about JSON payload, and do NOT append any JSON block at all. Output only clean human-readable Markdown with exactly these four H2 sections.\n"
            f"Ensure all links are formatted as clickable Markdown [label](https://url). No bare URLs. Save to output/daily_ai_news_{date_str}.md."
        ),
        expected_output="A beautiful human-readable report with exactly 4 H2 sections (using 'Section X:' naming and unnumbered emoji-prefixed H3 headings for stories) saved to output.",
        agent=formatter_agent,
        context=[extraction_task, verification_task, deduplication_task],
        output_file=f"output/daily_ai_news_{date_str}.md",
        callback=callbacks[4] if (callbacks and len(callbacks) > 4) else None
    )

    # Assemble the sequential pipeline
    return Crew(
        agents=[
            coordinator,
            discovery_agent,
            extraction_agent,
            verification_agent,
            deduplication_agent,
            formatter_agent
        ],
        tasks=[
            discovery_task,
            extraction_task,
            verification_task,
            deduplication_task,
            formatting_task
        ],
        process=Process.sequential,
        max_rpm=10,  # Limits the crew's total requests per minute to stay under the free tier rate limits
        verbose=True
    )

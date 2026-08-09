#!/usr/bin/env python3
"""
Orchestration Script for the Daily AI News Web Crawler.
CLI Entrypoint for executing the modular multi-agent swarm pipeline.
"""

import os
import sys
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
from core.pipeline import run_crawler_pipeline

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🕷️ STARTING THE DAILY AI NEWS MULTI-AGENT WEB CRAWLER")
    print("="*60 + "\n")

    # Run the default configured crew pipeline
    final_report = run_crawler_pipeline()

    date_str = datetime.now().strftime("%Y-%m-%d")
    print("\n" + "="*60)
    print("🎉 PIPELINE WORK COMPLETED SUCCESSFULLY!")
    print("="*60 + "\n")
    print(f"The final crawled newsletter has been formatted and saved to 'output/daily_ai_news_{date_str}.md'.")
    print("\nPreview of the formatted output:\n")
    print(final_report)

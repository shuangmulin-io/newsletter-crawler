import os
import json
import logging
from typing import List, Dict, Any, Optional, Callable
from core.pipeline import run_crawler_pipeline
from utils.cache import CacheManager
from models.data_schemas import TargetModel

logger = logging.getLogger(__name__)

class CrawlerService:
    """
    Service layer to coordinate newsletter crawling, caching, and schemas.
    """
    def __init__(self, model_name: str, api_key: str, base_url: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.cache_manager = CacheManager()

    def run(
        self,
        targets: List[Dict[str, str]],
        callbacks: Optional[List[Callable[[Any], Any]]] = None,
        force_fresh: bool = False
    ) -> tuple[dict, str]:
        """
        Executes the crawling pipeline, managing caching, model config, and error reports.

        Args:
            targets: List of targets with name and url.
            callbacks: Callbacks to invoke during different steps.
            force_fresh: Bypass cache if True.

        Returns:
            A tuple of (json_report_dict, markdown_content_str)
        """
        # Validate targets using TargetModel schema
        validated_targets = []
        for t in targets:
            target_model = TargetModel(**t)
            validated_targets.append(target_model.model_dump())

        # Check cache if not forcing a fresh run
        if not force_fresh:
            cached_data = self.cache_manager.load_cached_report(
                validated_targets, self.model_name, self.base_url
            )
            if cached_data:
                logger.info("Cache hit. Returning cached report.")
                markdown_content = cached_data.get("markdown_content", "")
                if not markdown_content:
                    output_file_path, _ = self.cache_manager.get_cache_paths()
                    if os.path.exists(output_file_path):
                        with open(output_file_path, "r", encoding="utf-8") as f:
                            markdown_content = f.read()
                return cached_data, markdown_content

        # Run pipeline
        logger.info("Executing fresh crawl pipeline...")
        markdown_content = run_crawler_pipeline(
            model_name=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            callbacks=callbacks,
            targets=validated_targets
        )
        markdown_content = str(markdown_content)

        # Parse saved json details to return structured dict
        _, json_file_path = self.cache_manager.get_cache_paths()
        json_report = {}
        if os.path.exists(json_file_path):
            try:
                with open(json_file_path, "r", encoding="utf-8") as f:
                    json_report = json.load(f)
            except Exception:
                pass

        # Save to cache with metadata
        json_report["markdown_content"] = markdown_content
        self.cache_manager.save_report(
            report_output=json_report,
            targets=validated_targets,
            model_name=self.model_name,
            base_url=self.base_url,
            markdown_content=markdown_content
        )

        return json_report, markdown_content

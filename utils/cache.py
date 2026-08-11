import os
import json
import hashlib
from datetime import datetime, timedelta

class DiskCache:
    def __init__(self, cache_dir="output/.cache", ttl_hours=4):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_path(self, url: str) -> str:
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.json")
        
    def get(self, url: str):
        cache_path = self._get_cache_path(url)
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time < self.ttl:
                return data["content"]
        except Exception:
            pass
        return None
        
    def set(self, url: str, content: str):
        cache_path = self._get_cache_path(url)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                    "content": content
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

global_disk_cache = DiskCache()

class CacheManager:
    """
    Manage overall execution report cache with hash-based invalidation.
    """
    def __init__(self, cache_dir="output"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def generate_cache_key(self, targets: list, model_name: str, base_url: str = None) -> str:
        # Sort targets by URL for deterministic hashing
        sorted_targets = sorted(targets, key=lambda x: x.get("url", ""))
        cache_data = {
            "targets": sorted_targets,
            "model_name": model_name or "",
            "base_url": base_url or ""
        }
        data_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
        
    def get_cache_paths(self) -> tuple:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_file_path = os.path.join(self.cache_dir, f"daily_ai_news_{date_str}.md")
        json_file_path = os.path.join(self.cache_dir, f"daily_ai_news_{date_str}.json")
        return output_file_path, json_file_path

    def load_cached_report(self, targets: list, model_name: str, base_url: str = None) -> dict:
        _, json_file_path = self.get_cache_paths()
        if not os.path.exists(json_file_path):
            return None
        try:
            with open(json_file_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            
            # Verify cache hash key matches current configuration
            current_key = self.generate_cache_key(targets, model_name, base_url)
            stored_metadata = cached_data.get("cache_metadata", {})
            stored_key = stored_metadata.get("cache_key")
            
            if current_key == stored_key:
                return cached_data
        except Exception:
            pass
        return None

    def save_report(self, report_output: dict, targets: list, model_name: str, base_url: str = None, markdown_content: str = ""):
        output_file_path, json_file_path = self.get_cache_paths()
        cache_key = self.generate_cache_key(targets, model_name, base_url)
        
        cache_metadata = {
            "cache_key": cache_key,
            "generated_at": datetime.now().isoformat(),
            "target_count": len(targets)
        }
        
        # Save JSON with cache metadata
        try:
            report_data = dict(report_output) if isinstance(report_output, dict) else {}
            report_data["cache_metadata"] = cache_metadata
            # Ensure essential keys exist
            if "newsletters" not in report_data:
                report_data["newsletters"] = targets
            
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
                
            if markdown_content:
                with open(output_file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
        except Exception:
            pass


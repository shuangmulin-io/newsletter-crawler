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

import json
import os
from typing import Any, Dict, List, Optional


class Config:
    def __init__(self, path: str = "config.json"):
        self.path = path
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Config file not found: {self.path}")
        with open(self.path, "r") as f:
            self.data = json.load(f)

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def get(self, *keys: str, default: Any = None) -> Any:
        d = self.data
        for key in keys:
            if isinstance(d, dict):
                d = d.get(key)
                if d is None:
                    return default
            else:
                return default
        return d if d is not None else default

    @property
    def threads(self) -> int:
        return int(self.get("general", "threads", default=10))

    @property
    def min_delay(self) -> float:
        return float(self.get("general", "min_delay", default=2.0))

    @property
    def max_delay(self) -> float:
        return float(self.get("general", "max_delay", default=8.0))

    @property
    def visit_duration_min(self) -> int:
        return int(self.get("general", "visit_duration_min", default=5))

    @property
    def visit_duration_max(self) -> int:
        return int(self.get("general", "visit_duration_max", default=30))

    @property
    def timeout(self) -> int:
        return int(self.get("general", "timeout", default=15))

    @property
    def max_retries(self) -> int:
        return int(self.get("general", "max_retries", default=3))

    @property
    def targets(self) -> List[Dict]:
        return self.get("targets", default=[])

    @property
    def proxy_enabled(self) -> bool:
        return bool(self.get("proxies", "enabled", default=False))

    @property
    def proxy_type(self) -> str:
        return str(self.get("proxies", "type", default="http"))

    @property
    def proxy_list(self) -> List[str]:
        return self.get("proxies", "list", default=[])

    @property
    def proxy_file(self) -> Optional[str]:
        return self.get("proxies", "file")

    @property
    def rotating_file(self) -> Optional[str]:
        """Path ke file rotating proxy gateways (rotating.txt)."""
        return self.get("proxies", "rotating_file", default="rotating.txt")

    @property
    def test_proxies(self) -> bool:
        return bool(self.get("proxies", "test_before_use", default=True))

    @property
    def proxy_test_url(self) -> str:
        return str(self.get("proxies", "test_url", default="http://httpbin.org/ip"))

    @property
    def rotate_every_request(self) -> bool:
        return bool(self.get("proxies", "rotate_every_request", default=True))

    @property
    def rotate_ua(self) -> bool:
        return bool(self.get("user_agent", "rotate", default=True))

    @property
    def device_type(self) -> str:
        return str(self.get("user_agent", "device_type", default="desktop"))

    @property
    def referrer_enabled(self) -> bool:
        return bool(self.get("referrers", "enabled", default=True))

    @property
    def referrer_sources(self) -> List[str]:
        return self.get("referrers", "sources", default=[])

    @property
    def scheduler_enabled(self) -> bool:
        return bool(self.get("scheduler", "enabled", default=False))

    @property
    def scheduler_mode(self) -> str:
        return str(self.get("scheduler", "mode", default="interval"))

    @property
    def scheduler_interval(self) -> int:
        return int(self.get("scheduler", "interval_minutes", default=60))

    @property
    def daily_time(self) -> str:
        return str(self.get("scheduler", "daily_time", default="09:00"))

    @property
    def daily_runs(self) -> int:
        return int(self.get("scheduler", "daily_runs", default=10))

    @property
    def run_duration(self) -> int:
        return int(self.get("scheduler", "run_duration_minutes", default=30))

    @property
    def stats_save(self) -> bool:
        return bool(self.get("statistics", "save_to_file", default=True))

    @property
    def stats_format(self) -> str:
        return str(self.get("statistics", "file_format", default="csv"))

    @property
    def stats_path(self) -> str:
        return str(self.get("statistics", "export_path", default="reports"))

    @property
    def log_level(self) -> str:
        return str(self.get("logging", "level", default="INFO"))

    @property
    def log_file(self) -> str:
        return str(self.get("logging", "file", default="logs/bot.log"))

    @property
    def log_max_size(self) -> int:
        return int(self.get("logging", "max_size_mb", default=10))

    @property
    def log_backup_count(self) -> int:
        return int(self.get("logging", "backup_count", default=5))

    def update_targets(self, targets: List[Dict]):
        self.data["targets"] = targets
        self.save()

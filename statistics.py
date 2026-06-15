import csv
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class VisitRecord:
    target_name: str
    url: str
    proxy: str
    user_agent: str
    status: str
    response_time: float
    response_code: int
    timestamp: float
    error: str = ""
    pages_visited: int = 1
    ads_found: int = 0
    ads_clicked: int = 0


@dataclass
class AdClickRecord:
    target_name: str
    page_url: str
    ad_url: str
    ad_type: str
    ad_network: str
    response_code: int
    response_time: float
    timestamp: float
    success: bool
    error: str = ""


@dataclass
class Stats:
    total_visits: int = 0
    successful: int = 0
    failed: int = 0
    total_response_time: float = 0.0
    start_time: float = field(default_factory=time.time)
    total_pages_visited: int = 0
    total_ads_found: int = 0
    total_ads_clicked: int = 0
    ad_clicks_success: int = 0
    ad_clicks_failed: int = 0
    target_stats: Dict[str, dict] = field(default_factory=dict)
    ad_type_stats: Dict[str, int] = field(default_factory=dict)
    ad_network_stats: Dict[str, int] = field(default_factory=dict)
    recent_records: List[VisitRecord] = field(default_factory=list)
    recent_ad_clicks: List[AdClickRecord] = field(default_factory=list)
    max_recent: int = 1000

    @property
    def avg_response_time(self) -> float:
        if self.total_visits == 0:
            return 0.0
        return self.total_response_time / self.total_visits

    @property
    def success_rate(self) -> float:
        if self.total_visits == 0:
            return 0.0
        return (self.successful / self.total_visits) * 100

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def visits_per_minute(self) -> float:
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return (self.total_visits / elapsed) * 60

    @property
    def ads_per_visit(self) -> float:
        if self.total_visits == 0:
            return 0.0
        return self.total_ads_clicked / self.total_visits

    @property
    def ad_click_rate(self) -> float:
        if self.total_ads_found == 0:
            return 0.0
        return (self.total_ads_clicked / self.total_ads_found) * 100


class StatisticsManager:
    def __init__(self, config):
        self.config = config
        self.stats = Stats()
        self.lock = threading.Lock()
        self.running = False

    def record_visit(self, record: VisitRecord):
        with self.lock:
            self.stats.total_visits += 1
            self.stats.total_response_time += record.response_time
            self.stats.total_pages_visited += record.pages_visited
            self.stats.total_ads_found += record.ads_found
            self.stats.total_ads_clicked += record.ads_clicked

            if record.status == "success":
                self.stats.successful += 1
            else:
                self.stats.failed += 1

            if record.target_name not in self.stats.target_stats:
                self.stats.target_stats[record.target_name] = {
                    "total": 0, "success": 0, "fail": 0,
                    "ads_found": 0, "ads_clicked": 0,
                }
            t = self.stats.target_stats[record.target_name]
            t["total"] += 1
            if record.status == "success":
                t["success"] += 1
            t["ads_found"] += record.ads_found
            t["ads_clicked"] += record.ads_clicked

            self.stats.recent_records.append(record)
            if len(self.stats.recent_records) > self.stats.max_recent:
                self.stats.recent_records = self.stats.recent_records[-self.stats.max_recent:]

    def record_ad_click(self, record: AdClickRecord):
        with self.lock:
            self.stats.ad_clicks_success += 1 if record.success else 0
            self.stats.ad_clicks_failed += 1 if not record.success else 0

            ad_type = record.ad_type or "unknown"
            self.stats.ad_type_stats[ad_type] = self.stats.ad_type_stats.get(ad_type, 0) + 1

            network = record.ad_network or "unknown"
            self.stats.ad_network_stats[network] = self.stats.ad_network_stats.get(network, 0) + 1

            self.stats.recent_ad_clicks.append(record)
            if len(self.stats.recent_ad_clicks) > self.stats.max_recent:
                self.stats.recent_ad_clicks = self.stats.recent_ad_clicks[-self.stats.max_recent:]

    def get_summary(self) -> dict:
        with self.lock:
            return {
                "total_visits": self.stats.total_visits,
                "successful": self.stats.successful,
                "failed": self.stats.failed,
                "success_rate": round(self.stats.success_rate, 2),
                "avg_response_time": round(self.stats.avg_response_time, 3),
                "visits_per_minute": round(self.stats.visits_per_minute, 2),
                "elapsed_seconds": round(self.stats.elapsed_seconds, 1),
                "total_pages_visited": self.stats.total_pages_visited,
                "total_ads_found": self.stats.total_ads_found,
                "total_ads_clicked": self.stats.total_ads_clicked,
                "ad_clicks_success": self.stats.ad_clicks_success,
                "ad_clicks_failed": self.stats.ad_clicks_failed,
                "ads_per_visit": round(self.stats.ads_per_visit, 2),
                "ad_click_rate": round(self.stats.ad_click_rate, 2),
                "ad_type_stats": dict(self.stats.ad_type_stats),
                "ad_network_stats": dict(self.stats.ad_network_stats),
                "targets": dict(self.stats.target_stats),
            }

    def export_csv(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "target", "url", "proxy", "status",
                "response_code", "response_time", "user_agent",
                "pages_visited", "ads_found", "ads_clicked", "error",
            ])
            with self.lock:
                records = list(self.stats.recent_records)
            for r in records:
                writer.writerow([
                    datetime.fromtimestamp(r.timestamp).isoformat(),
                    r.target_name, r.url, r.proxy, r.status,
                    r.response_code, round(r.response_time, 3),
                    r.user_agent, r.pages_visited, r.ads_found,
                    r.ads_clicked, r.error,
                ])

            writer.writerow([])
            writer.writerow(["AD CLICK LOG"])
            writer.writerow([
                "timestamp", "target", "page_url", "ad_url",
                "ad_type", "ad_network", "response_code",
                "response_time", "success", "error",
            ])
            with self.lock:
                ad_records = list(self.stats.recent_ad_clicks)
            for r in ad_records:
                writer.writerow([
                    datetime.fromtimestamp(r.timestamp).isoformat(),
                    r.target_name, r.page_url, r.ad_url,
                    r.ad_type, r.ad_network, r.response_code,
                    round(r.response_time, 3), r.success, r.error,
                ])

    def export_json(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        summary = self.get_summary()
        with self.lock:
            records = [
                {
                    "timestamp": datetime.fromtimestamp(r.timestamp).isoformat(),
                    "target": r.target_name,
                    "url": r.url,
                    "proxy": r.proxy,
                    "status": r.status,
                    "response_code": r.response_code,
                    "response_time": round(r.response_time, 3),
                    "pages_visited": r.pages_visited,
                    "ads_found": r.ads_found,
                    "ads_clicked": r.ads_clicked,
                    "error": r.error,
                }
                for r in self.stats.recent_records
            ]
            ad_records = [
                {
                    "timestamp": datetime.fromtimestamp(r.timestamp).isoformat(),
                    "target": r.target_name,
                    "page_url": r.page_url,
                    "ad_url": r.ad_url,
                    "ad_type": r.ad_type,
                    "ad_network": r.ad_network,
                    "response_code": r.response_code,
                    "response_time": round(r.response_time, 3),
                    "success": r.success,
                    "error": r.error,
                }
                for r in self.stats.recent_ad_clicks
            ]
        data = {"summary": summary, "visit_records": records, "ad_click_records": ad_records}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def export(self):
        if not self.config.stats_save:
            return
        fmt = self.config.stats_format
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = self.config.stats_path
        os.makedirs(base, exist_ok=True)
        if fmt == "csv":
            self.export_csv(os.path.join(base, f"report_{ts}.csv"))
        else:
            self.export_json(os.path.join(base, f"report_{ts}.json"))

    def reset(self):
        with self.lock:
            self.stats = Stats()

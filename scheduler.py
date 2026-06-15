import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from logger import logger


class Scheduler:
    def __init__(self, config):
        self.config = config
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callback: Optional[Callable] = None

    def set_callback(self, callback: Callable):
        self._callback = callback

    def start(self):
        if not self.config.scheduler_enabled:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        if self.config.scheduler_mode == "interval":
            self._run_interval()
        else:
            self._run_daily()

    def _run_interval(self):
        interval = self.config.scheduler_interval * 60
        while self._running and not self._stop_event.is_set():
            if self._callback:
                self._callback()
            self._stop_event.wait(interval)

    def _run_daily(self):
        daily_time = self.config.daily_time
        runs_remaining = self.config.daily_runs
        run_duration = self.config.run_duration * 60

        while self._running and not self._stop_event.is_set():
            now = datetime.now()
            try:
                target = datetime.strptime(daily_time, "%H:%M").time()
            except ValueError:
                target = datetime.strptime("09:00", "%H:%M").time()
                logger.warn(f"Scheduler: invalid daily_time '{daily_time}', falling back to 09:00")
            target_dt = datetime.combine(now.date(), target)

            if now > target_dt:
                target_dt = datetime.combine(
                    (now.date() + timedelta(days=1)), target
                )

            wait_seconds = (target_dt - now).total_seconds()
            if self._stop_event.wait(wait_seconds):
                break

            runs = 0
            while runs < runs_remaining and self._running:
                if self._callback:
                    self._callback()
                runs += 1
                if runs < runs_remaining and runs_remaining > 0:
                    self._stop_event.wait(run_duration / max(runs_remaining, 1))

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        mode = self.config.scheduler_mode
        if mode == "interval":
            return {
                "enabled": self.config.scheduler_enabled,
                "mode": "interval",
                "interval_minutes": self.config.scheduler_interval,
                "running": self._running,
            }
        return {
            "enabled": self.config.scheduler_enabled,
            "mode": "daily",
            "time": self.config.daily_time,
            "runs": self.config.daily_runs,
            "running": self._running,
        }

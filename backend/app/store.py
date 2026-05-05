from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.models import (
    LeadCandidate,
    Notification,
    OutreachEvent,
    ProductProfile,
    SocialConnection,
    SocialSyncRun,
    SourcingReport,
    TaskRecord,
)


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = BASE_DIR / ".runtime" / "leadagent_store.json"


@dataclass
class InMemoryStore:
    product_profiles: list[ProductProfile] = field(default_factory=list)
    tasks: list[TaskRecord] = field(default_factory=list)
    leads: list[LeadCandidate] = field(default_factory=list)
    outreach_events: list[OutreachEvent] = field(default_factory=list)
    notifications: list[Notification] = field(default_factory=list)
    social_connections: list[SocialConnection] = field(default_factory=list)
    social_sync_runs: list[SocialSyncRun] = field(default_factory=list)
    sourcing_reports: list[SourcingReport] = field(default_factory=list)
    state_path: Path = field(default_factory=lambda: Path(os.getenv("LEADAGENT_STORE_PATH", DEFAULT_STATE_PATH)))

    def __post_init__(self) -> None:
        self.load()

    def load(self) -> None:
        if not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.product_profiles = self._load_rows(payload.get("product_profiles", []), ProductProfile)
        self.tasks = self._load_rows(payload.get("tasks", []), TaskRecord)
        self.leads = self._load_rows(payload.get("leads", []), LeadCandidate)
        self.outreach_events = self._load_rows(payload.get("outreach_events", []), OutreachEvent)
        self.notifications = self._load_rows(payload.get("notifications", []), Notification)
        self.social_connections = self._load_rows(payload.get("social_connections", []), SocialConnection)
        self.social_sync_runs = self._load_rows(payload.get("social_sync_runs", []), SocialSyncRun)
        self.sourcing_reports = self._load_rows(payload.get("sourcing_reports", []), SourcingReport)

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "product_profiles": [row.model_dump(mode="json") for row in self.product_profiles],
            "tasks": [row.model_dump(mode="json") for row in self.tasks],
            "leads": [row.model_dump(mode="json") for row in self.leads],
            "outreach_events": [row.model_dump(mode="json") for row in self.outreach_events],
            "notifications": [row.model_dump(mode="json") for row in self.notifications],
            "social_connections": [row.model_dump(mode="json") for row in self.social_connections],
            "social_sync_runs": [row.model_dump(mode="json") for row in self.social_sync_runs],
            "sourcing_reports": [row.model_dump(mode="json") for row in self.sourcing_reports],
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _load_rows(rows: list[dict], model):  # noqa: ANN001
        return [model.model_validate(row) for row in rows]

    def add_leads(self, new_leads: list[LeadCandidate]) -> None:
        self.leads.extend(new_leads)
        self.save()

    def set_leads(self, leads: list[LeadCandidate]) -> None:
        self.leads = list(leads)
        self.save()

    def add_product_profile(self, profile: ProductProfile) -> None:
        self.product_profiles.append(profile)
        self.save()

    def upsert_task(self, task: TaskRecord) -> None:
        for idx, current in enumerate(self.tasks):
            if current.task_id == task.task_id:
                self.tasks[idx] = task
                self.save()
                return
        self.tasks.append(task)
        self.save()

    def upsert_social_connection(self, connection: SocialConnection) -> None:
        for idx, current in enumerate(self.social_connections):
            if current.connection_id == connection.connection_id:
                self.social_connections[idx] = connection
                self.save()
                return
        self.social_connections.append(connection)
        self.save()

    def add_social_sync_run(self, sync_run: SocialSyncRun) -> None:
        self.social_sync_runs.append(sync_run)
        self.save()

    def add_sourcing_report(self, report: SourcingReport) -> None:
        self.sourcing_reports.append(report)
        self.save()

    def add_outreach_event(self, event: OutreachEvent) -> None:
        self.outreach_events.append(event)
        self.save()

    def add_notification(self, notification: Notification) -> None:
        self.notifications.append(notification)
        self.save()

    def clear_all(self) -> None:
        self.product_profiles.clear()
        self.tasks.clear()
        self.leads.clear()
        self.outreach_events.clear()
        self.notifications.clear()
        self.social_connections.clear()
        self.social_sync_runs.clear()
        self.sourcing_reports.clear()
        self.save()


store = InMemoryStore()

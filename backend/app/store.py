from __future__ import annotations

from dataclasses import dataclass, field

from app.models import LeadCandidate, Notification, OutreachEvent, ProductProfile, TaskRecord


@dataclass
class InMemoryStore:
    product_profiles: list[ProductProfile] = field(default_factory=list)
    tasks: list[TaskRecord] = field(default_factory=list)
    leads: list[LeadCandidate] = field(default_factory=list)
    outreach_events: list[OutreachEvent] = field(default_factory=list)
    notifications: list[Notification] = field(default_factory=list)

    def add_leads(self, new_leads: list[LeadCandidate]) -> None:
        self.leads.extend(new_leads)

    def upsert_task(self, task: TaskRecord) -> None:
        for idx, current in enumerate(self.tasks):
            if current.task_id == task.task_id:
                self.tasks[idx] = task
                return
        self.tasks.append(task)


store = InMemoryStore()

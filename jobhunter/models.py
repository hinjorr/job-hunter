from dataclasses import dataclass, field


@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    description: str = ""
    score: int = 0
    reason: str = ""
    profiles: list = field(default_factory=list)
    posted: str = ""  # YYYY-MM-DD when the source gives it; "" = unknown
    status: str = ""  # scored | skipped | queued; "" = not decided yet (the pipeline decides)
    remote_ok: str = ""  # Gemini's remote_from_pakistan answer: yes | no | unclear ("" = not asked)

    @property
    def id(self) -> str:
        return self.url

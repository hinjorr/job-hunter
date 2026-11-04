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

    @property
    def id(self) -> str:
        return self.url

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class OnScreenText:
    """Text that appears on screen during the video."""
    role: str
    company: str
    location: str
    stipend: str
    eligibility: str  # e.g. "2027 batch" or "Freshers welcome"
    deadline_badge: str  # e.g. "Apply by Friday" or "Apply soon"
    cta: str  # e.g. "Apply link in description"


@dataclass
class VoiceoverLine:
    """A single line of spoken text with timing info."""
    text: str
    start_seconds: float = 0.0
    end_seconds: float = 0.0


@dataclass
class ScriptDoc:
    """Complete script for a short video."""
    hook: str  # First 2 seconds, e.g. "Google internship, apply before Friday"
    voiceover_lines: list[VoiceoverLine]  # Main body text
    on_screen: OnScreenText  # Text displayed on screen
    title: str  # YouTube video title (max 100 chars)
    description: str  # YouTube description
    hashtags: list[str]  # YouTube hashtags

    def to_dict(self) -> dict:
        return {
            "hook": self.hook,
            "voiceover_lines": [
                {"text": l.text, "start_seconds": l.start_seconds, "end_seconds": l.end_seconds}
                for l in self.voiceover_lines
            ],
            "on_screen": {
                "role": self.on_screen.role,
                "company": self.on_screen.company,
                "location": self.on_screen.location,
                "stipend": self.on_screen.stipend,
                "eligibility": self.on_screen.eligibility,
                "deadline_badge": self.on_screen.deadline_badge,
                "cta": self.on_screen.cta,
            },
            "title": self.title,
            "description": self.description,
            "hashtags": self.hashtags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScriptDoc":
        return cls(
            hook=data["hook"],
            voiceover_lines=[
                VoiceoverLine(
                    text=l["text"],
                    start_seconds=l.get("start_seconds", 0.0),
                    end_seconds=l.get("end_seconds", 0.0),
                )
                for l in data["voiceover_lines"]
            ],
            on_screen=OnScreenText(**data["on_screen"]),
            title=data["title"],
            description=data["description"],
            hashtags=data["hashtags"],
        )


@dataclass
class SceneSpec:
    """Specification for a single visual scene."""
    scene_number: int
    layout_name: str  # e.g. "hook", "facts", "deadline", "cta"
    duration_seconds: float
    text_lines: list[str]  # Lines of text to display
    theme_name: str  # e.g. "blue", "purple"


@dataclass
class PostRecord:
    """Record in the posts table tracking video generation and upload."""
    opportunity_id: str
    script_json: str  # Serialized ScriptDoc
    video_path: Optional[str] = None
    youtube_id: Optional[str] = None
    status: str = "pending"  # pending | generating | generated | uploading | posted | failed
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    posted_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "script_json": self.script_json,
            "video_path": self.video_path,
            "youtube_id": self.youtube_id,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "posted_at": self.posted_at,
        }

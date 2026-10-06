from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Mapping, Protocol

SourceKind = Literal["page", "visual", "ax"]
VisualDelivery = Literal["foreground", "background"]


def _ascii_lower(value: str) -> str:
    return "".join(chr(ord(char) + 32) if "A" <= char <= "Z" else char for char in value)


@dataclass(frozen=True)
class Candidate:
    id: str
    description: str
    tool: str | None
    arguments: Mapping[str, Any]
    capture_id: str | None = None
    screenshot_reference: str | None = None
    source: SourceKind | None = None
    snapshot_id: str | None = None


@dataclass(frozen=True)
class Control:
    source: SourceKind
    role: str
    name: str
    value: Any
    handle: Any


class CandidateSource(Protocol):
    kind: ClassVar[SourceKind]

    def find(self, role: str, name: str) -> Control | None: ...

    def click(self, control: Control, *, candidate_id: str, description: str) -> Candidate | None: ...

    def type_text(
        self, control: Control, text: str, *, candidate_id: str, description: str
    ) -> Candidate | None: ...


@dataclass(frozen=True)
class VisualGridSource:
    """Controls from hierarchical probabilistic visual grid localization (Clef).

    Locates targets in visual screenshot space before constructing the source.
    ``find`` matches the localized target description (ASCII case-insensitive)
    and returns a control only when localization succeeded for that target.
    ``click`` is offered only when Driver advertises capture-bound click
    (``capture_bound``); it targets the resolved click (x, y) coordinates
    with the exact ``capture_id`` and authorized ``delivery`` mode.
    ``type_text`` returns None.
    """

    localization: Any
    pid: int
    window_id: int
    capture_id: str
    delivery: VisualDelivery = "background"
    capture_bound: bool = False
    screenshot_reference: Any = None
    kind: ClassVar[SourceKind] = "visual"

    def find(self, role: str, name: str) -> Control | None:
        if not self.localization or not getattr(self.localization, "success", False):
            return None
        target_desc = getattr(self.localization, "target_description", "")
        if _ascii_lower(target_desc) != _ascii_lower(name):
            return None
        return Control("visual", role, target_desc, None, self.localization)

    def click(self, control: Control, *, candidate_id: str, description: str) -> Candidate | None:
        if not self.capture_bound:
            return None
        if not self.localization or not getattr(self.localization, "success", False):
            return None
        x = getattr(self.localization, "click_x", None)
        y = getattr(self.localization, "click_y", None)
        if x is None or y is None:
            return None
        return Candidate(
            candidate_id,
            description,
            "click",
            {
                "pid": self.pid,
                "window_id": self.window_id,
                "x": x,
                "y": y,
                "capture_id": self.capture_id,
                "delivery_mode": self.delivery,
            },
            capture_id=self.capture_id,
            screenshot_reference=self.screenshot_reference,
            source="visual",
        )

    def type_text(
        self, control: Control, text: str, *, candidate_id: str, description: str
    ) -> None:
        return None

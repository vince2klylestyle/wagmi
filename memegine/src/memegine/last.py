"""Last — show the most recent brief / winner / post / session in one view.

Quick "where was I?" command. Answers:
- What was my last brief? (intent, format, score)
- What was my last winner? (prompt, tags, notes)
- What was my last post? (folder, caption)
- What was my last session? (name, duration)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import archive, export as export_mod, reference_lib, session as session_mod


@dataclass
class LastSnapshot:
    last_brief: dict | None = None
    last_winner: dict | None = None
    last_post: dict | None = None
    last_session: dict | None = None

    def as_text(self) -> str:
        lines = ["=== last activity ==="]
        if self.last_brief:
            b = self.last_brief
            lines.append(
                f"brief   [{b.get('kind', '?')}]  "
                f"{b.get('created_at', '')[:19]}  "
                f"fmt={b.get('format') or '-'}  "
                f"intent={b.get('intent', '')[:60]}"
            )
        else:
            lines.append("brief   (none)")
        if self.last_winner:
            w = self.last_winner
            lines.append(
                f"winner  {w.get('added_at', '')[:19]}  {w.get('filename', '')}"
            )
            if w.get("prompt"):
                lines.append(f"        prompt: {w['prompt'][:100]}")
            if w.get("notes"):
                lines.append(f"        notes: {w['notes'][:100]}")
        else:
            lines.append("winner  (none)")
        if self.last_post:
            p = self.last_post
            lines.append(
                f"post    {p.get('created_at', '')[:19]}  id={p.get('id', '')}"
            )
            if p.get("caption"):
                lines.append(f"        caption: {p['caption'][:100]}")
        else:
            lines.append("post    (none)")
        if self.last_session:
            s = self.last_session
            dur = s.get("duration_sec")
            dur_str = f" ({dur//60}m)" if dur else " (open)"
            lines.append(
                f"session {s.get('started_at', '')[:19]}  "
                f"{s.get('name', '')}{dur_str}"
            )
        else:
            lines.append("session (none)")
        return "\n".join(lines)


def compute() -> LastSnapshot:
    # Last brief.
    briefs = archive.read_recent(n=1)
    last_brief = briefs[0] if briefs else None

    # Last winner.
    refs = reference_lib._load_index()
    winners = sorted(
        [r for r in refs if "winner" in r.get("tags", [])],
        key=lambda r: r.get("added_at", ""), reverse=True,
    )
    last_winner = winners[0] if winners else None

    # Last post.
    posts = export_mod.list_recent(n=1)
    last_post = posts[0] if posts else None

    # Last session.
    sessions = session_mod.list_sessions()
    last_session = sessions[0] if sessions else None

    return LastSnapshot(
        last_brief=last_brief, last_winner=last_winner,
        last_post=last_post, last_session=last_session,
    )

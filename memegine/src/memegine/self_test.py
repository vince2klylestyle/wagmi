"""Self-test — synthetic operator walks the whole pipeline in-memory.

Proves the whole chain works: queue a topic, build a brief, lint it,
export a fake post, log fake performance, verify stats/journal/next
all reflect the activity, clean up.

Runs against a temporary data dir so real operator state isn't touched.
Useful for:
- CI: verifies the integration after every change
- Post-install: operator runs it once to confirm everything plays
  together on their machine
- Debugging: isolate whether a bug is in integration or in data

Exit code 0 on success. Non-zero on any failure.
"""
from __future__ import annotations

import datetime as dt
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SelfTestReport:
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)

    def as_text(self) -> str:
        lines = ["=== self-test ==="]
        for s in self.steps:
            sigil = "[OK]  " if s.ok else "[FAIL]"
            lines.append(f"  {sigil} {s.name}")
            if s.detail:
                lines.append(f"         {s.detail}")
        lines.append("")
        lines.append(f"verdict: {'PASS' if self.ok else 'FAIL'}")
        return "\n".join(lines)


def run() -> SelfTestReport:
    """Execute every major operator-facing action against a tempdir."""
    from . import (
        archive,
        auto_codex,
        caption_linter,
        deep_linter,
        export as export_mod,
        format_suggest,
        fragments,
        idea_grader,
        last as last_mod,
        next_action,
        performance,
        pipeline as pipeline_mod,
        prompt_engine,
        reference_lib,
        scheduler,
        session as session_mod,
        stats as stats_mod,
        style_codex,
        topics,
        x_post,
    )
    from .config import settings

    report = SelfTestReport()

    def step(name: str, fn):
        try:
            detail = fn() or ""
            report.steps.append(StepResult(name, True, detail))
        except Exception as exc:
            report.steps.append(StepResult(name, False, f"{type(exc).__name__}: {exc}"))
        return report.steps[-1].ok

    with tempfile.TemporaryDirectory(prefix="memegine-self-test-") as raw_tmp:
        tmp = Path(raw_tmp)

        # Redirect every store to tmp.
        orig = {
            "data_root": settings.data_root,
            "data_dir": settings.data_dir,
            "logs_dir": settings.logs_dir,
            "references_dir": settings.references_dir,
            "outputs_dir": settings.outputs_dir,
            "codex_path": settings.codex_path,
        }
        # Copy SHARED static assets (formats library, fragments, playbooks)
        # into the tempdir so validate and fragment expand have content. These
        # live under data_root, not data_dir, because they are shared across
        # every project.
        import shutil
        for name in ("formats", "fragments", "playbooks"):
            src = orig["data_root"] / name
            if src.exists():
                shutil.copytree(src, tmp / name)
        settings.data_root = tmp
        settings.data_dir = tmp
        settings.logs_dir = tmp / "logs"
        settings.references_dir = tmp / "refs"
        settings.outputs_dir = tmp / "outputs"
        settings.codex_path = tmp / "codex" / "style.md"
        for p in (settings.logs_dir, settings.references_dir,
                  settings.outputs_dir, settings.codex_path.parent):
            p.mkdir(parents=True, exist_ok=True)

        # Patch store paths that read via callable helpers.
        orig_topic = getattr(topics, "_queue_path", None)
        orig_perf = getattr(performance, "_store_path", None)
        orig_session = getattr(session_mod, "_events_path", None)
        orig_sched = getattr(scheduler, "_jobs_path", None)
        orig_posts = getattr(export_mod, "_posts_dir", None)
        topics._queue_path = lambda: tmp / "topics" / "queue.yaml"
        performance._store_path = lambda: tmp / "performance" / "posts.jsonl"
        session_mod._events_path = lambda: tmp / "sessions" / "events.jsonl"
        scheduler._jobs_path = lambda: tmp / "scheduler" / "jobs.yaml"
        export_mod._posts_dir = lambda: tmp / "posts"

        # Seed a codex so stats/next have something to read.
        style_codex.init_template()

        try:
            # 1. Grade an idea.
            def s1():
                g = idea_grader.grade("trader at 3am, cope face, 12% drawdown")
                assert g.letter in ("A", "B", "C"), f"grade={g.letter}"
                return f"grade={g.letter} score={g.score}"

            step("grade idea", s1)

            # 2. Queue a topic.
            def s2():
                t = topics.add("trader at 3am, quiet dread", priority=4)
                queued = topics.list_queued()
                assert len(queued) == 1
                return f"topic {t.id}"

            step("queue topic", s2)

            # 3. Start a session.
            def s3():
                e = session_mod.start(name="self-test")
                return f"session {e.session_id}"

            step("start session", s3)

            # 4. Suggest a format.
            def s4():
                slug = format_suggest.best("trader at 3am, quiet dread", kind="image")
                assert slug, "no format returned"
                return f"format={slug}"

            step("format suggest", s4)

            # 5. Build a pipeline bundle.
            def s5():
                bundle = pipeline_mod.build(
                    "trader at 3am, quiet dread", kind="image",
                    format_slug="photoreal_portrait",
                )
                assert Path(bundle.folder).exists()
                return f"bundle {bundle.id}"

            step("build pipeline", s5)

            # 6. Lint a prompt.
            def s6():
                prompt = (
                    "Trader at a kitchen counter, 35mm f/1.4, Cinestill 800T, "
                    "hard window light at 3:1 ratio, 3am, rule of thirds, "
                    "no extra fingers, no warped text."
                )
                sc = deep_linter.score(prompt)
                assert sc.score >= 70, f"score={sc.score}"
                return f"score={sc.score}"

            step("deep lint", s6)

            # 7. Expand a fragment.
            def s7():
                out = fragments.expand(
                    "A trader, LENS.35mm_1_4, LIGHTING.harsh_window, TIME_OF_DAY.3am"
                )
                assert "35mm" in out
                return "fragments expanded"

            step("fragments expand", s7)

            # 8. Caption lint.
            def s8():
                r = caption_linter.lint("kitchen, no one home")
                assert r.ok
                return "caption lint clean"

            step("caption lint", s8)

            # 9. Add a reference winner (triggers auto-codex).
            def s9():
                img = tmp / "winner.png"
                img.write_bytes(b"PNG\0fake")
                entry = reference_lib.add(
                    img,
                    tags=["night", "trader"],
                    prompt="Trader, 35mm f/1.4, Cinestill 800T, window light, dusk, rule of thirds",
                    notes="quiet dread",
                    winner=True,
                )
                assert "winner" in entry.tags
                text = settings.codex_path.read_text(encoding="utf-8")
                assert "Compounded Patterns" in text
                return f"ref {entry.id} + codex updated"

            step("ref add winner + auto-codex", s9)

            # 10. Log engagement via paste parser.
            def s10():
                from . import engagement_parser
                entry, parsed = engagement_parser.log_from_paste(
                    "820 Likes  140 Reposts  35 Replies  12.4K Views",
                    format_slug="photoreal_portrait",
                )
                assert entry is not None
                assert parsed.likes == 820
                return f"perf logged id={entry.id}"

            step("engagement paste", s10)

            # 11. Build a post bundle + X prepare.
            def s11():
                img = tmp / "final.png"
                img.write_bytes(b"PNG\0final")
                b = export_mod.build(
                    media_path=img, caption="kitchen, no one home",
                    alt_text="trader at 3am",
                )
                plan = x_post.prepare(b.id)
                assert plan.lint_ok
                return f"post {b.id}, X plan ready"

            step("post build + X prepare", s11)

            # 12. Stats / next / last dashboards.
            def s12():
                rep = stats_mod.compute(window="all")
                assert rep.briefs_total >= 1
                dash = next_action.compute()
                assert dash.current_session is not None
                snap = last_mod.compute()
                assert snap.last_brief is not None
                assert snap.last_winner is not None
                return f"briefs={rep.briefs_total} winners={rep.refs_winners}"

            step("stats/next/last dashboards", s12)

            # 13. Validate config.
            def s13():
                from . import validate
                vrep = validate.run()
                # Post bundles written in s11 live under tmp/posts — count is
                # OK; what we care about is zero ERRORs.
                assert vrep.error_count == 0, vrep.as_text()
                return f"{vrep.warn_count} warnings"

            step("validate config", s13)

            # 14. Close session.
            def s14():
                e = session_mod.end()
                assert e is not None
                return f"session {e.session_id} closed"

            step("end session", s14)

        finally:
            # Restore settings so subsequent commands in this process see
            # the real store.
            for k, v in orig.items():
                setattr(settings, k, v)
            if orig_topic:
                topics._queue_path = orig_topic
            if orig_perf:
                performance._store_path = orig_perf
            if orig_session:
                session_mod._events_path = orig_session
            if orig_sched:
                scheduler._jobs_path = orig_sched
            if orig_posts:
                export_mod._posts_dir = orig_posts

    return report

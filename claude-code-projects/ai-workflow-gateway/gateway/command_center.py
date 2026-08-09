import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from gateway import __version__ as GATEWAY_VERSION
from gateway.discovery import BoardProject, discover_all_projects
from gateway.runs_log import RunLine, newest_line, newest_line_per_task, parse_run_lines
from gateway.state import StateStore
from gateway.util import atomic_write_text

logger = logging.getLogger(__name__)

_DATED_REPORT_RE = re.compile(r"^.+-(?P<date>\d{4}-\d{2}-\d{2})\.md$")

# "Worst state wins per project" (SPEC, aoe-gateway/State.md). This ranking is a
# detection-severity ordering, not a judgement about cause: NEVER RUN (nothing at all
# to check) and MISSING ARTIFACT (a self-reported "ok" that turned out false) rank
# above STALE (often just the desktop being off — SPEC calls this "expected, not a
# defect") and FAILED (already self-reported truthfully in the run's own note).
# NO HISTORY is informational only (SPEC, added 2026-08-08) — a task simply hasn't
# logged its first line since runs.md started existing. It never enters this ranking:
# worst_state is computed over every other state and defaults to OK if none remain.
_SEVERITY = {
    "OK": 0,
    "FAILED": 1,
    "STALE": 2,
    "MISSING ARTIFACT": 3,
    "NEVER RUN": 4,
}


@dataclass
class TaskStatus:
    task_id: str
    state: str
    line: RunLine | None


@dataclass
class ProjectRow:
    project: BoardProject
    worst_state: str
    tasks: list[TaskStatus]
    newest_overall: RunLine | None
    inbox_depth: int
    newest_report: str | None
    newest_report_published: bool | None
    no_history_tasks: list[str] = field(default_factory=list)


def run_command_center(workspace_root: Path, state: StateStore, log_path: Path) -> None:
    now = datetime.now().astimezone()
    boards = discover_all_projects(workspace_root)
    rows = [_evaluate_project(bp, now) for bp in boards]

    md_content = _render_markdown(rows, now, log_path, state)
    atomic_write_text(workspace_root / "Command-Center.md", md_content)

    artifacts_root = workspace_root.parent / "Artifacts"
    _write_html_artifact(rows, now, log_path, state, artifacts_root)

    logger.info("command center regenerated: %d project(s)", len(rows))


def _task_state(project_root: Path, max_age_hours: float | None, line: RunLine | None, now: datetime) -> str:
    if line is None:
        # NO HISTORY (SPEC, added 2026-08-08): runs.md exists and has lines, but none
        # for this specific task yet — informational, not a fault (distinct from the
        # whole-project NEVER RUN case, and from STALE, which implies a task that HAS
        # run before but has gone quiet).
        return "NO HISTORY"

    if max_age_hours is not None:
        ts = line.timestamp
        # runs.md timestamps carry no tz (written in local time by the Project Worker);
        # compare naive-to-naive against local now rather than assuming/attaching a tz.
        age_hours = (now.replace(tzinfo=None) - ts).total_seconds() / 3600 if ts else float("inf")
        if age_hours > max_age_hours:
            return "STALE"

    if line.status in ("failed", "partial"):
        return "FAILED"

    missing = [a for a in line.artifacts if not (project_root / a).is_file()]
    if missing:
        return "MISSING ARTIFACT"

    return "OK"


def _evaluate_project(bp: BoardProject, now: datetime) -> ProjectRow:
    runs_path = bp.path / "State" / "runs.md"
    lines = parse_run_lines(runs_path)
    newest_overall = newest_line(lines)

    if not lines:
        # SPEC: NEVER RUN is a whole-project state — runs.md absent or contains no run
        # lines at all — distinct from a single cadence task simply not having fired yet.
        task_ids = [c.get("task", "?") for c in bp.cadence] or ["(no cadence declared)"]
        tasks = [TaskStatus(task_id=tid, state="NEVER RUN", line=None) for tid in task_ids]
    elif bp.cadence:
        by_task = newest_line_per_task(lines)
        tasks = [
            TaskStatus(
                task_id=c.get("task", "?"),
                state=_task_state(bp.path, c.get("max_age_hours"), by_task.get(c.get("task", "?")), now),
                line=by_task.get(c.get("task", "?")),
            )
            for c in bp.cadence
        ]
    else:
        # No declared cadence — fall back to the file's single newest line, no staleness check.
        tasks = [TaskStatus(task_id=newest_overall.task_id, state=_task_state(bp.path, None, newest_overall, now), line=newest_overall)]

    no_history_tasks = [t.task_id for t in tasks if t.state == "NO HISTORY"]
    ranked = [t.state for t in tasks if t.state != "NO HISTORY"]
    worst_state = max(ranked, key=lambda s: _SEVERITY[s]) if ranked else "OK"

    inbox_dir = bp.path / "Inbox"
    inbox_depth = len(list(inbox_dir.glob("*"))) if inbox_dir.is_dir() else 0

    reports_dir = bp.path / "Reports"
    newest_report_path = _newest_report(reports_dir)
    newest_report = None
    newest_report_published = None
    if newest_report_path is not None:
        newest_report = newest_report_path.name
        newest_report_published = (reports_dir / "published" / (newest_report_path.stem + ".pdf")).is_file()

    return ProjectRow(
        project=bp,
        worst_state=worst_state,
        tasks=tasks,
        newest_overall=newest_overall,
        inbox_depth=inbox_depth,
        newest_report=newest_report,
        newest_report_published=newest_report_published,
        no_history_tasks=no_history_tasks,
    )


def _newest_report(reports_dir: Path) -> Path | None:
    """Prefer the newest *dated* report (`<name>-YYYY-MM-DD.md`) over raw mtime — a
    continuously-updated document like a CRM/pipeline file otherwise wins on mtime
    despite not being the newest dated deliverable (found in the first live board)."""
    if not reports_dir.is_dir():
        return None

    md_files = list(reports_dir.glob("*.md"))
    if not md_files:
        return None

    dated = [(m.group("date"), p) for p in md_files if (m := _DATED_REPORT_RE.match(p.name))]
    if dated:
        # Tie-break same-dated reports by mtime — glob() order isn't a guaranteed stable
        # sort, so without this the pick could vary run-to-run for no visible reason.
        return max(dated, key=lambda pair: (pair[0], pair[1].stat().st_mtime))[1]

    return max(md_files, key=lambda p: p.stat().st_mtime)


def _retention_display(retention: dict) -> str:
    if not retention:
        return "—"
    return ", ".join(f"{k}={v}" for k, v in retention.items())


def _format_pass_time(value: str | None) -> str:
    if not value:
        return "never"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return value


def _latest_warning_or_error(log_path: Path) -> str | None:
    if not log_path.is_file():
        return None
    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        return None
    for raw in reversed(text.splitlines()):
        parts = raw.split(None, 3)
        if len(parts) >= 3 and parts[2] in ("WARNING", "ERROR", "CRITICAL"):
            return raw.strip()
    return None


def _render_markdown(rows: list[ProjectRow], now: datetime, log_path: Path, state: StateStore) -> str:
    lines: list[str] = []
    lines.append("# Command Center")
    lines.append("")
    lines.append(f"_Generated {now.strftime('%Y-%m-%d %H:%M:%S %Z')} by AI Workflow Gateway v{GATEWAY_VERSION}_")
    lines.append("")

    tally: dict[str, int] = {}
    for row in rows:
        tally[row.worst_state] = tally.get(row.worst_state, 0) + 1
    tally_str = " · ".join(f"{count} {state}" for state, count in sorted(tally.items(), key=lambda kv: -_SEVERITY[kv[0]]))
    lines.append(f"**{len(rows)} project(s)** — {tally_str or 'none'}")
    lines.append("")

    lines.append("## Projects")
    lines.append("")
    lines.append("| Project | State | Newest run | Inbox | Newest report | Published | Retention | Pending first run |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in rows:
        newest_run_cell = "—"
        if row.newest_overall is not None:
            ts = row.newest_overall
            newest_run_cell = f"{ts.date} {ts.time} · {ts.task_id} · {ts.status}"
        published_cell = "—" if row.newest_report is None else ("yes" if row.newest_report_published else "no")
        pending_cell = ", ".join(row.no_history_tasks) if row.no_history_tasks else "—"
        lines.append(
            f"| {row.project.title} | {row.worst_state} | {newest_run_cell} | {row.inbox_depth} | "
            f"{row.newest_report or '—'} | {published_cell} | {_retention_display(row.project.retention)} | {pending_cell} |"
        )
    lines.append("")

    lines.append("## Attention")
    lines.append("")
    attention_rows = [r for r in rows if r.worst_state != "OK"]
    if not attention_rows:
        lines.append("All green — no project below OK.")
    else:
        for i, row in enumerate(attention_rows):
            if i > 0:
                lines.append("")
            runs_link = f"{row.project.path.name}/State/runs.md"
            lines.append(f"### {row.project.title} — {row.worst_state}")
            for task in row.tasks:
                if task.state in ("OK", "NO HISTORY"):
                    continue
                line_desc = f"`{task.line.raw}`" if task.line else "(no matching run line)"
                lines.append(f"- **{task.task_id}**: {task.state} — {line_desc}")
            lines.append(f"  - [runs.md]({runs_link})")
            if row.newest_report:
                report_link = f"{row.project.path.name}/Reports/{row.newest_report}"
                lines.append(f"  - [{row.newest_report}]({report_link})")
    lines.append("")

    pending_first_run = [(row, task_id) for row in rows for task_id in row.no_history_tasks]
    if pending_first_run:
        lines.append(
            "_" + ", ".join(f"{row.project.title}/{task_id}" for row, task_id in pending_first_run) +
            " — awaiting their first run line since `runs.md` began tracking. Informational only, not a fault; "
            "self-clears on first run._"
        )
        lines.append("")

    lines.append("## Gateway health")
    lines.append("")
    lines.append(f"- Last publish pass: {_format_pass_time(state.last_pass_run_at('publish'))}")
    lines.append(f"- Last notify pass: {_format_pass_time(state.last_pass_run_at('notify'))}")
    lines.append(f"- Last accountability pass: {_format_pass_time(state.last_pass_run_at('accountability'))}")
    latest_issue = _latest_warning_or_error(log_path)
    lines.append(f"- Most recent WARNING/ERROR: {f'`{latest_issue}`' if latest_issue else 'none'}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Generated by the AI Workflow Gateway. Do not edit; regenerated every pass. Diagnosis belongs to the Project Worker._")
    lines.append("")

    return "\n".join(lines)


# --- HTML artifact -----------------------------------------------------------
# Overwrites the shell Cowork registers at Artifacts/command-center/index.html
# (SPEC "Artifact path"). The gateway never creates or touches the manifest — if
# the file isn't there, registration hasn't happened yet and this is a no-op.
# The <script id="cowork-artifact-meta"> block Cowork wrote at registration is
# preserved byte-for-byte; only the content after it is gateway-owned/regenerated.

_META_END_MARKER = "</script>"

_STATE_CSS = {
    "OK": ("c-ok", "d-ok"),
    "FAILED": ("c-warn", "d-warn"),
    "STALE": ("c-bad", "d-bad"),
    "MISSING ARTIFACT": ("c-bad", "d-bad"),
    "NEVER RUN": ("c-bad", "d-bad"),
}

_HTML_STYLE = """<style>
    :root { color-scheme: light; }
    #cc {
      font-family: ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif;
      color: #1a1a1a; background: #fff; line-height: 1.5;
      max-width: 1100px; margin: 0 auto; padding: 8px 4px 32px;
      font-size: 14px;
    }
    #cc h1 { font-size: 22px; font-weight: 650; margin: 0 0 2px; letter-spacing: -0.01em; }
    #cc h2 { font-size: 13px; font-weight: 650; text-transform: uppercase; letter-spacing: 0.06em;
             color: #6b7280; margin: 30px 0 10px; }
    #cc h3 { font-size: 15px; font-weight: 620; margin: 18px 0 8px; }
    #cc .gen { font-size: 12.5px; color: #6b7280; margin-bottom: 14px; font-variant-numeric: tabular-nums; }
    #cc .gen b { color: #374151; font-weight: 600; }
    #cc .rollup { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
    #cc .chip { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600;
                padding: 4px 10px; border-radius: 999px; border: 1px solid transparent; }
    #cc .chip .dot { width: 7px; height: 7px; border-radius: 50%; }
    #cc .c-ok    { background: #ecfdf5; color: #065f46; border-color: #a7f3d0; }
    #cc .c-warn  { background: #fffbeb; color: #92400e; border-color: #fde68a; }
    #cc .c-bad   { background: #fef2f2; color: #991b1b; border-color: #fecaca; }
    #cc .c-mute  { background: #f3f4f6; color: #4b5563; border-color: #e5e7eb; }
    #cc .d-ok   { background: #10b981; }
    #cc .d-warn { background: #f59e0b; }
    #cc .d-bad  { background: #ef4444; }
    #cc .d-mute { background: #9ca3af; }
    #cc table { width: 100%; border-collapse: collapse; margin-top: 4px; }
    #cc th { text-align: left; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.05em;
             color: #6b7280; font-weight: 600; padding: 7px 10px; border-bottom: 1px solid #e5e7eb; }
    #cc td { padding: 10px; border-bottom: 1px solid #f3f4f6; vertical-align: top; font-size: 13.5px; }
    #cc tr:last-child td { border-bottom: none; }
    #cc .proj { font-weight: 600; }
    #cc .mono { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
                font-size: 12px; color: #4b5563; font-variant-numeric: tabular-nums; }
    #cc .card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; background: #fff; }
    #cc .card.bad  { border-left: 3px solid #ef4444; }
    #cc .card.warn { border-left: 3px solid #f59e0b; }
    #cc ul { margin: 8px 0 0; padding-left: 18px; }
    #cc li { margin-bottom: 6px; font-size: 13.5px; }
    #cc code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 12px;
               background: #f3f4f6; padding: 1.5px 5px; border-radius: 4px; color: #374151;
               word-break: break-word; }
    #cc .path { color: #6b7280; font-size: 12px; }
    #cc .health { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
    #cc .h-item { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px; }
    #cc .h-lab { font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; font-weight: 600; }
    #cc .h-val { font-size: 14px; margin-top: 3px; font-weight: 550; }
    #cc .h-val.never { color: #b45309; }
    #cc .banner { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
                  padding: 11px 14px; font-size: 12.5px; color: #4b5563; margin-bottom: 20px; }
    #cc .banner b { color: #1f2937; }
    #cc footer { margin-top: 32px; padding-top: 14px; border-top: 1px solid #e5e7eb;
                 font-size: 12px; color: #9ca3af; }
  </style>"""


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _chip_html(state: str) -> str:
    chip_class, dot_class = _STATE_CSS.get(state, ("c-mute", "d-mute"))
    return f'<span class="chip {chip_class}"><span class="dot {dot_class}"></span>{_html_escape(state)}</span>'


def _card_class(row: ProjectRow) -> str:
    task_states = {t.state for t in row.tasks if t.state not in ("OK", "NO HISTORY")}
    if task_states & {"STALE", "MISSING ARTIFACT", "NEVER RUN"}:
        return "bad"
    return "warn"  # only FAILED remains — already self-reported truthfully


def _render_html_body(rows: list[ProjectRow], now: datetime, log_path: Path, state: StateStore) -> str:
    parts: list[str] = []
    parts.append(
        "<!-- RBK-AOE Command Center — derived view.\n"
        "     CANONICAL SOURCE: E:\\RBK_AUR_DSKTP_AI\\Workspace\\Command-Center.md\n"
        "     This file is overwritten in full by the AI Workflow Gateway on every pass.\n"
        "     Do not hand-edit. Cowork owns the manifest entry; the gateway owns this file's contents. -->"
    )
    parts.append('<div id="cc">')
    parts.append(f"  {_HTML_STYLE}")
    parts.append("")
    parts.append("  <h1>Command Center</h1>")
    parts.append(
        f'  <div class="gen">Generated <b>{_html_escape(now.strftime("%Y-%m-%d %H:%M:%S %Z"))}</b> '
        f"&middot; AI Workflow Gateway v{GATEWAY_VERSION}</div>"
    )
    parts.append("")

    tally: dict[str, int] = {}
    for row in rows:
        tally[row.worst_state] = tally.get(row.worst_state, 0) + 1
    worst_overall = max(tally, key=lambda s: _SEVERITY[s]) if tally else "OK"
    rollup_class, rollup_dot = _STATE_CSS.get(worst_overall, ("c-ok", "d-ok"))
    tally_str = " &middot; ".join(f"{count} {s}" for s, count in sorted(tally.items(), key=lambda kv: -_SEVERITY[kv[0]]))
    parts.append('  <div class="rollup">')
    parts.append(f'    <span class="chip {rollup_class}"><span class="dot {rollup_dot}"></span>{len(rows)} projects &middot; {tally_str or "none"}</span>')
    parts.append('    <span class="chip c-mute"><span class="dot d-mute"></span>derived view &middot; Command-Center.md is canonical</span>')
    parts.append("  </div>")
    parts.append("")

    parts.append(
        '  <div class="banner"><b>Shell registered by Cowork; contents owned by the gateway.</b> '
        "This page is a snapshot of <code>Command-Center.md</code> as of the timestamp above. "
        "The gateway overwrites it on every pass. If the timestamp does not advance after the next pass, "
        "Cowork is caching at registration rather than reading from disk &mdash; in that case this pin is "
        "unreliable and the Markdown file is authoritative.</div>"
    )
    parts.append("")

    parts.append("  <h2>Projects</h2>")
    parts.append("  <table>")
    parts.append(
        "    <thead><tr><th>Project</th><th>State</th><th>Newest run</th><th>Inbox</th>"
        "<th>Newest report</th><th>Published</th><th>Retention</th><th>Pending first run</th></tr></thead>"
    )
    parts.append("    <tbody>")
    for row in rows:
        newest_run_cell = "—"
        if row.newest_overall is not None:
            ts = row.newest_overall
            newest_run_cell = f"{_html_escape(ts.date)} {_html_escape(ts.time)}<br>{_html_escape(ts.task_id)} &middot; {_html_escape(ts.status)}"
        published_cell = "—" if row.newest_report is None else ("yes" if row.newest_report_published else "no")
        pending_cell = ", ".join(_html_escape(t) for t in row.no_history_tasks) if row.no_history_tasks else "—"
        parts.append(
            "      <tr>"
            f'<td class="proj">{_html_escape(row.project.title)}</td>'
            f"<td>{_chip_html(row.worst_state)}</td>"
            f'<td class="mono">{newest_run_cell}</td>'
            f"<td>{row.inbox_depth}</td>"
            f'<td class="mono">{_html_escape(row.newest_report or "—")}</td>'
            f"<td>{published_cell}</td>"
            f'<td class="mono">{_html_escape(_retention_display(row.project.retention))}</td>'
            f'<td class="mono">{pending_cell}</td>'
            "</tr>"
        )
    parts.append("    </tbody>")
    parts.append("  </table>")
    parts.append("")

    parts.append("  <h2>Attention</h2>")
    parts.append("")
    attention_rows = [r for r in rows if r.worst_state != "OK"]
    if not attention_rows:
        parts.append("  <p>All green &mdash; no project below OK.</p>")
    else:
        for row in attention_rows:
            parts.append(f'  <div class="card {_card_class(row)}">')
            parts.append(f"    <h3>{_html_escape(row.project.title)}</h3>")
            parts.append("    <ul>")
            for task in row.tasks:
                if task.state in ("OK", "NO HISTORY"):
                    continue
                if task.line:
                    parts.append(
                        f"      <li><b>{_html_escape(task.task_id)}</b> &mdash; {_html_escape(task.state)}<br>"
                        f"<code>{_html_escape(task.line.raw)}</code></li>"
                    )
                else:
                    parts.append(f"      <li><b>{_html_escape(task.task_id)}</b> &mdash; {_html_escape(task.state)}</li>")
            parts.append("    </ul>")
            path_bits = [f"{row.project.path.name}/State/runs.md"]
            if row.newest_report:
                path_bits.append(f"{row.project.path.name}/Reports/{row.newest_report}")
            parts.append(f'    <div class="path" style="margin-top:10px">{" &middot; ".join(_html_escape(b) for b in path_bits)}</div>')
            parts.append("  </div>")
    parts.append("")

    pending_first_run = [(row, task_id) for row in rows for task_id in row.no_history_tasks]
    if pending_first_run:
        pending_str = ", ".join(f"{_html_escape(row.project.title)}/{_html_escape(task_id)}" for row, task_id in pending_first_run)
        parts.append(
            f'  <div class="banner" style="margin-top:4px"><b>{pending_str}</b> awaiting their first run line '
            "since <code>runs.md</code> began tracking. Informational only, not a fault; self-clears on first run.</div>"
        )
        parts.append("")

    parts.append("  <h2>Gateway health</h2>")
    last_publish = state.last_pass_run_at("publish")
    last_notify = state.last_pass_run_at("notify")
    last_accountability = state.last_pass_run_at("accountability")
    parts.append('  <div class="health">')
    for label, value in (("Last publish", last_publish), ("Last notify", last_notify), ("Last accountability", last_accountability)):
        cls = "h-val never" if not value else "h-val"
        parts.append(f'    <div class="h-item"><div class="h-lab">{label}</div><div class="{cls}">{_html_escape(_format_pass_time(value))}</div></div>')
    parts.append("  </div>")

    latest_issue = _latest_warning_or_error(log_path)
    parts.append('  <div class="h-item" style="margin-top:10px">')
    parts.append('    <div class="h-lab">Most recent WARNING/ERROR</div>')
    if latest_issue:
        parts.append(f'    <div class="h-val" style="font-size:12.5px; font-weight:450"><code>{_html_escape(latest_issue)}</code></div>')
    else:
        parts.append('    <div class="h-val" style="font-size:12.5px; font-weight:450">none</div>')
    parts.append("  </div>")
    parts.append("")

    parts.append("  <footer>")
    parts.append("    Generated by the AI Workflow Gateway. Do not edit; regenerated every pass.")
    parts.append("    Diagnosis belongs to the Project Worker.")
    parts.append("  </footer>")
    parts.append("</div>")

    return "\n".join(parts)


def _write_html_artifact(rows: list[ProjectRow], now: datetime, log_path: Path, state: StateStore, artifacts_root: Path) -> None:
    index_path = artifacts_root / "command-center" / "index.html"
    if not index_path.is_file():
        # Gateway cannot create an artifact — only Cowork can write the manifest entry
        # that makes this folder exist (SPEC "Artifact path"). Not registered yet: skip.
        logger.info("command center: HTML artifact not registered at %s, skipping overwrite", index_path)
        return

    try:
        existing = index_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.error("command center: could not read existing HTML artifact at %s", index_path, exc_info=True)
        return

    marker_pos = existing.find(_META_END_MARKER)
    if marker_pos == -1:
        logger.error(
            "command center: %s has no cowork-artifact-meta script block, refusing to guess where the "
            "manifest metadata ends — skipping HTML overwrite", index_path,
        )
        return

    preserved_head = existing[: marker_pos + len(_META_END_MARKER)]
    body = _render_html_body(rows, now, log_path, state)
    content = f"{preserved_head}\n{body}\n"

    tmp = index_path.with_name(index_path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(index_path)
    logger.info("command center: overwrote HTML artifact at %s", index_path)

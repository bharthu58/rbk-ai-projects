#!/usr/bin/env python3
"""
podcast_ingest — Spotify podcast → wiki note pipeline

Usage (via run_podcast.sh or directly):
    python -m podcast_ingest <spotify_url> [options]

Options:
    --whisper-local         Use local Whisper model instead of OpenAI API
    --record-seconds N      Override recording duration for the record fallback
    --dry-run               Print the note without writing to raw/
    --resolve-only          Print resolver JSON result and exit (no transcription)

Pipeline:
    1. Resolver  → finds audio source (direct MP3 / YouTube / RSS / record)
    2. Transcript → yt-dlp captions (YouTube) or Whisper (audio) or ffmpeg record
    3. Note      → structured .md written to raw/ for /wiki-ingest
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

# Support both `python -m podcast_ingest` and direct script execution
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))

from podcast_ingest.resolver import resolve, ResolveResult


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wiki root discovery
# ---------------------------------------------------------------------------

def find_wiki_root() -> Path:
    env = os.environ.get("WIKI_ROOT")
    if env:
        return Path(env)
    for root in [Path.cwd(), _HERE.parent.parent, Path.home()]:
        for cfg in root.rglob("wiki-config.md"):
            return cfg.parent
    raise FileNotFoundError(
        "Could not locate wiki-config.md. Set WIKI_ROOT env var or run from inside the wiki."
    )


# ---------------------------------------------------------------------------
# Transcript acquisition
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:80]


def clean_vtt(vtt_text: str) -> str:
    lines, prev = [], ""
    for line in vtt_text.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or re.match(r"^\d+$", line):
            continue
        if re.match(r"[\d:]+\s*-->\s*[\d:]+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line != prev:
            lines.append(line)
            prev = line
    return " ".join(lines)


def clean_transcript(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw).strip()
    text = re.sub(r"\b(\w+)-\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    return text


def _whisper_transcribe(audio_path: Path, use_local: bool) -> str:
    if use_local:
        try:
            import whisper
        except ImportError:
            raise ImportError("openai-whisper not installed. Run: pip install openai-whisper")
        return whisper.load_model("base").transcribe(str(audio_path))["text"]
    else:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        with open(audio_path, "rb") as f:
            return client.audio.transcriptions.create(model="whisper-1", file=f).text


def get_yt_captions(youtube_url: str) -> str | None:
    """Download auto-generated captions for a known YouTube URL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-auto-sub", "--sub-lang", "en", "--sub-format", "vtt",
            "--skip-download", "--no-playlist",
            "--js-runtimes", "node",
            "-o", str(Path(tmpdir) / "transcript"),
            youtube_url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            return None
        return clean_vtt(vtt_files[0].read_text(encoding="utf-8", errors="replace"))


def download_and_transcribe(audio_url: str, use_local: bool) -> str | None:
    """Download audio from a direct URL and transcribe with Whisper."""
    import urllib.request
    tmpdir = tempfile.mkdtemp()
    ext = ".mp3" if ".mp3" in audio_url else ".m4a"
    audio_path = Path(tmpdir) / f"episode{ext}"
    log.info("  Downloading audio...")
    try:
        urllib.request.urlretrieve(audio_url, audio_path)
    except Exception as e:
        log.warning("  Audio download failed: %s", e)
        return None
    log.info("  Transcribing with Whisper (%s)...", "local" if use_local else "API")
    try:
        return _whisper_transcribe(audio_path, use_local)
    except Exception as e:
        log.warning("  Whisper failed: %s", e)
        return None


def get_transcript_record(duration_s: int, use_local: bool) -> str | None:
    """Record system audio via ffmpeg while user plays episode manually."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        log.error("  ffmpeg not found. Install: sudo apt install ffmpeg")
        return None

    try:
        pa = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, check=True)
        monitor_source = pa.stdout.strip() + ".monitor"
    except (FileNotFoundError, subprocess.CalledProcessError):
        monitor_source = "default"
        log.info("  pactl not found — recording from default input.")

    tmpdir = tempfile.mkdtemp()
    audio_path = Path(tmpdir) / "recording.mp3"

    print(f"\n  >>> PLAY THE EPISODE NOW in Spotify. Recording for {duration_s}s.")
    input("  >>> Press ENTER when ready to start recording.")

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "pulse", "-i", monitor_source,
             "-t", str(duration_s), "-ar", "16000", "-ac", "1", str(audio_path)],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        log.error("  Recording failed: %s", e.stderr.decode()[:200])
        return None

    log.info("  Recording complete. Transcribing...")
    try:
        return _whisper_transcribe(audio_path, use_local)
    except Exception as e:
        log.error("  Whisper failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Note builder
# ---------------------------------------------------------------------------

def build_note(transcript: str, result: ResolveResult) -> tuple[str, str]:
    today = date.today().isoformat()
    meta = result.metadata
    yt_url = result.youtube_url
    youtube_line = f'source_youtube: "{yt_url}"\n' if yt_url else ""
    youtube_ref = f"\n> **Also on YouTube:** {yt_url}" if yt_url else ""
    desc = meta.description.strip()

    frontmatter = (
        f"---\n"
        f'title: "Podcast — {meta.title}"\n'
        f"source_type: podcast\n"
        f'source_podcast: "{meta.podcast}"\n'
        f'source_episode: "{meta.title}"\n'
        f'source_url: "{meta.spotify_url}"\n'
        f"{youtube_line}"
        f"date: {today}\n"
        f"tags: [podcast]\n"
        f"---"
    )
    header = (
        f"# {meta.podcast} — {meta.title}\n\n"
        f"> **Source:** [{meta.podcast} on Spotify]({meta.spotify_url}){youtube_ref}\n"
        f"> **Date:** {today}\n"
        f"> **Transcript via:** {result.source} (confidence {result.confidence:.2f})\n"
    )
    desc_section = f"\n## Episode Description\n\n{desc}\n" if desc else ""
    body = f"{desc_section}\n## Transcript\n\n{transcript}\n"

    stem = f"podcast--{slugify(meta.title)}--{today}"
    return f"{frontmatter}\n\n{header}{body}", stem


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve a Spotify podcast, transcribe, and write to raw/ for /wiki-ingest."
    )
    parser.add_argument("url", help="Spotify episode URL")
    parser.add_argument("--whisper-local", action="store_true",
                        help="Use local Whisper model instead of OpenAI API")
    parser.add_argument("--record-seconds", type=int, default=0,
                        help="Duration to record for the record fallback")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print note without writing to raw/")
    parser.add_argument("--resolve-only", action="store_true",
                        help="Print resolver JSON result and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    # ── Resolve ──────────────────────────────────────────────────────────
    result = resolve(args.url)

    if args.resolve_only:
        print(json.dumps({
            "audio_url": result.audio_url,
            "source": result.source,
            "confidence": round(result.confidence, 3),
            "metadata": {
                "title": result.metadata.title,
                "podcast": result.metadata.podcast,
                "episode_number": result.metadata.episode_number,
                "guest": result.metadata.guest,
            },
            "notes": result.notes,
        }, indent=2))
        return

    meta = result.metadata
    log.info("\nResolved: %s (source=%s, confidence=%.2f)", meta.title, result.source, result.confidence)

    # ── Transcribe ───────────────────────────────────────────────────────
    transcript: str | None = None

    if result.source == "youtube":
        log.info("Fetching YouTube captions...")
        transcript = get_yt_captions(result.audio_url)
        if transcript:
            log.info("  Captions obtained.")
        else:
            log.info("  No captions — falling back to audio download + Whisper.")
            transcript = download_and_transcribe(result.audio_url, args.whisper_local)

    elif result.source in ("direct", "web", "rss"):
        log.info("Downloading audio and transcribing...")
        transcript = download_and_transcribe(result.audio_url, args.whisper_local)

    elif result.source == "record":
        duration_s = args.record_seconds or (meta.duration_ms // 1000) or 3600
        log.info("Record fallback (%ds)...", duration_s)
        transcript = get_transcript_record(duration_s, args.whisper_local)

    if not transcript:
        log.error(
            "\nCould not obtain transcript.\n"
            "Manual option: paste transcript into raw/ as a .md or .txt file, then run /wiki-ingest."
        )
        sys.exit(1)

    transcript = clean_transcript(transcript)
    log.info("Transcript: %d chars (~%d tokens)", len(transcript), len(transcript) // 4)

    # ── Build & write note ───────────────────────────────────────────────
    note, stem = build_note(transcript, result)

    if args.dry_run:
        print("\n=== DRY RUN ===\n")
        print(note)
        return

    wiki_root = find_wiki_root()
    out_path = wiki_root / "raw" / f"{stem}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(note, encoding="utf-8")
    log.info("\nWritten: %s", out_path)
    log.info("Next: run /wiki-ingest in Claude Code to distil and integrate.")


if __name__ == "__main__":
    main()

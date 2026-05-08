"""End-to-end QA harness: runs the production CLI with mock inputs and a
known user-content article, verifies every output is well-formed.

What it does:
  1. Backs up real input/Substacks.csv to .qa-backup
  2. Replaces it with input/Substacks_qa_mock.csv (5 substacks, fast)
  3. Spawns `crypto-research` as a subprocess with stdin/stdout pipes
  4. Watches the new output dir as it's created
  5. Drops the user-content fixture into <output_dir>/user_content/
     before the user-content prompt fires
  6. Pipes a scripted sequence of inputs to exercise:
        - user content "ready"
        - outline revise + accept
        - section accept / revise+accept / edited
  7. After the run completes, restores Substacks.csv and verifies outputs

Usage:
    python scripts/qa_full_run.py "Bitcoin ETF" \
        --thesis "Bitcoin ETF inflows are a recovery signal..."
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO / "input"
OUTPUT_DIR = REPO / "output"
SCRIPTS_DIR = REPO / "scripts"

REAL_CSV = INPUT_DIR / "Substacks.csv"
MOCK_CSV = INPUT_DIR / "Substacks_qa_mock.csv"
BACKUP_CSV = INPUT_DIR / "Substacks.csv.qa-backup"

USER_CONTENT_FIXTURE = SCRIPTS_DIR / "qa_user_content_template"

# Path to the crypto-research console script installed via pipx
CLI = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".local" / "bin" / "crypto-research.exe"

# Scripted user inputs in order. The harness sends "ready" automatically when
# the [USER CONTENT] prompt fires; the rest are sent in order to subsequent
# prompts (outline review, then each section review).
SCRIPTED_INPUTS = [
    "ready",                                                                 # user_wants_to_add_content
    "revise Reduce to 4 main sections, focused on actionable insights.",     # outline revise
    "accept",                                                                # outline accept
    "accept",                                                                # section 1
    "revise Tighten the opening, lead with the strongest finding.",          # section 2 revise
    "accept",                                                                # section 2 accept
    "edited",                                                                # section 3 edited
    "accept",                                                                # section 4
    "accept",                                                                # section 5 (if present)
    "accept",                                                                # section 6 (if present)
    "accept", "accept", "accept",                                            # safety buffer
]


def setup_mock_csv() -> None:
    """Back up real CSV, install mock."""
    if REAL_CSV.exists():
        shutil.copy2(REAL_CSV, BACKUP_CSV)
        print(f"[harness] Backed up {REAL_CSV.name} -> {BACKUP_CSV.name}")
    if not MOCK_CSV.exists():
        raise FileNotFoundError(f"Mock CSV not found: {MOCK_CSV}")
    shutil.copy2(MOCK_CSV, REAL_CSV)
    print(f"[harness] Installed mock CSV ({MOCK_CSV.name} -> {REAL_CSV.name})")


def restore_real_csv() -> None:
    """Restore backed-up CSV. Always called via try/finally."""
    if BACKUP_CSV.exists():
        shutil.copy2(BACKUP_CSV, REAL_CSV)
        BACKUP_CSV.unlink()
        print(f"[harness] Restored real Substacks.csv from backup")


def watch_for_run_dir(parent: Path, query_slug: str, before_ts: float,
                      timeout: float = 60.0) -> Path:
    """Block until a new directory matching <slug>_* appears under parent.
    Returns the new directory's path."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for child in parent.iterdir():
            if (child.is_dir() and child.name.startswith(query_slug + "_")
                    and child.stat().st_mtime >= before_ts - 1):
                return child
        time.sleep(0.3)
    raise TimeoutError(f"Run directory under {parent} did not appear within {timeout}s")


def drop_user_content_fixture(run_dir: Path) -> None:
    """Copy fixture user content files into run_dir/user_content/."""
    target = run_dir / "user_content"
    target.mkdir(parents=True, exist_ok=True)
    for src in USER_CONTENT_FIXTURE.iterdir():
        if src.is_file():
            shutil.copy2(src, target / src.name)
    print(f"[harness] Dropped fixture user content into {target}")


def run_cli(query: str, thesis: str, max_age: int, test_mode: bool) -> tuple[Path, int]:
    """Spawn the CLI, watch for its output dir, drop user content,
    pipe scripted inputs, return (run_dir, exit_code)."""
    if not CLI.exists():
        raise FileNotFoundError(f"crypto-research CLI not found at {CLI}")

    args = [str(CLI), query]
    if thesis:
        args.extend(["--thesis", thesis])
    args.extend(["--substack", "--max-age", str(max_age)])
    if test_mode:
        args.append("--test")
    print(f"[harness] Running: {' '.join(args)}")

    before = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build query slug the same way build_output_dir does
    from crypto_research_agent.utils.paths import sanitize_query_slug
    slug = sanitize_query_slug(query)

    proc = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1, cwd=str(REPO),
    )

    run_dir_holder: dict[str, Path] = {}
    user_content_dropped = threading.Event()
    inputs_iter = iter(SCRIPTED_INPUTS)
    inputs_lock = threading.Lock()
    log_lines: list[str] = []
    log_path = REPO / "qa_run.stdout.log"
    log_path.write_text("", encoding="utf-8")

    def reader_thread():
        """Stream subprocess stdout, log it, react to prompt markers."""
        try:
            for line in proc.stdout:
                log_lines.append(line)
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(line)
                # Echo a few key milestones to the harness console
                if any(k in line for k in (
                    "Plan:", "Discovery starting", "Discovery complete",
                    "Substack: retrieved", "passed required-term",
                    "Test mode", "Research summary", "Style card saved",
                    "DOCX written", "Run Summary", "[FEEDBACK]",
                    "[USER CONTENT]", "[NOTICE]", "ERROR", "WARNING"
                )):
                    print(f"  | {line.rstrip()}")

                if "[USER CONTENT]" in line and not user_content_dropped.is_set():
                    # Find run_dir, drop fixture, then send "ready"
                    try:
                        rd = watch_for_run_dir(OUTPUT_DIR, slug, before)
                        run_dir_holder["dir"] = rd
                        drop_user_content_fixture(rd)
                    except Exception as e:
                        print(f"[harness] Failed to drop user content: {e}")
                    user_content_dropped.set()
                    _send_next_input(proc, inputs_iter, inputs_lock,
                                     run_dir_holder, expected="ready")
                elif "[FEEDBACK]" in line:
                    _send_next_input(proc, inputs_iter, inputs_lock,
                                     run_dir_holder)
                elif "[NOTICE]" in line:
                    # Articles+videos empty case — pipe a "2" to continue
                    try:
                        proc.stdin.write("2\n")
                        proc.stdin.flush()
                    except Exception:
                        pass
        except Exception as e:
            print(f"[harness] reader_thread error: {e}")

    t = threading.Thread(target=reader_thread, daemon=True)
    t.start()

    # Wait for completion (with a generous timeout — discovery + analysis
    # + writing for 5 substacks at max-age 30 should be ~30-90 min)
    try:
        proc.wait(timeout=7200)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[harness] CLI exceeded 2-hour timeout — killed")
        return run_dir_holder.get("dir", OUTPUT_DIR), -1

    # Drain remaining output
    t.join(timeout=10)
    return run_dir_holder.get("dir", OUTPUT_DIR), proc.returncode


USER_EDIT_MARKER = "USER MANUALLY ADDED THIS PARAGRAPH FOR QA TESTING."


def _maybe_mutate_article_before_edited(line: str, run_dir: Path | None) -> None:
    """Right before we send 'edited', append a unique marker to article.md so
    that we can verify post-run that the manual edit survived through any
    later accept_revision rewrites (the SectionReview-edited bug fix)."""
    if line != "edited" or run_dir is None:
        return
    art = run_dir / "article.md"
    if not art.exists():
        return
    text = art.read_text(encoding="utf-8")
    if USER_EDIT_MARKER in text:
        return
    # Append the marker just before the next "## " heading (or at end)
    lines = text.splitlines(keepends=True)
    inserted = False
    out: list[str] = []
    seen_first_section = False
    for ln in lines:
        if ln.startswith("## "):
            if seen_first_section and not inserted:
                out.append(f"\n{USER_EDIT_MARKER}\n\n")
                inserted = True
            seen_first_section = True
        out.append(ln)
    if not inserted:
        out.append(f"\n{USER_EDIT_MARKER}\n")
    art.write_text("".join(out), encoding="utf-8")
    print(f"  ! injected QA edit marker into {art.name} before sending 'edited'")


def _send_next_input(proc, inputs_iter, lock, run_dir_holder,
                     *, expected: str | None = None) -> None:
    """Thread-safe: send the next scripted input to the subprocess stdin.
    Mutates the article file before sending 'edited' so we can verify
    the manual-edit-preservation behavior post-run."""
    with lock:
        try:
            line = next(inputs_iter)
        except StopIteration:
            return
        # Slight delay to let the prompt finish printing before we respond
        time.sleep(0.4)
        # If sending 'edited', simulate a real manual edit first
        _maybe_mutate_article_before_edited(line, run_dir_holder.get("dir"))
        try:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            print(f"  > sent: {line!r}")
        except Exception as e:
            print(f"[harness] failed to send input {line!r}: {e}")


def verify_outputs(run_dir: Path) -> dict[str, object]:
    """Inspect the run directory and report findings as a dict."""
    findings: dict[str, object] = {"run_dir": str(run_dir)}
    expected_files = [
        "research_results.md", "research_outline.md",
        "style_card.json", "article.md",
    ]
    for name in expected_files:
        f = run_dir / name
        findings[f"has_{name}"] = f.exists()
        if f.exists():
            findings[f"size_{name}"] = f.stat().st_size

    # Article body checks
    art = run_dir / "article.md"
    if art.exists():
        text = art.read_text(encoding="utf-8")
        findings["article_starts_with_h1"] = text.lstrip().startswith("# ")
        findings["article_has_no_acknowledged"] = "Acknowledged" not in text
        # Section count
        section_count = sum(1 for line in text.splitlines()
                            if line.startswith("## "))
        findings["article_section_count"] = section_count
        # User content reference (the user_content fixture has phrases
        # the LLM should have integrated into the synthesis)
        findings["article_mentions_user_research"] = (
            "research note" in text.lower()
            or "personal observation" in text.lower()
            or "second wave" in text.lower()  # phrase from the user content
            or "rotation" in text.lower()
        )
        # CRITICAL: the manual edit marker should survive any later revisions
        # that triggered a full file rewrite via accept_revision.
        findings["manual_edit_preserved"] = USER_EDIT_MARKER in text

    # Style card checks
    sc = run_dir / "style_card.json"
    if sc.exists():
        import json
        try:
            data = json.loads(sc.read_text(encoding="utf-8"))
            findings["style_card_has_excerpts"] = bool(
                data.get("example_excerpts")
            )
            findings["style_card_has_vocabulary"] = bool(
                data.get("vocabulary", {}).get("preferred")
                or data.get("vocabulary", {}).get("avoided")
            )
            findings["style_card_tone"] = data.get("tone", "")
            findings["style_card_is_fallback"] = (
                data.get("tone") == "analytical and informative"
                and not data.get("example_excerpts")
            )
        except Exception as e:
            findings["style_card_parse_error"] = str(e)

    return findings


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("query", help="Research query")
    p.add_argument("--thesis", default="", help="Thesis direction")
    p.add_argument("--max-age", type=int, default=30)
    p.add_argument("--test", action="store_true",
                   help="Pass --test to the CLI (Haiku for all calls; cheap/fast)")
    args = p.parse_args()

    try:
        setup_mock_csv()
        run_dir, exit_code = run_cli(args.query, args.thesis, args.max_age, args.test)
        print(f"\n[harness] CLI exited with code {exit_code}")
        print(f"[harness] Run dir: {run_dir}")
    finally:
        restore_real_csv()

    findings = verify_outputs(run_dir)
    print("\n=== Output verification ===")
    for k, v in findings.items():
        print(f"  {k}: {v}")
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

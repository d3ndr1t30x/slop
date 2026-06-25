#!/usr/bin/env python3
"""
recon.py — reusable httpx + gowitness pipeline

Usage:
    python3 recon.py --base-dir /home/kali/reconftw-workspace/example.com
    python3 recon.py --base-dir /path/to/workspace --batch-size 20 --httpx-threads 4
    python3 recon.py --base-dir /path/to/workspace --dry-run
"""

import argparse
import subprocess
import time
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


# ----------------------------
# CONFIG
# ----------------------------

@dataclass
class Config:
    base_dir: Path
    httpx_threads: int = 2
    gow_threads: int = 1
    batch_size: int = 10
    chromium_path: str = "/usr/bin/chromium"
    sleep_action_range: tuple = (2, 6)
    sleep_batch_range: tuple = (15, 40)
    sleep_target_range: tuple = (30, 90)
    rescued_filename: str = "rescued_urls.txt"
    dry_run: bool = False

    @property
    def state_file(self) -> Path:
        return self.base_dir / "gowitness_state.log"


# ----------------------------
# TIMING
# ----------------------------

def sleep_action(cfg: Config):
    if not cfg.dry_run:
        time.sleep(random.uniform(*cfg.sleep_action_range))

def sleep_batch(cfg: Config):
    if not cfg.dry_run:
        time.sleep(random.uniform(*cfg.sleep_batch_range))

def sleep_target(cfg: Config):
    if not cfg.dry_run:
        time.sleep(random.uniform(*cfg.sleep_target_range))


# ----------------------------
# STATE (resume system)
# format: target|batch_index
# ----------------------------

def load_state(cfg: Config) -> dict:
    if not cfg.state_file.exists():
        return {}
    state = {}
    for line in cfg.state_file.read_text().splitlines():
        if "|" in line:
            t, b = line.split("|", 1)
            try:
                state[t] = int(b)
            except ValueError:
                pass
    return state

def save_state(cfg: Config, target: str, batch_index: int):
    with open(cfg.state_file, "a") as f:
        f.write(f"{target}|{batch_index}\n")


# ----------------------------
# UTIL
# ----------------------------

def run(cmd: list[str], dry_run: bool = False):
    print("[CMD]", " ".join(cmd))
    if dry_run:
        print("[DRY RUN] skipped")
        return None
    return subprocess.run(cmd, text=True)

def chunk(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield i, lst[i:i + size]

def find_targets(base_dir: Path) -> list[Path]:
    return (
        sorted(base_dir.rglob("katana.txt")) +
        sorted(base_dir.rglob("waybackurls.txt"))
    )


# ----------------------------
# URL RESCUE LAYER
# ----------------------------

URL_REGEX = re.compile(r"https?://[^\s\"'<>]+")

def clean_url(u: str) -> str | None:
    u = u.strip()
    if "<" in u or ">" in u or " " in u:
        return None
    m = URL_REGEX.search(u)
    if m:
        u = m.group(0)
    try:
        p = urlparse(u)
        if p.scheme not in ("http", "https") or not p.netloc:
            return None
        return u
    except Exception:
        return None

def rescue_urls(input_file: Path, output_file: Path) -> list[str]:
    if not input_file.exists():
        return []
    raw = input_file.read_text(errors="ignore").splitlines()
    cleaned = sorted({u for line in raw if (u := clean_url(line))})
    if cleaned:
        output_file.write_text("\n".join(cleaned) + "\n")
    return cleaned


# ----------------------------
# HTTPX
# ----------------------------

def httpx_filter(cfg: Config, input_file: Path, output_file: Path):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    sleep_action(cfg)
    cmd = [
        "httpx",
        "-l", str(input_file),
        "-silent",
        "-threads", str(cfg.httpx_threads),
        "-o", str(output_file),
    ]
    run(cmd, dry_run=cfg.dry_run)


# ----------------------------
# GOWITNESS
# ----------------------------

def gowitness_scan(cfg: Config, target_file: Path, screenshot_dir: Path, db_path: Path):
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    sleep_action(cfg)
    cmd = [
        "gowitness", "scan", "file",
        "-f", str(target_file),
        "--driver", "chromedp",
        "--chrome-path", cfg.chromium_path,
        "--no-http",
        "--log-scan-errors",
        "--delay", "6",
        "-t", str(cfg.gow_threads),
        "--screenshot-path", str(screenshot_dir),
        "--write-db",
        "--write-db-uri", f"sqlite:///{db_path}",
    ]
    run(cmd, dry_run=cfg.dry_run)


# ----------------------------
# PIPELINE
# ----------------------------

def process_target(cfg: Config, file_path: Path, resume_batch: int = 0):
    domain_dir = file_path.parent.parent
    gow_dir = domain_dir / "subdomains" / "gowitness"
    alive_file = gow_dir / "alive_urls.txt"
    rescued_file = gow_dir / cfg.rescued_filename
    targets_file = gow_dir / "targets.txt"
    db_file = gow_dir / "gowitness.sqlite3"
    screenshot_dir = gow_dir / "screenshots"

    print(f"\n=== TARGET: {file_path}")

    httpx_filter(cfg, file_path, alive_file)

    raw_candidates = alive_file if alive_file.exists() else file_path
    urls = rescue_urls(raw_candidates, rescued_file)
    if not urls:
        print("[SKIP] no URL candidates could be rescued from input")
        return

    total_raw = len(raw_candidates.read_text(errors="ignore").splitlines())
    print(f"[RESCUE] total={total_raw} cleaned={len(urls)}")

    for batch_index, batch in chunk(urls, cfg.batch_size):
        if batch_index < resume_batch:
            print(f"[RESUME SKIP] batch {batch_index}")
            continue
        print(f"\n[BATCH {batch_index}] size={len(batch)}")
        targets_file.write_text("\n".join(batch) + "\n")
        gowitness_scan(cfg, targets_file, screenshot_dir, db_file)
        save_state(cfg, str(file_path), batch_index)
        sleep_batch(cfg)


# ----------------------------
# CLI
# ----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="httpx + gowitness recon pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--base-dir", required=True, type=Path,
                   help="Root workspace directory to scan (e.g. reconftw-workspace/example.com)")
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--httpx-threads", type=int, default=2)
    p.add_argument("--gow-threads", type=int, default=1)
    p.add_argument("--chromium-path", default="/usr/bin/chromium")
    p.add_argument("--dry-run", action="store_true",
                   help="Print commands without executing them")
    return p.parse_args()


def main():
    args = parse_args()

    cfg = Config(
        base_dir=args.base_dir,
        batch_size=args.batch_size,
        httpx_threads=args.httpx_threads,
        gow_threads=args.gow_threads,
        chromium_path=args.chromium_path,
        dry_run=args.dry_run,
    )

    print(f"Base dir : {cfg.base_dir}")
    print(f"Dry run  : {cfg.dry_run}")
    print("Loading targets...")

    state = load_state(cfg)
    targets = find_targets(cfg.base_dir)
    print(f"Found {len(targets)} targets")

    for i, t in enumerate(targets):
        t_str = str(t)
        resume_batch = state.get(t_str, 0)
        print(f"\n[{i+1}/{len(targets)}] {t_str}")
        try:
            process_target(cfg, Path(t_str), resume_batch)
            sleep_target(cfg)
        except KeyboardInterrupt:
            print("\n[STOP] graceful shutdown requested")
            break
        except Exception as e:
            print(f"[ERROR] {t_str} -> {e}")
            print("[PAUSING SAFELY]")
            break


if __name__ == "__main__":
    main()

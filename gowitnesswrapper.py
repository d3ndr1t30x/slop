#!/usr/bin/env python3

import subprocess
import time
import random
import re
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path("/home/kali/reconftw-workspace/semgrep.dev")

# keep everything slow and safe
HTTPX_THREADS = 2
GOW_THREADS = 1
BATCH_SIZE = 10

CHROMIUM_PATH = "/usr/bin/chromium"

STATE_FILE = BASE_DIR / "gowitness_state.log"
RESCUED_FILE = "rescued_urls.txt"


# ----------------------------
# SAFE TIMING LAYER
# ----------------------------

def sleep_action():
    time.sleep(random.uniform(2, 6))

def sleep_batch():
    time.sleep(random.uniform(15, 40))

def sleep_target():
    time.sleep(random.uniform(30, 90))


# ----------------------------
# STATE (resume system)
# format: target|batch_index
# ----------------------------

def load_state():
    if not STATE_FILE.exists():
        return {}
    state = {}
    for line in STATE_FILE.read_text().splitlines():
        if "|" in line:
            t, b = line.split("|", 1)
            try:
                state[t] = int(b)
            except:
                pass
    return state


def save_state(target, batch_index):
    with open(STATE_FILE, "a") as f:
        f.write(f"{target}|{batch_index}\n")


# ----------------------------
# UTIL
# ----------------------------

def run(cmd):
    print("[CMD]", " ".join(cmd))
    return subprocess.run(cmd, text=True)


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield i, lst[i:i + size]


def find_targets():
    return sorted(list(BASE_DIR.rglob("katana.txt"))) + sorted(list(BASE_DIR.rglob("waybackurls.txt")))


# ----------------------------
# SMART URL RESCUE LAYER
# ----------------------------

URL_REGEX = re.compile(r"https?://[^\s\"'<>]+")


def clean_url(u: str):
    u = u.strip()

    # kill obvious junk
    if "<" in u or ">" in u:
        return None
    if " " in u:
        return None

    # extract embedded URLs from garbage lines
    m = URL_REGEX.search(u)
    if m:
        u = m.group(0)

    # final parse validation
    try:
        p = urlparse(u)
        if p.scheme not in ["http", "https"]:
            return None
        if not p.netloc:
            return None
        return u
    except:
        return None


def rescue_urls(input_file: Path, output_file: Path):
    if not input_file.exists():
        return []

    raw = input_file.read_text(errors="ignore").splitlines()

    cleaned = []
    for line in raw:
        u = clean_url(line)
        if u:
            cleaned.append(u)

    # dedupe
    cleaned = sorted(set(cleaned))

    if not cleaned:
        return []

    output_file.write_text("\n".join(cleaned) + "\n")
    return cleaned


# ----------------------------
# HTTPX (minimal)
# ----------------------------

def httpx_filter(input_file, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    sleep_action()

    cmd = [
        "httpx",
        "-l", str(input_file),
        "-silent",
        "-threads", str(HTTPX_THREADS),
        "-o", str(output_file),
    ]

    return run(cmd)


# ----------------------------
# GOWITNESS (SAFE MODE)
# ----------------------------

def gowitness_scan(target_file, screenshot_dir, db_path):
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    sleep_action()

    cmd = [
        "gowitness",
        "scan",
        "file",
        "-f", str(target_file),

        "--driver", "chromedp",
        "--chrome-path", CHROMIUM_PATH,

        "--no-http",
        "--log-scan-errors",

        "--delay", "6",

        "-t", str(GOW_THREADS),

        "--screenshot-path", str(screenshot_dir),

        "--write-db",
        "--write-db-uri", f"sqlite:///{db_path}",
    ]

    return run(cmd)


# ----------------------------
# PIPELINE
# ----------------------------

def process_target(file_path: Path, resume_batch=0):
    domain_dir = file_path.parent.parent
    gow_dir = domain_dir / "subdomains" / "gowitness"

    alive_file = gow_dir / "alive_urls.txt"
    rescued_file = gow_dir / RESCUED_FILE
    targets_file = gow_dir / "targets.txt"
    db_file = gow_dir / "gowitness.sqlite3"
    screenshot_dir = gow_dir / "screenshots"

    print(f"\n=== TARGET: {file_path}")

    # 1. httpx filter (optional sanity pass)
    httpx_filter(file_path, alive_file)

    # 2. SMART RESCUE (this is the important part)
    raw_candidates = alive_file if alive_file.exists() else file_path

    urls = rescue_urls(raw_candidates, rescued_file)

    if not urls:
        print("[SKIP] no URL candidates could be rescued from input")
        return

    print(f"[RESCUE] total={len(open(raw_candidates).read().splitlines())} cleaned={len(urls)}")

    batches = list(chunk(urls, BATCH_SIZE))

    for batch_index, batch in batches:
        if batch_index < resume_batch:
            print(f"[RESUME SKIP] batch {batch_index}")
            continue

        print(f"\n[BATCH {batch_index}] size={len(batch)}")

        targets_file.write_text("\n".join(batch) + "\n")

        gowitness_scan(targets_file, screenshot_dir, db_file)

        save_state(str(file_path), batch_index)

        sleep_batch()


# ----------------------------
# MAIN
# ----------------------------

def main():
    print("Loading targets...")

    state = load_state()
    targets = find_targets()

    print(f"Found {len(targets)} targets")

    for i, t in enumerate(targets):
        t = str(t)

        resume_batch = state.get(t, 0)

        print(f"\n[{i+1}/{len(targets)}] {t}")

        try:
            process_target(Path(t), resume_batch)

            sleep_target()

        except KeyboardInterrupt:
            print("\n[STOP] graceful shutdown requested")
            break

        except Exception as e:
            print(f"[ERROR] {t} -> {e}")
            print("[PAUSING SAFELY]")
            break


if __name__ == "__main__":
    main()
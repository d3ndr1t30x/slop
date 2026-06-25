# recon.py

A Python script that screenshots websites very, very slowly, on purpose. You're welcome.

---

## What It Does

Takes a list of URLs you definitely found ethically, runs them through `httpx` to confirm they exist (groundbreaking), then points `gowitness` at each one to take screenshots you'll look at once and never open again.

Also rescues malformed URLs from your recon tool output, because apparently `katana` and `waybackurls` need a babysitter.

---

## Requirements

- Python 3.10+
- `httpx` installed and on your PATH
- `gowitness` installed and on your PATH
- Chromium, specifically at `/usr/bin/chromium`, unless you tell it otherwise like an adult
- A reconftw workspace you generated at some point and then immediately forgot the structure of
- Time. A lot of time. This is not a fast script. This is the opposite of a fast script.
- I made it that way on purpose because my router is shite and crashed my whole home network the first time I ran this. 

---

## Installation

```bash
git clone <your repo>
cd <your repo>
# that's it. it's one file.
```

---

## Usage

```bash
python3 recon.py --base-dir /home/kali/reconftw-workspace/target.com
```

### All Flags

| Flag | Default | Purpose |
|---|---|---|
| `--base-dir` | required, figure it out | The reconftw workspace you want to run against |
| `--batch-size` | 10 | URLs per gowitness batch. Lower = slower = safer = more boring |
| `--httpx-threads` | 2 | Two. On purpose. Don't touch it. |
| `--gow-threads` | 1 | One. Also on purpose. This isn't a race. |
| `--chromium-path` | `/usr/bin/chromium` | In case your Chromium is somewhere unusual, like a normal OS |
| `--dry-run` | off | Prints all the commands without running them, for when you want to feel productive |

---

## How Slow Is It?

Very.

- Between individual actions: 2–6 seconds
- Between batches: 15–40 seconds
- Between targets: 30–90 seconds

If you came here for speed, you have made a navigational error.

---

## The Resume System

The script writes a state file (`gowitness_state.log`) so it can pick up where it left off after crashing, losing network, or having a crisis of motivation. It tracks progress as `target_path|batch_index`.

It will not help you if you delete the file. Don't delete the file.

---

## The URL Rescue Layer

Your recon tools output garbage. This is known. `rescue_urls()` extracts valid HTTP/HTTPS URLs from lines containing HTML fragments, whitespace, angle brackets, and what appears to be abstract art. It does its best. Sometimes its best is `[]`.

Cleaned URLs land in `rescued_urls.txt` inside each target's gowitness directory, deduplicated and sorted, because someone has to have standards.

---

## Output Structure

For each target file found, outputs land under:

```
<domain>/subdomains/gowitness/
├── alive_urls.txt       # httpx survivors
├── rescued_urls.txt     # what actually made it through cleaning
├── targets.txt          # current batch (overwritten each time, intentionally)
├── gowitness.sqlite3    # screenshot database
└── screenshots/         # the whole point
```

---

## Ethical Use

This tool is for authorised security assessments only. If you're running it against something you don't have permission to test, you've made a different kind of error than the navigational one mentioned earlier.

---

## FAQ

**Why is it so slow?**
Because you're not the only person on the internet.

**Can I make it faster?**
Yes. You can also make it get you blocked. These are related.

**Why does it stop on error instead of continuing?**
Because silently continuing through errors is how you end up with a half-finished scan and no idea what failed. It pauses. You check. You re-run. This is the way.

**The dry run shows my commands. Why won't it run them?**
That's what dry run means.

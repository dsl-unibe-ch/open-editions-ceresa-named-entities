import re, sys

# run: python make-printable.py < pares.md > pares-print.md

BASE_URL = "https://asciinema.org/a/CvUyVktwWlx02NTE"
TIMESTAMPS = [43, 165, 194]  # seconds, one per bash snippet

note_template = """
For executed code see: {url}
===
"""

out = []
pending_note = False
ts_idx = 0

for line in sys.stdin:
    # Strip +pty* from ```bash fences
    if re.match(r"^```bash\b.*\+pty", line):
        line = re.sub(r"\s+\+pty[^\n]*", "", line)
        pending_note = True
    out.append(line)

    # On closing fence, append the note with the next timestamp (if any)
    if pending_note and line.strip() == "```":
        ts = TIMESTAMPS[ts_idx] if ts_idx < len(TIMESTAMPS) else None
        url = f"{BASE_URL}?t={ts}" if ts is not None else BASE_URL
        out.append(note_template.format(url=url))
        ts_idx += 1
        pending_note = False

sys.stdout.writelines(out)

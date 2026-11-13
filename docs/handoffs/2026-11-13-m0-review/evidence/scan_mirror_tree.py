#!/usr/bin/env python3
"""Reviewer's scan of the committed server mirror, ledger snapshots and the
M0 execution handoff document (2026-11-13 M0 review).

It reads files only and never imports or executes them. Every address-like
or secret-like value is masked in its own output.

Usage
  mkdir <dir>
  git archive <commit> docs/paper-sim/server-mirror docs/paper-sim/ledger-snapshots \
      docs/handoffs/2026-11-12-m0-execution-review.md | tar -x -C <dir>
  python3 -I scan_mirror_tree.py <dir>
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import sys
from collections import Counter
from pathlib import Path

root = Path(sys.argv[1])
mirror = root / "docs/paper-sim/server-mirror"
TOP_DOCS = {
    "FX-04-wiring-proof.md", "MANIFEST-NOT-MIRRORED.md", "MANIFEST.sha256",
    "REDACTIONS.md", "REPLACEMENT-MAP.md", "VERSION-CHECKIN.md",
}
DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- 1. MANIFEST.sha256: TAB-separated sha256, size, server mtime, path ----
entries: dict[str, tuple[str, int]] = {}
comment_lines = 0
for line in (mirror / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
    parts = line.split("\t")
    if len(parts) >= 4 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
        entries[parts[-1].strip()] = (parts[0], int(parts[1]))
    elif line.strip():
        comment_lines += 1
files = {p.relative_to(mirror).as_posix(): p for p in mirror.rglob("*") if p.is_file()}
scripts = {k: v for k, v in files.items() if k not in TOP_DOCS}
hash_mismatch = sorted(k for k, (h, _) in entries.items() if k in files and sha(files[k]) != h)
size_mismatch = sorted(k for k, (_, size) in entries.items() if k in files and files[k].stat().st_size != size)
print(f"[manifest] entries={len(entries)} header/comment lines={comment_lines} files in tree={len(files)} "
      f"(top-level docs={len(files) - len(scripts)}, scripts={len(scripts)})")
print(f"[manifest] hash mismatch={len(hash_mismatch)} size mismatch={len(size_mismatch)} "
      f"listed but absent={sum(1 for k in entries if k not in files)} "
      f"scripts not listed={sum(1 for k in scripts if k not in entries)}")
for k in hash_mismatch:
    print("   HASH MISMATCH", k)
for k in size_mismatch:
    print("   size column differs from the committed file:", k)
print(f"[manifest] sum of listed sizes={sum(size for _, size in entries.values())} "
      f"largest committed script={max(p.stat().st_size for p in scripts.values())} bytes")

# ---- 2. REDACTIONS.md rows (paths are relative to docs/paper-sim/) ---------
rows = re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([0-9a-f]{64})\s*\|$",
                  (mirror / "REDACTIONS.md").read_text(encoding="utf-8"), flags=re.M)
ok = 0
for path, _original, redacted in rows:
    target = root / "docs/paper-sim" / path
    good = target.is_file() and sha(target) == redacted
    ok += good
    if not good:
        print("   REDACTION ROW DOES NOT MATCH THE COMMITTED FILE:", path)
print(f"[redactions] rows={len(rows)} rows whose 'redacted sha256' equals the committed file={ok}")

# ---- 3. addresses, secrets, e-mail ----------------------------------------
ipv4 = re.compile(r"(?<![\d.])(\d{1,3})\\?\.(\d{1,3})\\?\.(\d{1,3})\\?\.(\d{1,3})(?![\d.])")
secret_res = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "pgpassword": re.compile(r"PGPASSWORD\s*=\s*['\"]?[^\s'\"$]{4,}"),
    "dsn_password": re.compile(r"(?i)postgres(?:ql)?://[^\s:@/]+:[^\s@/]+@"),
    "password_kv": re.compile(r"(?i)\bpassword\s*[=:]\s*['\"][^'\"\s]{4,}['\"]"),
    "api_key_kv": re.compile(r"(?i)\b(api[_-]?key|apikey|secret|token|bearer)\b\s*[=:]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    "sk_key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "webhook": re.compile(r"hooks\.slack\.com/services/|discord(?:app)?\.com/api/webhooks/"),
    "telegram_bot": re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{30,}\b"),
    "cookie_header": re.compile(r"(?i)['\"]cookie['\"]\s*:\s*['\"][^'\"]{20,}"),
    "auth_header": re.compile(r"(?i)['\"](x-api-key|authorization)['\"]\s*:\s*['\"][^'\"]{12,}"),
}
email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
hits: Counter[str] = Counter()
details: list[str] = []
scan_files = sorted(p for p in root.rglob("*") if p.is_file())
for path in scan_files:
    rel = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        hits["not_utf8"] += 1
        details.append(f"not UTF-8: {rel}")
        continue
    for number, line in enumerate(text.splitlines(), 1):
        for match in ipv4.finditer(line):
            octets = [int(x) for x in match.groups()]
            if any(x > 255 for x in octets):
                continue
            address = ipaddress.ip_address(".".join(map(str, octets)))
            if not address.is_global and not any(address in net for net in DOC_NETS):
                continue  # loopback / private / reserved
            kind = "documentation-range" if any(address in net for net in DOC_NETS) else "public"
            form = "regex-escaped" if "\\" in match.group(0) else "plain"
            hits[f"ipv4_{kind}"] += 1
            details.append(f"IPv4-like ({kind}, {form}, value masked): {rel}:{number}")
        for name, pattern in secret_res.items():
            if pattern.search(line):
                hits[name] += 1
                details.append(f"{name} (value masked): {rel}:{number}")
        for match in email.finditer(line):
            hits["email"] += 1
            details.append(f"e-mail address (masked): {rel}:{number}")
print(f"[scan] files scanned={len(scan_files)} hit counts={dict(hits)}")
for item in details:
    print("   ", item)

# ---- 4. redaction placeholder census --------------------------------------
census = Counter()
for path in scan_files:
    try:
        count = path.read_text(encoding="utf-8").count("SERVER_HOST_REDACTED")
    except UnicodeDecodeError:
        continue
    if count:
        census[path.relative_to(root).as_posix()] = count
print(f"[placeholder] files containing SERVER_HOST_REDACTED={len(census)} occurrences={sum(census.values())}")
for rel, count in sorted(census.items()):
    print(f"    {count} {rel}")

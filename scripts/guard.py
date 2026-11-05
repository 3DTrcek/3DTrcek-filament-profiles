#!/usr/bin/env python3
"""Safety guard for issues and comments.

Anyone on GitHub can open an issue or write a comment and attach a file. This guard runs on
every new or edited issue/comment from someone outside the 3DTrcek team and:

  * downloads every attached file and runs the same safety scan used for the profile library
    (plain text only, no executables inside archives, no post-processing scripts, no dangerous
    G-code). Anything that fails is REMOVED from the text and replaced with a warning, and the
    issue gets the `suspicious` label.
  * flags links to websites outside a short allow-list with the `link-review` label, so a
    maintainer looks at them. These links are not removed.

The text is untrusted: it is only parsed in Python and passed to `gh` as separate arguments,
never through a shell.

Local test:  python scripts/guard.py --dry-run event.json [attachment-name=local-path ...]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import safety  # noqa: E402
import profiles as lib  # noqa: E402

TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
MAX_DOWNLOAD = 10 * 1024 * 1024
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov"}
# .zip is allowed only as a wrapper for upload – the library itself never stores plain zips.
ALLOWED_EXT = lib.ALL_EXT | {".zip", ".txt", ".log", ".3mf"} | IMAGE_EXT
ALLOWED_HOSTS = {
    "github.com", "raw.githubusercontent.com", "user-images.githubusercontent.com",
    "private-user-images.githubusercontent.com", "3dtrcek.com", "www.3dtrcek.com",
    "printables.com", "www.printables.com", "makerworld.com", "www.thingiverse.com", "thingiverse.com",
    "youtube.com", "www.youtube.com", "youtu.be", "bambulab.com", "wiki.bambulab.com",
    "prusa3d.com", "www.prusa3d.com", "help.prusa3d.com", "ultimaker.com", "orcaslicer.com",
}
FILE_LINK = re.compile(
    r"\[(?P<name>[^\]]+)\]\((?P<url>https://github\.com/(?:user-attachments/files|[^)\s]+/files)/[^)\s]+)\)")
ANY_URL = re.compile(r"https?://[^\s)\]>\"']+")
REMOVED = "⚠️ *attachment removed by the 3DTrcek safety check*"


def scan_attachment(name: str, data: bytes) -> list[str]:
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        return [f"file type '{ext or '(none)'}' is not allowed"]
    if ext in IMAGE_EXT:
        return []
    if ext == ".3mf":
        return []  # a 3mf is a zip of model data; it is never published from an issue, only read by the team
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / f"attachment{ext}"
        p.write_bytes(data)
        errors, _, _ = safety.scan_file(p, name)
    return errors


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "3DTrcek-safety-guard"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("larger than 10 MB")
    return data


def check(text: str, fetch) -> tuple[str, list[str], list[str], list[str]]:
    """Return (cleaned_text, removed_reasons, unverified, unknown_links)."""
    removed: list[str] = []
    unverified: list[str] = []
    attachment_urls = set()

    def repl(m: re.Match) -> str:
        name, url = m.group("name"), m.group("url")
        attachment_urls.add(url)
        try:
            problems = scan_attachment(name, fetch(name, url))
        except Exception as e:  # noqa: BLE001 – any failure to fetch means "could not verify"
            unverified.append(f"`{name}`: could not be scanned ({e})")
            return m.group(0)
        if problems:
            removed.append(f"`{name}`: " + "; ".join(problems))
            return REMOVED
        return m.group(0)

    cleaned = FILE_LINK.sub(repl, text or "")
    unknown = []
    for url in ANY_URL.findall(cleaned):
        if url in attachment_urls:
            continue
        host = (urlparse(url).hostname or "").lower()
        if host and host not in ALLOWED_HOSTS and not host.endswith(".github.com"):
            unknown.append(url)
    return cleaned, removed, unverified, sorted(set(unknown))


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    args = [a for a in argv if not a.startswith("--")]
    event = json.loads(Path(args[0] if args else os.environ["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    local = dict(a.split("=", 1) for a in args[1:])
    repo = os.environ.get("GITHUB_REPOSITORY", lib.REPO)

    is_comment = "comment" in event
    item = event["comment"] if is_comment else event["issue"]
    number = event["issue"]["number"]
    if item.get("author_association") in TRUSTED or item["user"].get("type") == "Bot":
        print("Trusted author – skipping.")
        return 0

    def fetch(name: str, url: str) -> bytes:
        return Path(local[name]).read_bytes() if name in local else download(url)

    cleaned, removed, unverified, unknown = check(item.get("body") or "", fetch)
    report = {"removed": removed, "unverified": unverified, "unknown_links": unknown}
    print(json.dumps(report, indent=2))
    if dry or not (removed or unverified or unknown):
        return 0

    if removed:
        endpoint = (f"repos/{repo}/issues/comments/{item['id']}" if is_comment
                    else f"repos/{repo}/issues/{number}")
        gh("api", "-X", "PATCH", endpoint, "-f", f"body={cleaned}")
        gh("issue", "edit", str(number), "--repo", repo, "--add-label", "suspicious")
        gh("issue", "comment", str(number), "--repo", repo, "--body",
           "🛡️ **Safety check:** an attached file failed the security scan and was removed.\n\n"
           + "\n".join(f"- {r}" for r in removed)
           + "\n\nProfiles must be plain slicer exports (`.json`, `.ini`, `.bbsflmt`, `.orca_filament`, "
             "`.curaprofile`…) or a zip of those. **Only download profiles from the "
             f"[catalog](https://github.com/{repo}/blob/main/CATALOG.md), never from issues or comments.**")
    if unverified or unknown:
        gh("issue", "edit", str(number), "--repo", repo, "--add-label", "link-review")
        lines = [f"- {u}" for u in unverified] + [f"- link to an outside site: `{u}`" for u in unknown]
        gh("issue", "comment", str(number), "--repo", repo, "--body",
           "🛡️ **Safety check:** a maintainer will review the following before anyone should open it:\n\n"
           + "\n".join(lines)
           + f"\n\nOnly download profiles from the [catalog](https://github.com/{repo}/blob/main/CATALOG.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

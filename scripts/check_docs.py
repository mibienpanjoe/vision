import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[1]
files = [
    root / "README.md",
    root / "CONTRIBUTING.md",
    root / "SECURITY.md",
    *sorted((root / "docs").rglob("*.md")),
    *sorted((root / "assets").rglob("*.md")),
    *sorted((root / "apps/web").glob("*.md")),
]
errors = []
links = 0
examples = 0


def anchors(path):
    content = path.read_text()
    ids = []
    counts = {}
    fenced = False
    for line in content.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        m = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if not m:
            continue
        label = re.sub(r"<[^>]+>", "", m[1])
        label = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", label)
        label = label.lower().strip()
        label = "".join(c for c in label if c.isalnum() or c in " _-")
        label = label.replace(" ", "-")
        count = counts.get(label, 0)
        counts[label] = count + 1
        ids.append(label if count == 0 else f"{label}-{count}")
    return ids


for path in files:
    text = path.read_text()
    if sum(1 for line in text.splitlines() if line.startswith("```")) % 2:
        errors.append(f"{path.relative_to(root)}: unbalanced fence")
    for index, line in enumerate(text.splitlines(), 1):
        if line.rstrip() != line and not line.endswith("  "):
            errors.append(f"{path.relative_to(root)}:{index}: trailing whitespace")
    for value in re.findall(r"```json\s*\n(.*?)\n```", text, re.DOTALL):
        examples += 1
        try:
            json.loads(value)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(root)}: JSON: {exc}")
    stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    targets = re.findall(r"\]\(([^)]+)\)", stripped)
    targets += re.findall(r'(?:href|src)="([^"]+)"', stripped)
    for target in targets:
        target = html.unescape(target.strip().strip("<>"))
        if urlsplit(target).scheme or target.startswith("//"):
            continue
        links += 1
        name, _, fragment = target.partition("#")
        dest = (path.parent / unquote(name)).resolve() if name else path
        if not dest.exists():
            errors.append(f"{path.relative_to(root)}: missing {target}")
        elif (
            fragment and dest.suffix == ".md" and unquote(fragment) not in anchors(dest)
        ):
            errors.append(f"{path.relative_to(root)}: missing anchor {target}")

req = (root / "docs/product/requirements-and-acceptance.md").read_text()
defs = set(re.findall(r"\| (REQ-\d+) \|", req))
used = set()
for path in files:
    used.update(re.findall(r"REQ-\d+", path.read_text()))
if defs != {f"REQ-{i:02}" for i in range(1, 23)}:
    errors.append("Requirements are not exactly REQ-01..REQ-22")
if used - defs:
    errors.append(f"Undefined requirements: {used - defs}")
for name, expected in {
    "docs/architecture/retrieval-strategy.md": "6bf4371ca369dba8f46a057ef7dd219b4a0b90d1a3a6ddb34f9ec8d6f6217542",
    "Icon direction.png": "c95d03220884b7b55fbbac28b662f2f714a6a15e0d916143a167d553aa38346f",
}.items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
        errors.append(f"Source changed: {name}")
for name in ["project_overview.md", "retrieval_strategy.md"]:
    if (root / name).exists():
        errors.append(f"Root source duplicate: {name}")
print(
    json.dumps(
        {
            "markdown_files": len(files),
            "relative_links": links,
            "json_examples": examples,
            "requirements": len(defs),
            "errors": errors,
        },
        indent=2,
    )
)
raise SystemExit(bool(errors))

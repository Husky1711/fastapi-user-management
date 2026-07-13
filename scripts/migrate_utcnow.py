"""One-shot: replace datetime.utcnow() with utc_now() across app code."""

from __future__ import annotations

from pathlib import Path

ROOTS = [Path("services"), Path("routes"), Path("utils"), Path("dependencies"), Path("config")]
SKIP = {"auto_refresh_middleware.py", "auto_refresh_service.py", "datetime_utc.py", "migrate_utcnow.py"}


def ensure_import(text: str) -> str:
    if "from utils.datetime_utc import utc_now" in text:
        return text
    lines = text.splitlines(keepends=True)
    insert_at = 0
    i = 0
    if i < len(lines) and lines[i].startswith("#!"):
        i += 1
    if i < len(lines) and '"""' in lines[i]:
        if lines[i].count('"""') >= 2:
            i += 1
        else:
            i += 1
            while i < len(lines) and '"""' not in lines[i]:
                i += 1
            i += 1
    while i < len(lines) and (
        lines[i].startswith("from __future__") or lines[i].strip() == ""
    ):
        if lines[i].startswith("from __future__"):
            i += 1
            insert_at = i
            break
        i += 1
    else:
        insert_at = i
    for idx, line in enumerate(lines):
        if line.startswith("from utils.") or line.startswith("import utils"):
            insert_at = idx
            break
    lines.insert(insert_at, "from utils.datetime_utc import utc_now\n")
    return "".join(lines)


def main() -> None:
    changed: list[str] = []
    for root in ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.name in SKIP:
                continue
            text = path.read_text(encoding="utf-8")
            if "datetime.utcnow()" not in text and "default_factory=datetime.utcnow" not in text:
                continue
            new = ensure_import(text)
            new = new.replace("datetime.utcnow()", "utc_now()")
            new = new.replace("default_factory=datetime.utcnow", "default_factory=utc_now")
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed.append(str(path))
    print(f"updated {len(changed)} files")
    for p in changed:
        print(f"  {p}")


if __name__ == "__main__":
    main()

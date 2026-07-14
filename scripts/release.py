import argparse
import re
import sys
from pathlib import Path


VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def read_collection_version(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip().strip("'\"")
            if VERSION_RE.fullmatch(version):
                return version
            raise ValueError("galaxy.yml contains an invalid semantic version: %s" % version)
    raise ValueError("galaxy.yml does not contain a version field")


def normalize_tag(tag: str) -> str:
    value = tag.strip()
    if value.startswith("refs/tags/"):
        value = value[len("refs/tags/"):]
    if value.startswith("v"):
        value = value[1:]
    if not VERSION_RE.fullmatch(value):
        raise ValueError("release tag must use vMAJOR.MINOR.PATCH")
    return value


def changelog_section(path: Path, version: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = re.compile(r"^##\s+" + re.escape(version) + r"(?:\s|$)")
    start = next((index for index, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise ValueError("CHANGELOG.md has no section for %s" % version)

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    section = "\n".join(lines[start + 1:end]).strip()
    if not section:
        raise ValueError("CHANGELOG.md section for %s is empty" % version)
    return section + "\n"


def validate(tag: str, root: Path) -> tuple[str, str]:
    version = normalize_tag(tag)
    collection_version = read_collection_version(root / "galaxy.yml")
    if collection_version != version:
        raise ValueError(
            "tag version %s does not match galaxy.yml version %s"
            % (version, collection_version)
        )

    notes = changelog_section(root / "CHANGELOG.md", version)
    expected_archive = "mraibo-yacompress-%s.tar.gz" % version
    return expected_archive, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate YaCompress release metadata")
    parser.add_argument("tag", help="Release tag, for example v1.5.0")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--notes-output", type=Path)
    args = parser.parse_args()

    try:
        archive, notes = validate(args.tag, args.root.resolve())
    except (OSError, ValueError) as exc:
        print("release validation failed: %s" % exc, file=sys.stderr)
        return 1

    if args.notes_output:
        args.notes_output.write_text(notes, encoding="utf-8")

    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

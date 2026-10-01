import argparse
import os
import re
import sys
import zipfile


FRONTMATTER_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PLACEHOLDER_PATTERN = re.compile(r"\$\{[A-Z][A-Z0-9_]*\}")
PLUGIN_DIRECTORY_PATTERN = re.compile(r"^\.[a-z0-9-]*plugin$")
BACKTICK_PATTERN = re.compile(r"`([^`]+)`")
FRONTMATTER_LINE_PATTERN = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")


def package_files(root):
    for current, directories, filenames in os.walk(root):
        directories.sort()
        for filename in sorted(filenames):
            yield os.path.join(current, filename)


def collect_failures(root):
    failures = []
    root = os.path.abspath(root)
    skill_files = [
        path
        for path in package_files(root)
        if os.path.basename(path) == "SKILL.md"
    ]
    if len(skill_files) != 1:
        failures.append("Expected exactly one file named SKILL.md; found {}.".format(len(skill_files)))

    for current, directories, filenames in os.walk(root):
        for directory in directories:
            if PLUGIN_DIRECTORY_PATTERN.match(directory):
                failures.append("Plugin manifest directory is not allowed: {}.".format(
                    os.path.relpath(os.path.join(current, directory), root)
                ))
        for filename in filenames:
            if filename in ("plugin.json", "marketplace.json"):
                failures.append("Manifest file is not allowed: {}.".format(
                    os.path.relpath(os.path.join(current, filename), root)
                ))

    skill_path = os.path.join(root, "SKILL.md")
    skill_text = None
    if not os.path.isfile(skill_path):
        failures.append("The package root must contain SKILL.md.")
    else:
        with open(skill_path, "r", encoding="utf-8") as source:
            skill_text = source.read()
        lines = skill_text.splitlines()
        frontmatter = {}
        if not lines or lines[0] != "---":
            failures.append("SKILL.md must start with a --- frontmatter delimiter.")
        else:
            closing_index = next(
                (index for index in range(1, len(lines)) if lines[index] == "---"),
                None,
            )
            if closing_index is None:
                failures.append("SKILL.md frontmatter must have a closing --- delimiter.")
            else:
                for line in lines[1:closing_index]:
                    if not line.strip():
                        continue
                    match = FRONTMATTER_LINE_PATTERN.match(line)
                    if not match:
                        failures.append("Invalid frontmatter line: {!r}.".format(line))
                        continue
                    key, value = match.groups()
                    if key not in FRONTMATTER_KEYS:
                        failures.append("Unsupported frontmatter key: {}.".format(key))
                    frontmatter[key] = value.strip()

                name = frontmatter.get("name", "")
                directory_name = os.path.basename(os.path.normpath(root))
                if not NAME_PATTERN.fullmatch(name):
                    failures.append("Frontmatter name must be a lowercase hyphenated name.")
                if len(name) > 64:
                    failures.append("Frontmatter name must be at most 64 characters.")
                if name != directory_name:
                    failures.append("Frontmatter name must equal the package directory name.")
                description = frontmatter.get("description", "")
                if not description:
                    failures.append("Frontmatter description must not be empty.")
                if len(description) > 1024:
                    failures.append("Frontmatter description must be at most 1024 characters.")

        if skill_text is not None:
            for match in BACKTICK_PATTERN.finditer(skill_text):
                token = match.group(1)
                if "<" in token:
                    continue
                if token.startswith("references/") or token.startswith("scripts/"):
                    if not os.path.isfile(os.path.join(root, token)):
                        failures.append("Referenced package path does not exist: {}.".format(token))

    for path in package_files(root):
        if path.lower().endswith(".md"):
            with open(path, "r", encoding="utf-8") as source:
                if PLACEHOLDER_PATTERN.search(source.read()):
                    failures.append("Environment placeholder found in {}.".format(
                        os.path.relpath(path, root)
                    ))

    return failures


def write_zip(root, output_path):
    root = os.path.abspath(root)
    output_path = os.path.abspath(output_path)
    name = os.path.basename(os.path.normpath(root))
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in package_files(root):
            relative = os.path.relpath(path, root)
            parts = relative.split(os.sep)
            if "tests" in parts or "__pycache__" in parts or path.endswith(".pyc"):
                continue
            if os.path.abspath(path) == output_path:
                continue
            archive.write(path, os.path.join(name, relative))


def validate_zip(output_path):
    failures = []
    with zipfile.ZipFile(output_path, "r") as archive:
        members = archive.namelist()
    skill_members = [member for member in members if member.rsplit("/", 1)[-1] == "SKILL.md"]
    if len(skill_members) != 1:
        failures.append("ZIP must contain exactly one SKILL.md member; found {}.".format(
            len(skill_members)
        ))
    for member in members:
        parts = member.split("/")
        if any(PLUGIN_DIRECTORY_PATTERN.match(part) for part in parts):
            failures.append("ZIP contains a plugin manifest directory: {}.".format(member))
        if parts[-1] in ("plugin.json", "marketplace.json"):
            failures.append("ZIP contains a manifest file: {}.".format(member))
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_directory")
    parser.add_argument("--zip", dest="zip_path")
    args = parser.parse_args()

    if not os.path.isdir(args.skill_directory):
        print("Skill directory does not exist: {}".format(args.skill_directory), file=sys.stderr)
        return 1

    failures = collect_failures(args.skill_directory)
    if args.zip_path:
        try:
            write_zip(args.skill_directory, args.zip_path)
            failures.extend(validate_zip(args.zip_path))
        except (OSError, zipfile.BadZipFile) as error:
            failures.append("Could not create or verify ZIP: {}".format(error))

    if failures:
        for failure in failures:
            print("FAIL: {}".format(failure))
        return 1

    print("Skill package validation passed.")
    if args.zip_path:
        print("ZIP package validated: {}".format(args.zip_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())

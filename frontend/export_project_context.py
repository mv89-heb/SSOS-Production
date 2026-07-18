import os
from pathlib import Path


OUTPUT_FILE = "frontend_full_context.txt"


EXCLUDED_DIRS = {
    "node_modules",
    ".next",
    ".git",
    "dist",
    "build",
    ".cache",
    "coverage",
    ".turbo",
    "out"
}


EXCLUDED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    OUTPUT_FILE
}


INCLUDED_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".css",
    ".scss",
    ".md",
    ".d.ts"
}


IMPORTANT_FILES = {
    "package.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "middleware.ts",
    "tsconfig.json"
}


def should_ignore(path: Path):

    for part in path.parts:
        if part in EXCLUDED_DIRS:
            return True

    if path.name in EXCLUDED_FILES:
        return True

    return False


def is_relevant_file(path: Path):

    if path.name in IMPORTANT_FILES:
        return True

    return path.suffix in INCLUDED_EXTENSIONS


def export_tree(root, output):

    output.write("\n")
    output.write("=" * 80)
    output.write("\nPROJECT STRUCTURE\n")
    output.write("=" * 80)
    output.write("\n\n")

    for path in sorted(root.rglob("*")):

        if should_ignore(path):
            continue

        relative = path.relative_to(root)

        if path.is_dir():
            output.write(f"[DIR ] {relative}\n")

        else:
            output.write(f"[FILE] {relative}\n")


def export_sources(root, output):

    output.write("\n\n")
    output.write("=" * 80)
    output.write("\nSOURCE FILES\n")
    output.write("=" * 80)


    counter = 0
    total_lines = 0


    for path in sorted(root.rglob("*")):

        if should_ignore(path):
            continue

        if not path.is_file():
            continue

        if not is_relevant_file(path):
            continue


        counter += 1

        relative = path.relative_to(root)


        output.write("\n\n")
        output.write("#" * 80)
        output.write("\n")
        output.write(f"# FILE: {relative}\n")
        output.write("#" * 80)
        output.write("\n\n")


        try:

            content = path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            output.write(content)

            total_lines += len(content.splitlines())


        except Exception as e:

            output.write(
                f"\nERROR READING FILE: {e}\n"
            )


    output.write("\n\n")
    output.write("=" * 80)
    output.write("\nEXPORT SUMMARY\n")
    output.write("=" * 80)

    output.write(
        f"\nFiles exported: {counter}"
    )

    output.write(
        f"\nTotal lines: {total_lines}"
    )


def main():

    root = Path(".")


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as output:

        export_tree(root, output)

        export_sources(root, output)


    print(
        f"\nCompleted successfully:"
        f"\n{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
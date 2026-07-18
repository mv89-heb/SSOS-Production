import os
from pathlib import Path
from datetime import datetime


# ============================
# הגדרות
# ============================

PROJECT_ROOT = Path(".")
OUTPUT_FILE = "project_export.txt"


IGNORE_DIRS = {
    "node_modules",
    ".next",
    ".git",
    ".vercel",
    "dist",
    "build",
    "__pycache__"
}


INCLUDE_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".css",
    ".scss",
    ".env",
    ".md",
    ".py"
}


MAX_FILE_SIZE_MB = 2


# ============================
# עזר
# ============================

def should_ignore(path):
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    return False



def is_code_file(path):
    return (
        path.suffix in INCLUDE_EXTENSIONS
        or path.name.startswith(".env")
    )



def print_tree(root, file):

    file.write("\n\n")
    file.write("=" * 80)
    file.write("\nPROJECT STRUCTURE\n")
    file.write("=" * 80)
    file.write("\n\n")


    for path in sorted(root.rglob("*")):

        if should_ignore(path):
            continue

        relative = path.relative_to(root)

        depth = len(relative.parts) - 1

        indent = "    " * depth


        if path.is_dir():
            file.write(
                f"{indent}📁 {path.name}/\n"
            )

        else:
            file.write(
                f"{indent}📄 {path.name}\n"
            )



def export_files(root, file):

    file.write("\n\n")
    file.write("=" * 80)
    file.write("\nSOURCE FILES\n")
    file.write("=" * 80)


    for path in sorted(root.rglob("*")):

        if not path.is_file():
            continue

        if should_ignore(path):
            continue

        if not is_code_file(path):
            continue


        size_mb = path.stat().st_size / 1024 / 1024

        if size_mb > MAX_FILE_SIZE_MB:
            continue


        relative = path.relative_to(root)


        file.write("\n\n")
        file.write("#" * 80)
        file.write("\n")
        file.write(
            f"FILE: {relative}\n"
        )
        file.write("#" * 80)
        file.write("\n\n")


        try:
            content = path.read_text(
                encoding="utf-8"
            )

            file.write(content)

        except Exception as e:

            file.write(
                f"\n[ERROR READING FILE: {e}]"
            )



# ============================
# הרצה
# ============================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(
        "SSOS PROJECT EXPORT\n"
    )

    f.write(
        f"Generated: {datetime.now()}\n"
    )


    print_tree(
        PROJECT_ROOT,
        f
    )


    export_files(
        PROJECT_ROOT,
        f
    )


print(
    f"Done! Created: {OUTPUT_FILE}"
)
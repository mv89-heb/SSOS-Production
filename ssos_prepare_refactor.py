from pathlib import Path
import subprocess
import json
import datetime
import sys


ROOT = Path(".")
REPORT = Path("baseline_audit")



def run(cmd, cwd=None):

    print("\n>", cmd)

    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        text=True,
        capture_output=True
    )

    return {
        "command": cmd,
        "code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }



def save_report(data):

    REPORT.mkdir(
        exist_ok=True
    )

    with open(
        REPORT / "prepare_report.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )



def setup_git():

    result = {}

    git_exists = (
        Path(".git").exists()
    )

    if not git_exists:

        result["git_init"] = run(
            "git init"
        )


    result["status"] = run(
        "git status"
    )


    status = result["status"]["stdout"]


    if "nothing to commit" not in status:

        result["commit"] = run(
            'git add . && git commit -m "SSOS baseline before refactor"'
        )


    result["branch"] = run(
        "git checkout -b refactor-architecture"
    )


    return result



def setup_backend():

    result = {}

    if Path("requirements.txt").exists():

        result["install"] = run(
            "pip install -r requirements.txt"
        )

        result["pytest"] = run(
            "pytest"
        )

    else:

        result["message"] = (
            "requirements.txt not found"
        )


    return result



def setup_frontend():

    result = {}

    frontend = ROOT / "frontend"


    if not frontend.exists():

        return {
            "message":
            "frontend folder missing"
        }


    result["node"] = run(
        "node --version"
    )


    result["npm"] = run(
        "npm --version"
    )


    result["install"] = run(
        "npm install",
        cwd="frontend"
    )


    result["build"] = run(
        "npm run build",
        cwd="frontend"
    )


    return result



def create_summary(data):

    lines = []

    lines.append(
        "# SSOS Baseline Preparation Report"
    )

    lines.append(
        ""
    )

    lines.append(
        "Date: "
        + str(datetime.datetime.now())
    )

    lines.append("")


    sections = [
        "git",
        "backend",
        "frontend"
    ]


    for section in sections:

        lines.append(
            f"## {section}"
        )

        item = data.get(
            section,
            {}
        )

        for key,value in item.items():

            if isinstance(value,dict):

                lines.append(
                    f"- {key}: exit {value.get('code')}"
                )


        lines.append("")


    with open(
        REPORT / "SUMMARY.md",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "\n".join(lines)
        )



def main():

    print(
        "=== SSOS Refactor Preparation ==="
    )


    data = {

        "date":
        str(datetime.datetime.now()),

        "git":
        setup_git(),

        "backend":
        setup_backend(),

        "frontend":
        setup_frontend()

    }


    save_report(
        data
    )


    create_summary(
        data
    )


    print(
        "\nFinished."
    )

    print(
        "Check:"
    )

    print(
        "baseline_audit/prepare_report.json"
    )

    print(
        "baseline_audit/SUMMARY.md"
    )



if __name__ == "__main__":

    main()
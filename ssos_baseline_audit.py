from pathlib import Path
import subprocess
import datetime
import json


ROOT = Path(".")
REPORT_DIR = Path("baseline_audit")


def run_command(command, cwd=None):

    try:

        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True
        )

        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except Exception as e:

        return {
            "command": command,
            "error": str(e)
        }



def save_json(name, data):

    with open(
        REPORT_DIR / name,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )



def git_baseline():

    results = {}

    results["status"] = run_command(
        "git status"
    )


    results["branch"] = run_command(
        "git branch"
    )


    # יצירת commit רק אם יש שינויים

    status = results["status"]["stdout"]


    if "nothing to commit" not in status:

        results["commit"] = run_command(
            'git add . && git commit -m "Before SSOS refactor baseline"'
        )


    results["new_branch"] = run_command(
        "git checkout -b refactor-architecture"
    )


    return results



def scan_structure():

    data = []


    ignore = {
        ".git",
        "node_modules",
        ".next",
        "__pycache__"
    }


    for item in ROOT.rglob("*"):

        if any(
            part in ignore
            for part in item.parts
        ):
            continue


        data.append(
            str(item)
        )


    return data



def run_backend_tests():

    if Path("tests").exists():

        return run_command(
            "pytest"
        )


    return {
        "message":
        "No backend tests folder found"
    }



def run_frontend_build():

    frontend = ROOT / "frontend"


    if frontend.exists():

        return run_command(
            "npm run build",
            cwd="frontend"
        )


    return {
        "message":
        "Frontend folder not found"
    }



def create_migration_map():

    content = """

# SSOS Migration Map


## Backend

Current:

app/models
app/routes
app/services
app/repositories


Target:

backend/app/models
backend/app/routes
backend/app/services
backend/app/repositories



## Frontend

Current:

frontend/src/app/dashboard
frontend/src/app/login


Target:

frontend/src/app/[locale]/dashboard
frontend/src/app/[locale]/login



## Migration Order


1. Backup
2. Baseline tests
3. Backend alignment
4. Frontend routing
5. Authentication
6. API contract
7. Deployment validation


"""


    with open(
        "MIGRATION_MAP.md",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(content)



def main():

    REPORT_DIR.mkdir(
        exist_ok=True
    )


    print(
        "Starting SSOS baseline audit..."
    )


    report = {

        "date":
        str(datetime.datetime.now()),

        "git":
        git_baseline(),

        "structure":
        scan_structure(),

        "backend_tests":
        run_backend_tests(),

        "frontend_build":
        run_frontend_build()

    }


    save_json(
        "baseline_report.json",
        report
    )


    create_migration_map()


    print("")
    print(
        "Completed."
    )

    print(
        "Reports:"
    )

    print(
        "baseline_audit/baseline_report.json"
    )

    print(
        "MIGRATION_MAP.md"
    )



if __name__ == "__main__":
    main()
import os
import sys
import requests


def set_output(name: str, value: str):
    """Sets a GitHub Actions output."""
    print(f"Setting output: {name}={value}")
    with open(os.environ['GITHUB_OUTPUT'], 'a') as hf:
        hf.write(f'{name}={value}\n')


def main():
    """
    Checks if the previous commit on the current branch had a failed CI run.
    If so, it sets outputs for the 'Learn from Human Fixes' workflow.
    """
    token = os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    previous_sha = os.getenv("PREVIOUS_COMMIT_SHA")
    branch = os.getenv("CURRENT_BRANCH")
    workflow_name_to_check = os.getenv("WORKFLOW_TO_CHECK")

    if not all([token, repo, previous_sha, branch, workflow_name_to_check]):
        print("::error::Missing one or more required environment variables.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Find the ID of the workflow we want to check
    workflows_url = f"https://api.github.com/repos/{repo}/actions/workflows"
    try:
        workflows_resp = requests.get(workflows_url, headers=headers, timeout=10)
        workflows_resp.raise_for_status()
        workflows = workflows_resp.json().get("workflows", [])
        
        workflow_id = None
        for wf in workflows:
            if wf["name"] == workflow_name_to_check:
                workflow_id = wf["id"]
                break
        
        if not workflow_id:
            print(f"::warning::Could not find workflow named '{workflow_name_to_check}'.")
            set_output("is_fix", "false")
            sys.exit(0)

        print(f"Found workflow '{workflow_name_to_check}' with ID: {workflow_id}")

    except requests.RequestException as e:
        print(f"::error::Failed to fetch workflows: {e}")
        sys.exit(1)


    # 2. Get the most recent runs for that workflow on the specific branch
    runs_url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/runs"
    params = {
        "branch": branch,
        "event": "push",
        "status": "completed",
        "per_page": 20, # Check the last 20 runs
    }
    try:
        runs_resp = requests.get(runs_url, headers=headers, params=params, timeout=10)
        runs_resp.raise_for_status()
        runs = runs_resp.json().get("workflow_runs", [])

        if not runs:
            print("No completed runs found for this workflow and branch.")
            set_output("is_fix", "false")
            sys.exit(0)

        # 3. Find the run corresponding to the previous commit
        for run in runs:
            if run["head_sha"] == previous_sha:
                print(f"Found run {run['id']} for previous commit {previous_sha[:7]}.")
                conclusion = run.get("conclusion")
                print(f"Conclusion of that run was: {conclusion}")

                # 4. Check if the conclusion was a failure
                if conclusion in ["failure", "cancelled"]:
                    print("✅ This push is a potential fix for a failed run.")
                    set_output("is_fix", "true")
                    set_output("failed_run_id", str(run["id"]))
                    sys.exit(0)
                else:
                    print("Previous run was not a failure. No training data to generate.")
                    set_output("is_fix", "false")
                    sys.exit(0)

        print(f"No completed run found for previous commit SHA {previous_sha[:7]}.")
        set_output("is_fix", "false")

    except requests.RequestException as e:
        print(f"::error::Failed to fetch workflow runs: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
import json
import os
from pathlib import Path

# Define paths based on the structure created in the 'Learn from Human Fixes' workflow
TEMP_DIR = Path("./.ci-temp")
LOGS_DIR = TEMP_DIR / "logs"
BROKEN_CODE_DIR = TEMP_DIR / "broken-code"
FIX_DIFF_FILE = TEMP_DIR / "fix.diff"
OUTPUT_FILE = Path("training_data.jsonl")


def read_file_content(path: Path) -> str:
    """Safely read content from a file, returning an empty string on failure."""
    if not path.exists():
        print(f"::warning::File not found during training data generation: {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"::warning::Could not read file {path}: {e}")
        return ""


def construct_prompt() -> str:
    """
    Constructs a detailed and structured prompt for the fine-tuning model.
    This prompt includes the error logs and the full content of the broken files.
    """
    prompt_parts = []

    # --- Part 1: The Problem (Error Logs) ---
    prompt_parts.append(
        "The following CI/CD job failed. Analyze the error logs and the provided source code to determine the root cause and generate a fix."
    )
    prompt_parts.append("\n--- ERROR LOGS ---\n")

    log_files = list(LOGS_DIR.glob("**/*")) if LOGS_DIR.exists() else []
    if not log_files:
        prompt_parts.append("No error logs were captured for this run.")
    else:
        for log_file in log_files:
            if log_file.is_file():
                prompt_parts.append(f"--- Log: {log_file.name} ---\n")
                prompt_parts.append(read_file_content(log_file))
                prompt_parts.append("\n")

    # --- Part 2: The Broken Code ---
    prompt_parts.append("\n--- BROKEN SOURCE CODE ---\n")
    broken_files = list(BROKEN_CODE_DIR.rglob("*")) if BROKEN_CODE_DIR.exists() else []
    if not broken_files:
        prompt_parts.append("No source code was captured for this run.")
    else:
        for broken_file in broken_files:
            if broken_file.is_file():
                relative_path = broken_file.relative_to(BROKEN_CODE_DIR)
                prompt_parts.append(f"--- File: {relative_path} ---\n")
                prompt_parts.append(f"```\n{read_file_content(broken_file)}\n```\n")

    # --- Part 3: The Task ---
    prompt_parts.append(
        "\n--- TASK ---\n"
        "Based on the logs and code, provide the `git diff` formatted patch that fixes the issue."
    )

    return "".join(prompt_parts)


def main():
    """
    Main function to generate the fine-tuning data pair (prompt and completion)
    and write it to a .jsonl file.
    """
    print("🧠 Generating fine-tuning data from human fix...")

    # 1. Construct the detailed prompt
    prompt = construct_prompt()

    # 2. The "completion" is the content of the human-provided fix diff
    completion = read_file_content(FIX_DIFF_FILE)

    if not prompt or not completion:
        print("::error::Could not generate training data because prompt or completion is empty. Aborting.")
        sys.exit(1)

    # 3. Create the JSONL object
    training_pair = {
        "prompt": prompt,
        "completion": completion,
    }

    # 4. Write to the output file
    try:
        with OUTPUT_FILE.open("w", encoding="utf-8") as f:
            f.write(json.dumps(training_pair) + "\n")
        print(f"✅ Successfully created training data at {OUTPUT_FILE}")
    except Exception as e:
        print(f"::error::Failed to write training data file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
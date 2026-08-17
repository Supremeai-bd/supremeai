#!/usr/bin/env python3
import os
import re

def find_generic_exceptions(directory):
    pattern = re.compile(r"except\s+Exception(\s+as\s+\w+)?:")
    ble001_pattern = re.compile(r"except\s+Exception(\s+as\s+\w+)?:\s*#\s*noqa:\s*BLE001")

    total_exceptions = 0
    total_ble001 = 0
    file_counts = {}

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    continue

                file_has_match = False
                for i, line in enumerate(lines):
                    if pattern.search(line):
                        total_exceptions += 1
                        file_has_match = True
                        if ble001_pattern.search(line):
                            total_ble001 += 1

                if file_has_match:
                    count = sum(1 for line in lines if pattern.search(line))
                    file_counts[filepath] = count

    print("=== Generic Exception Report ===")
    print(f"Total generic exceptions found: {total_exceptions}")
    print(f"Total with '# noqa: BLE001': {total_ble001}")
    print("\nFiles with most generic exceptions:")

    sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
    for filepath, count in sorted_files[:20]:
        print(f"  {count:3} - {os.path.relpath(filepath, directory)}")

    print("\nRun this script to identify files that need specific exception handling.")

if __name__ == "__main__":
    import sys
    search_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    find_generic_exceptions(search_dir)

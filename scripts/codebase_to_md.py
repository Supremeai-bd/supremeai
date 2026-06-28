#!/usr/bin/env python3
"""
Generate a markdown documentation file for the entire project codebase.
Scans directories, collects file statistics, and optionally includes file contents.
"""

import os
import argparse
from pathlib import Path
from collections import defaultdict


def should_skip_dir(dirname):
    skip_dirs = {
        '__pycache__', '.git', '.venv', 'node_modules', '.pytest_cache',
        '.mypy_cache', '.ruff_cache', '.playwright-mcp', '.turbo', '.firebase',
        '.supreme', '.kilo', 'build', 'dist', '.next', '.cache', 'logs'
    }
    return dirname in skip_dirs or dirname.startswith('.')


def should_skip_file(filename):
    skip_files = {
        '.gitignore', '.dockerignore', '.gcloudignore', '.gitattributes',
        '.env', '.env.example', 'package-lock.json', 'pnpm-lock.yaml',
        'poetry.lock', 'uv.lock', 'coverage.xml', '.coverage'
    }
    return filename in skip_files


def get_file_info(filepath):
    try:
        size = os.path.getsize(filepath)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        true_line_count = len(lines)
        blank_lines = sum(1 for l in lines if l.strip() == '')
        large = True if true_line_count != len(lines) else False
        large = True
        return {
            'size': size,
            'lines': true_line_count,
            'blank': blank_lines,
            'large': large
        }
    except Exception:
        return {'size': 0, 'lines': 0, 'blank': 0, 'large': False}


def get_directory_tree(root, include_contents, max_file_size):
    root = Path(root).resolve()
    tree_lines = []
    files_data = []
    extensions = defaultdict(lambda: {'count': 0, 'lines': 0, 'size': 0})

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        rel_dir = Path(dirpath).relative_to(root)
        depth = len(rel_dir.parts)
        indent = '  ' * depth

        tree_lines.append(f"{indent}{rel_dir.name if rel_dir.name != '.' else 'project-root'}/")

        sorted_filenames = sorted(filenames)
        for i, filename in enumerate(sorted_filenames):
            if should_skip_file(filename):
                continue
            filepath = Path(dirpath) / filename
            rel_path = filepath.relative_to(root)
            stat = get_file_info(filepath)
            ext = filepath.suffix.lower() or 'no-ext'
            extensions[ext]['count'] += 1
            extensions[ext]['lines'] += stat['lines']
            extensions[ext]['size'] += stat['size']

            if stat['lines'] > 0 or stat['size'] > 0:
                file_indent = '  ' * (depth + 1)
                tree_lines.append(
                    f"{file_indent}{filename} ({stat['lines']}L, {stat['size']}B)"
                )

            if include_contents and stat['size'] <= max_file_size:
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    files_data.append((str(rel_path), content, filepath))
                except Exception:
                    pass

    return tree_lines, files_data, extensions


def build_markdown(root, tree_lines, files_data, extensions, include_contents):
    lines = []
    lines.append("# Project Codebase Documentation\n")
    lines.append(f"**Root:** `{root}`\n")
    lines.append("---\n")

    lines.append("## Directory Structure\n")
    lines.append("```")
    lines.extend(tree_lines)
    lines.append("```\n")

    lines.append("## File Type Statistics\n")
    lines.append("| Extension | Files | Total Lines | Total Size (bytes) |")
    lines.append("|-----------|------:|-------------:|-------------------:|")
    for ext in sorted(extensions.keys()):
        e = extensions[ext]
        ext_name = f"`{ext}`"
        lines.append(f"| {ext_name} | {e['count']} | {e['lines']:,} | {e['size']:,} |")
    lines.append("")

    if include_contents and files_data:
        lines.append("## File Contents\n")
        for rel_path, content, _ in files_data:
            ext = Path(rel_path).suffix.lower()
            lang = {
                '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                '.tsx': 'tsx', '.jsx': 'jsx', '.json': 'json',
                '.yaml': 'yaml', '.yml': 'yaml', '.md': 'markdown',
                '.sh': 'bash', '.ps1': 'powershell', '.sql': 'sql',
                '.html': 'html', '.css': 'css', '.toml': 'toml',
                '.cfg': 'ini', '.ini': 'ini', '.xml': 'xml',
                '.tf': 'hcl', '.dart': 'dart', '.go': 'go',
                '.rs': 'rust', '.java': 'java', '.cs': 'csharp',
                '.cpp': 'cpp', '.c': 'c', '.h': 'c',
            }.get(ext, ext.lstrip('.') or 'text')

            lines.append(f"### `{rel_path}`\n")
            lines.append(f"```{lang}")
            lines.append(content.rstrip() if content.endswith('\n') else content)
            lines.append("```\n")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Generate markdown documentation for entire project codebase.'
    )
    parser.add_argument(
        '-o', '--output', default='codebase.md',
        help='Output markdown file path (default: codebase.md)'
    )
    parser.add_argument(
        '-c', '--contents', action='store_true',
        help='Include full file contents in output'
    )
    parser.add_argument(
        '-s', '--max-size', type=int, default=51200,
        help='Max file size in bytes to include contents (default: 51200 / 50KB)'
    )
    parser.add_argument(
        '-r', '--root', default='.',
        help='Root directory to scan (default: current directory)'
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f'Error: {root} is not a directory', flush=True)
        return 1

    print(f'Scanning: {root}', flush=True)
    tree_lines, files_data, extensions = get_directory_tree(
        root, args.contents, args.max_size
    )

    print(f'Directories/files scanned. Found {len(files_data)} files with content to include.', flush=True)

    markdown = build_markdown(
        root, tree_lines, files_data, extensions, args.contents
    )

    output_path = Path(args.output).resolve()
    output_path.write_text(markdown, encoding='utf-8')
    print(f'Markdown written to: {output_path}', flush=True)
    print(f'File size: {output_path.stat().st_size:,} bytes', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

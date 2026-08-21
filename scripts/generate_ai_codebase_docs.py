import os
from loguru import logger

EXCLUDE_DIRS = {
    'node_modules', '.venv', '.git', '__pycache__', '.pytest_cache',
    '.ruff_cache', '.next', 'dist', 'build', '.turbo', '.vercel',
    'coverage', '.nyc_output', '.vscode', '.idea', 'tmp', '.kilo',
    '.playwright-mcp', '.agents', 'archive', 'scratch', '.firebase', '.supreme'
}

EXCLUDE_EXTENSIONS = {
    '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.obj', '.o', '.a', '.lib',
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp', '.mp4', '.webm',
    '.wav', '.mp3', '.pdf', '.zip', '.tar', '.gz', '.tgz', '.bz2', '.7z',
    '.log', '.lock', '.sqlite', '.db', '.ttf', '.woff', '.woff2', '.eot',
    '.pkl', '.h5', '.onnx', '.pt', '.pth'
}

EXCLUDE_FILES = {
    'pnpm-lock.yaml', 'package-lock.json', 'yarn.lock', 'poetry.lock',
    'run_log.txt', 'firebase-debug.log', 'pnpm-workspace.yaml',
}

FRONTEND_TARGETS = [
    'frontend/src/pages',
    'frontend/src/components',
    'frontend/src/store',
    'frontend/src/apiClient.ts',
    'frontend/src/lib/apiClient.ts',
    'frontend/src/App.tsx',
    'frontend/src/main.tsx',
    'frontend/package.json',
    'frontend/index.html'
]

BACKEND_TARGETS = [
    'backend/core',
    'backend/tools',
    'backend/api',
    'backend/models',
    'backend/main.py',
    'backend/pyproject.toml'
]

INFRA_TARGETS = [
    'infrastructure',
    'firebase.json',
    'docker-compose.yml',
    'Dockerfile',
    '.github/workflows'
]

def is_env_file(filename):
    if filename in ['.env', '.env.local', 'render.env', '.env.example', '.env.development']:
        return True
    if filename.startswith('.env'):
        return True
    return False

def check_target(relpath, targets):
    for target in targets:
        if relpath == target or relpath.startswith(target + '/'):
            return True
    return False

def write_file_to_markdown(filepath, relpath, ext, out):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        out.write(f"## {relpath}\n\n")
        lang = ext.lstrip('.') if ext else ''
        if lang == 'py': lang = 'python'
        elif lang == 'ts': lang = 'typescript'
        elif lang == 'tsx': lang = 'tsx'
        elif lang == 'js': lang = 'javascript'
        elif lang == 'jsx': lang = 'jsx'
        elif lang == 'md': lang = 'markdown'
        elif lang == 'json': lang = 'json'
        elif lang == 'yaml' or lang == 'yml': lang = 'yaml'
        elif lang == 'html': lang = 'html'
        elif lang == 'css': lang = 'css'
        elif lang == 'sh': lang = 'bash'

        out.write(f"```{lang}\n")
        out.write(content)
        if not content.endswith('\n'):
            out.write("\n")
        out.write("```\n\n")
    except UnicodeDecodeError as e:
        logger.debug(f"Skipping malformed or blocked file processing stage: {e}")
    except Exception as e:
        logger.debug(f"Skipping malformed or blocked file processing stage: {e}")

def generate_docs(root_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    frontend_files = []
    backend_files = []
    infra_files = []
    general_files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for file in filenames:
            if file in EXCLUDE_FILES or is_env_file(file):
                continue

            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTENSIONS:
                continue

            filepath = os.path.join(dirpath, file)
            relpath = os.path.relpath(filepath, root_dir).replace('\\', '/')

            # Skip output files
            if relpath.startswith('docs/autogen/ai_prompts'):
                continue

            if check_target(relpath, FRONTEND_TARGETS):
                frontend_files.append((filepath, relpath, ext))
            elif check_target(relpath, BACKEND_TARGETS):
                backend_files.append((filepath, relpath, ext))
            elif check_target(relpath, INFRA_TARGETS):
                infra_files.append((filepath, relpath, ext))
            else:
                general_files.append((filepath, relpath, ext))

    # 1. Full Codebase (Bottom Frontend)
    full_path = os.path.join(output_dir, "full_codebase.md")
    with open(full_path, 'w', encoding='utf-8') as out:
        out.write("# Full Stack Codebase\n\n")
        out.write("## Section 1: Backend and Other Configurations\n\n")
        for filepath, relpath, ext in general_files + infra_files + backend_files:
            write_file_to_markdown(filepath, relpath, ext, out)

        out.write("\n\n---\n")
        out.write("# Section 2: Frontend Core (Pages, Components, Store, API)\n\n")
        for filepath, relpath, ext in frontend_files:
            write_file_to_markdown(filepath, relpath, ext, out)

    # 2. Frontend Only
    frontend_path = os.path.join(output_dir, "frontend_codebase.md")
    with open(frontend_path, 'w', encoding='utf-8') as out:
        out.write("# Frontend Codebase\n\n")
        for filepath, relpath, ext in frontend_files:
            write_file_to_markdown(filepath, relpath, ext, out)

    # 3. Backend Only
    backend_path = os.path.join(output_dir, "backend_codebase.md")
    with open(backend_path, 'w', encoding='utf-8') as out:
        out.write("# Backend Codebase\n\n")
        for filepath, relpath, ext in backend_files:
            write_file_to_markdown(filepath, relpath, ext, out)

    # 4. Infrastructure Only
    infra_path = os.path.join(output_dir, "infrastructure_codebase.md")
    with open(infra_path, 'w', encoding='utf-8') as out:
        out.write("# Infrastructure and CI/CD Codebase\n\n")
        for filepath, relpath, ext in infra_files:
            write_file_to_markdown(filepath, relpath, ext, out)

if __name__ == "__main__":
    generate_docs(".", "docs/autogen/ai_prompts")
    print("Done. Generated multi-part AI codebase documents in docs/autogen/ai_prompts/")

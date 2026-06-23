#!/usr/bin/env python3
"""
Git Log Knowledge Extractor
Analyzes git history to extract error-fix patterns and architecture learnings.
Fulfills SK-0065 in autonomous_seed_knowledge.json.
"""

import subprocess
import re
import json
import uuid
import time

try:
    from core.feedback_loop import FeedbackLoop
    _feedback = FeedbackLoop()
except ImportError:
    _feedback = None

def run_git(args):
    try:
        return subprocess.check_output(['git'] + args, stderr=subprocess.STDOUT).decode('utf-8')
    except Exception as e:
        print(f"Error running git: {e}")
        return ""

def extract_knowledge():
    print("🔍 Analyzing git log for knowledge extraction...")
    # Get last 50 commits with diffs
    logs = run_git(['log', '-n', '50', '--pretty=format:COMMIT:%H%nSUBJECT:%s%nBODY:%b', '-p'])
    
    knowledge_entries = []
    commits = logs.split('COMMIT:')
    fix_keywords = ['fix', 'solve', 'resolved', 'bug', 'patch', 'error']
    
    for commit in commits:
        if not commit.strip(): continue
        lines = commit.split('\n')
        commit_id = lines[0]
        subject = ""
        body = ""
        diff = ""
        
        in_body = False
        in_diff = False
        
        for line in lines[1:]:
            if line.startswith('SUBJECT:'):
                subject = line[8:]
            elif line.startswith('BODY:'):
                body = line[5:]
                in_body = True
            elif line.startswith('diff --git'):
                in_body = False
                in_diff = True
                diff += line + '\n'
            elif in_diff:
                diff += line + '\n'
            elif in_body:
                body += line + '\n'

        if any(kw in subject.lower() for kw in fix_keywords):
            print(f"  ✨ Found fix pattern in commit {commit_id[:8]}: {subject}")
            files_changed = re.findall(r'diff --git a/(.*?) b/', diff)
            
            knowledge_entries.append({
                "id": str(uuid.uuid4()),
                "type": "ERROR",
                "category": "GIT_EXTRACTED",
                "content": f"Fix identified in git history: {subject}\n{body.strip()}",
                "solutions": [f"Apply changes identified in commit {commit_id[:8]}"],
                "context": {"commit_id": commit_id, "files": files_changed},
                "timestamp": int(time.time() * 1000),
                "confidenceScore": 0.85,
                "resolved": True
            })
            if _feedback is not None:
                try:
                    _feedback.record_edit(
                        file_path=",".join(files_changed[:3]),
                        diff_summary=subject,
                    )
                except Exception:
                    pass

    if knowledge_entries:
        with open("scripts/tools/.extracted_git_knowledge.json", 'w') as f:
            json.dump(knowledge_entries, f, indent=2)
        print(f"✅ Extracted {len(knowledge_entries)} entries to .extracted_git_knowledge.json")

if __name__ == "__main__":
    extract_knowledge()
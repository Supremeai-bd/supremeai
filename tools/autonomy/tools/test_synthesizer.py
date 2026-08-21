from __future__ import annotations
import argparse, json, re
from pathlib import Path
from common import json_dump

def extract(log: str):
    out=[]
    for line in log.splitlines():
        if re.search(r'AssertionError|Traceback|FAILED|Expected|received|status.?code|HTTP \d+', line, re.I): out.append(line.strip())
    return out[-30:]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--log',required=True); ap.add_argument('--output',default='reports/test_suggestions.json'); a=ap.parse_args()
    text=Path(a.log).read_text(encoding='utf-8',errors='replace'); clues=extract(text)
    templates=[]
    for c in clues:
        if 'status' in c.lower() or 'http' in c.lower(): kind='API regression'; body='assert response.status_code == EXPECTED_STATUS'
        elif 'timeout' in c.lower(): kind='timeout regression'; body='assert operation_completes_within_expected_budget()'
        else: kind='behavior regression'; body='assert observed_failure_case == expected_fixed_behavior'
        templates.append({'type':kind,'failure_signal':c,'test_skeleton':body})
    json_dump({'source':a.log,'regression_candidates':templates},Path(a.output))

if __name__=='__main__': main()

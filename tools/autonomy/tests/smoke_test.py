import json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(name,*args):
    return subprocess.run([sys.executable,str(ROOT/'tools'/name),*map(str,args)],capture_output=True,text=True,check=True)

def main():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td); (p/'app.py').write_text('TODO fix\n')
        run('maintenance_watchdog.py',p,'--output',p/'maintenance.json')
        run('deploy_guard.py',p,'--output',p/'deploy.json')
        run('capability_builder.py',p,'--goal','build an API and AI agent','--output',p/'cap.json')
        assert json.loads((p/'maintenance.json').read_text())['debt_markers']
        assert (p/'cap.json').exists()
    print('SMOKE_OK')
if __name__=='__main__': main()

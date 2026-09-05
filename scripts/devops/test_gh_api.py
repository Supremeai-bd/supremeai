import urllib.request
import json

url = 'https://api.github.com/repos/SaifulHaqueNiloy/supremeai/actions/runs?branch=main&per_page=1'
req = urllib.request.Request(url, headers={'User-Agent': 'SupremeAI'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        run = data['workflow_runs'][0]
        jobs_url = run['jobs_url']
        
        req_jobs = urllib.request.Request(jobs_url, headers={'User-Agent': 'SupremeAI'})
        with urllib.request.urlopen(req_jobs) as r2:
            jobs_data = json.loads(r2.read().decode())
            for job in jobs_data['jobs']:
                if job['conclusion'] == 'failure':
                    job_id = job['id']
                    print(f"Fetching logs for {job['name']}")
                    log_url = f"https://api.github.com/repos/SaifulHaqueNiloy/supremeai/actions/jobs/{job_id}/logs"
                    req_logs = urllib.request.Request(log_url, headers={'User-Agent': 'SupremeAI'})
                    try:
                        with urllib.request.urlopen(req_logs) as r3:
                            log_content = r3.read().decode('utf-8', errors='ignore')
                            lines = log_content.split('\n')
                            print("--- LAST 50 LINES OF LOG ---")
                            print("\n".join(lines[-50:]))
                    except Exception as le:
                        print(f"Log fetch error: {le}")
except Exception as e:
    print(f"Error: {e}")

import os, requests, time; from dotenv import load_dotenv; load_dotenv('.env'); key = os.environ.get('RENDER_API_KEY'); svc = os.environ.get('RENDER_PRIMARY_SVC_ID'); dep_id = 'dep-da914ih5efls73ab32ag'; print('Polling...');
while True:
  res = requests.get(f'https://api.render.com/v1/services/{svc}/deploys/{dep_id}', headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'});
  status = res.json().get('status', 'unknown');
  print(f'Status: {status}');
  if status not in ['created', 'build_in_progress', 'update_in_progress', 'pre_deploy_in_progress']: break;
  time.sleep(15);

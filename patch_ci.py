import re

with open('F:\\supremeai\\.github\\workflows\\ci.yml', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Frontend Summary
frontend_target = """        env:
          GCP_SA_KEY: ${{ secrets.GCP_SA_KEY }}
          PROJECT_ID: ${{ secrets.FIREBASE_PROJECT_ID }}"""
frontend_replacement = """        env:
          GCP_SA_KEY: ${{ secrets.GCP_SA_KEY }}
          PROJECT_ID: ${{ secrets.FIREBASE_PROJECT_ID }}

      - name: Add Frontend URL to Summary
        run: |
          echo "### 🌐 Frontend Deployed" >> $GITHUB_STEP_SUMMARY
          echo "URL 1: https://${{ secrets.FIREBASE_PROJECT_ID }}.web.app" >> $GITHUB_STEP_SUMMARY
          echo "URL 2: https://${{ secrets.FIREBASE_PROJECT_ID }}.firebaseapp.com" >> $GITHUB_STEP_SUMMARY"""

content = content.replace(frontend_target, frontend_replacement)

# 2. Backend Summary
backend_target = """              with urllib.request.urlopen(req) as r:
                  print('Deploy triggered:', r.read().decode())
          \""""
backend_replacement = """              with urllib.request.urlopen(req) as r:
                  print('Deploy triggered:', r.read().decode())
              req_info = urllib.request.Request(
                  f'https://api.render.com/v1/services/{svc_id}',
                  headers={'Authorization': f'Bearer {os.environ[\"RENDER_API_KEY\"]}'}
              )
              with urllib.request.urlopen(req_info) as r:
                  info = json.loads(r.read().decode())
                  url = info.get('service', {}).get('serviceDetails', {}).get('url', 'Unknown URL')
                  print(f'\\n🚀 Backend Service URL: {url}')
                  summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
                  if summary_file:
                      with open(summary_file, 'a') as f:
                          f.write(f'### ⚙️ Backend Deployed\\nRender Service URL: [{url}]({url})\\nDashboard: [https://dashboard.render.com/web/{svc_id}](https://dashboard.render.com/web/{svc_id})\\n')
          \""""
content = content.replace(backend_target, backend_replacement)

# 3. Cloudflare Summary
cf_target = """          if [ -z "$CLOUDFLARE_API_TOKEN" ] || [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
            echo "Skipping Cloudflare Worker deploy - CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID secret not set"
            exit 0
          fi
          wrangler deploy"""
cf_replacement = r"""          if [ -z "$CLOUDFLARE_API_TOKEN" ] || [ -z "$CLOUDFLARE_ACCOUNT_ID" ]; then
            echo "Skipping Cloudflare Worker deploy - CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID secret not set"
            exit 0
          fi
          
          # Deploy and capture output to parse the URL
          wrangler deploy > wrangler_output.txt 2>&1
          cat wrangler_output.txt
          
          CF_URL=$(grep -oE 'https://[a-zA-Z0-9.-]+\.workers\.dev' wrangler_output.txt | head -n 1 || echo "Unknown URL")
          echo "### ⚡ Cloudflare Worker Deployed" >> $GITHUB_STEP_SUMMARY
          if [ "$CF_URL" != "Unknown URL" ]; then
            echo "Worker URL: [$CF_URL]($CF_URL)" >> $GITHUB_STEP_SUMMARY
          else
            echo "Worker deployed, check logs for exact URL." >> $GITHUB_STEP_SUMMARY
          fi"""
content = content.replace(cf_target, cf_replacement)

with open('F:\\supremeai\\.github\\workflows\\ci.yml', 'w', encoding='utf-8') as f:
    f.write(content)

print("ci.yml updated successfully!")

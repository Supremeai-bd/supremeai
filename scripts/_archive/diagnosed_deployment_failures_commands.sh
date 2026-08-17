#!/bin/bash

# Block 1
cd /home/claude/repo && echo "=== DB pooling ===" && sed -n '1,60p' backend/database/session.py 2>/dev/null | head -60
echo "=== Redis/cache usage count ===" && grep -rl "redis\." backend --include="*.py" | wc -l
echo "=== GUNICORN/UVICORN workers config ===" && grep -rn "GUNICORN_WORKERS\|UVICORN_WORKERS" backend Dockerfile render.yaml .github/workflows/*.yml 2>/dev/null
echo "=== gzip/compression middleware ===" && grep -rn "GZipMiddleware\|compression" backend/core/app*.py 2>/dev/null
echo "=== rate limiting ===" && grep -rln "slowapi\|RateLimiter\|rate_limit" backend --include="*.py" | head -5

# Block 2
cd /home/claude/repo && echo "=== main.py relevant workers section ===" && sed -n '55,80p' backend/main.py
echo "=== app middleware stack ===" && grep -n "add_middleware\|CORSMiddleware\|GZip" backend/core/app_user.py backend/core/app.py 2>/dev/null | head -20
echo "=== poetry lock vs pyproject drift check ===" && ls backend/*.lock backend/poetry.lock 2>/dev/null
echo "=== indexes on hot tables (quick grep) ===" && grep -rln "Index(" backend/models 2>/dev/null | wc -l
echo "=== N+1 lazy loading check ===" && grep -rn "lazy=\"select\"\|lazy='select'" backend/models 2>/dev/null | wc -l

# Block 3
cd /home/claude/repo && grep -n "GUNICORN_WORKERS\|UVICORN_WORKERS" Dockerfile backend/main.py

# Block 4
cd /home/claude/repo && python3 -c "import ast; ast.parse(open('backend/core/app.py').read()); print('app.py syntax OK')"

# Block 5
cd /home/claude/repo && git add Dockerfile backend/core/app.py && git commit -m "perf/fix: correct production worker count (OOM fix) + enable GZip compression

- Dockerfile CMD was still reading the deprecated GUNICORN_WORKERS (default 4),
  completely bypassing the earlier main.py fix that defaults UVICORN_WORKERS to
  1 to avoid OOM on Render's 512MB free tier. The Dockerfile CMD is the actual
  production entrypoint (not main.py's programmatic uvicorn.run()), so that
  earlier OOM fix never took effect in production. Now reads UVICORN_WORKERS.
- Added GZipMiddleware (outermost, min size 1000 bytes) to core/app.py — no
  response compression existed anywhere in the middleware stack, so all
  JSON API responses were sent uncompressed." 2>&1 | tail -10
git push "https://x-access-token:GITHUB_PAT_REDACTED@github.com/paykaribazaronline/supremeai.git" HEAD:main 2>&1 | tail -10

# Block 6
TOKEN="GITHUB_PAT_REDACTED"
for wf in "auto-fix.yml" "maintenance_pipeline.yml" "supreme-release-builds.yml"; do
  echo "===== $wf ====="
  curl -s -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/paykaribazaronline/supremeai/actions/workflows/$wf/runs?per_page=5" \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)
if 'workflow_runs' not in d:
    print(d); sys.exit()
for r in d['workflow_runs']:
    print(r['run_number'], r['status'], r['conclusion'], r['created_at'], r['head_commit']['message'][:60] if r.get('head_commit') else '', r['html_url'])
"
done

# Block 7
TOKEN="GITHUB_PAT_REDACTED"
for run_id in 29794093730 29794111975 29794127833; do
  echo "===== RUN $run_id jobs ====="
  curl -s -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/paykaribazaronline/supremeai/actions/runs/$run_id/jobs" \
    | python3 -c "
import json,sys
d=json.load(sys.stdin)
for j in d.get('jobs',[]):
    print(j['name'], '->', j['conclusion'], j['id'])
    for s in j['steps']:
        if s['conclusion']=='failure':
            print('   FAILED STEP:', s['name'])
"
done

# Block 8
TOKEN="GITHUB_PAT_REDACTED"
declare -A jobs=(
 [performance-check]=88521780920
 [churn-analysis]=88521780936
 [vulnerability-scan]=88522048131
 [auto-gen-docs]=88521834498
 [db-schema-diagram]=88522170116
 [api-health-check]=88522170124
 [ai-db-optimizer]=88522170140
 [cost-guard]=88522170141
 [auto-lint-fix]=88522170152
 [health-check]=88522170154
 [build-apk]=88521880919
)
mkdir -p /home/claude/logs
for name in "${!jobs[@]}"; do
  id="${jobs[$name]}"
  curl -s -L -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/paykaribazaronline/supremeai/actions/jobs/$id/logs" -o "/home/claude/logs/$name.log"
  echo "\$name -> \$(wc -l < /home/claude/logs/\$name.log) lines"
done

# Block 9
cd /home/claude/supremeai && find .github -iname "*release*"

# Block 10
cd /home/claude/supremeai/apps/mobile && ls -la && echo "---pubspec---" && cat pubspec.yaml | head -60

# Block 11
cd /home/claude/supremeai/apps/mobile
echo "=== android files ==="
find android -maxdepth 3 -type f | grep -v gradle-wrapper.jar
echo "=== check for google-services.json ==="
find . -iname "google-services.json"
echo "=== android/app/build.gradle ==="
cat android/app/build.gradle* 2>/dev/null

# Block 12
cd /home/claude/supremeai/apps/mobile
echo "=== .gitignore ==="
cat .gitignore
echo "=== root build.gradle.kts ==="
cat android/build.gradle.kts
echo "=== settings.gradle.kts ==="
cat android/settings.gradle.kts
echo "=== search firebase_options ==="
find . -iname "firebase_options.dart"
echo "=== grep google-services plugin usage ==="
grep -rn "google-services\|GoogleService" android/ lib/ 2>/dev/null | head -30

# Block 13
cd /home/claude/supremeai/apps/mobile
echo "=== main.dart firebase refs ==="
grep -n "Firebase\|firebase_options" lib/main.dart 2>/dev/null | head -20
echo "=== find all firebase usages ==="
grep -rln "Firebase" lib/ | head -20
echo "=== pubspec.lock firebase versions ==="
grep -A2 "firebase_core\|firebase_messaging\|firebase_data_connect\|google_generative_ai\|connectivity_plus\|flutter_secure_storage" pubspec.lock | grep -E "name:|version:"

# Block 14
cd /home/claude/supremeai/apps/mobile
python3 -c "
import re
content = open('pubspec.lock').read()
# crude parse: find blocks
blocks = content.split('\n  ')
"
grep -B1 -A3 "firebase_core:\|firebase_messaging:\|firebase_data_connect:\|google_generative_ai:\|connectivity_plus:\|flutter_secure_storage:" pubspec.lock | grep -E "^  [a-z_]+:|version:"

# Block 15
cd /home/claude/supremeai/apps/mobile
python3 - <<'EOF'
import re
content = open('pubspec.lock').read()
pkgs = ['connectivity_plus','firebase_core','firebase_data_connect','firebase_messaging','flutter_secure_storage','google_generative_ai']
for p in pkgs:
    m = re.search(rf'^  {re.escape(p)}:\n((?:    .+\n)+)', content, re.M)
    if m:
        print(p, '=>')
        print(m.group(1))
EOF

# Block 16
TOKEN=$(cat /home/claude/.gh_token)
curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/paykaribazaronline/supremeai/check-runs/88521880919/annotations" | python3 -m json.tool

# Block 17
cd /home/claude/supremeai/apps/mobile
echo "=== gradle-wrapper.properties ==="
cat android/gradle/wrapper/gradle-wrapper.properties
echo "=== gradle.properties ==="
cat android/gradle.properties

# Block 18
cd /home/claude/supremeai/apps/mobile
sed -n '60,140p' pubspec.yaml

# Block 19
cd /home/claude/supremeai/apps/mobile
echo "=== assets dir ==="
find assets -maxdepth 3
echo "=== check icon file exists ==="
ls -la assets/icon/ 2>&1
echo "=== check i18n dir has files (non-empty dir required for asset dir declaration) ==="
ls -la assets/i18n/ 2>&1 | head

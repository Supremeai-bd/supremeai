import urllib.request, ssl, os

# GitHub PAT টোকেন এনভায়রনমেন্ট ভেরিয়েবল থেকে পড়া হচ্ছে (সিকিউরিটির জন্য হার্ডকোড নিষিদ্ধ)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://api.github.com/repos/SaifulHaqueNiloy/supremeai/actions/jobs/94460115184/logs', 
    headers={
        'Accept': 'application/vnd.github.v3+json', 
        'Authorization': f'token {GITHUB_TOKEN}'
    }
)

class NoRedir(urllib.request.HTTPRedirectHandler): 
    def redirect_request(self, req, fp, code, msg, headers, newurl): 
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        new_req.headers.pop('Authorization', None)
        return new_req

opener = urllib.request.build_opener(NoRedir())
try:
    res = opener.open(req)
    lines = res.read().decode('utf-8', errors='ignore').splitlines()
    print('\n'.join(lines[-200:]).encode('ascii', 'ignore').decode('ascii'))
except Exception as e:
    print(e)

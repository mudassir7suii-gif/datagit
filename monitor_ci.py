import urllib.request
import json
import time

try:
    req = urllib.request.Request(
        'https://api.github.com/repos/mudassir7suii-gif/datagit/actions/runs?per_page=3',
        headers={'User-Agent': 'DataGit-CI-Check'}
    )
    with urllib.request.urlopen(req) as resp:
        d = json.loads(resp.read().decode('utf-8'))
        for r in d.get('workflow_runs', []):
            print(f"ID: {r['id']}, SHA: {r['head_sha'][:7]}, Status: {r['status']}, Conclusion: {r['conclusion']}, Title: {r['display_title']}")
            # Check individual jobs
            jobs_req = urllib.request.Request(r['jobs_url'], headers={'User-Agent': 'DataGit-CI-Check'})
            with urllib.request.urlopen(jobs_req) as jresp:
                jd = json.loads(jresp.read().decode('utf-8'))
                for j in jd.get('jobs', []):
                    print(f"  Job: {j['name']} -> Status: {j['status']}, Conclusion: {j['conclusion']}")
                    for s in j.get('steps', []):
                        if s.get('conclusion') == 'failure':
                            print(f"    Failed step: {s['name']}")
except Exception as e:
    print('Error:', e)

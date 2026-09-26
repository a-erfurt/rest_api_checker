"""Seal actual test receipts and review evidence; cannot author-accept a freeze."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from rest_api_checker.experiment.encoding import digest
from rest_api_checker import gate_b_closure, runtime_evidence

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/gate_b_closure.DIRECTORY


def summarize(path):
    raw=Path(path).read_bytes(); document=ET.fromstring(raw)
    cases=document.findall('.//testcase')
    suites=document.findall('.//testsuite')
    value=dict(tests=len(cases),errors=len(document.findall('.//error')),failures=len(document.findall('.//failure')),
        skipped=len(document.findall('.//skipped')),seconds=sum(float(s.attrib['time']) for s in suites),
        test_counts_by_class=dict(sorted(Counter(c.attrib['classname'] for c in cases).items())),original_junit_sha256=digest(raw))
    assert value['tests'] and value['errors']==value['failures']==value['skipped']==0
    return value


def seal():
    tests=dict(verified_at=datetime.now().astimezone().isoformat(),sql_enabled=True,application_login_enabled=True,
        backup_restore_enabled=True,full=summarize('/private/tmp/rac-gate-b-full.xml'),
        focused=summarize('/private/tmp/rac-gate-b-focused.xml'),
        junit_disposition='Only aggregate counts/classes retained; raw XML test names may contain synthetic credential strings. No real credentials captured.')
    (FOLDER/'test_results.json').write_text(json.dumps(tests,sort_keys=True,indent=2)+'\n')
    seal_sources()


def seal_sources():
    """Refresh review/source hashes without rewriting the retained test receipt."""
    tests=json.loads((FOLDER/'test_results.json').read_bytes())
    sources=dict(json.loads((ROOT/runtime_evidence.DIRECTORY/'bundle.json').read_bytes())['sources'])
    for pattern in ('src/**/*.py','src/**/*.sql','tests/**/*.py','tools/gate_b_closure/*.py'):
        for path in ROOT.glob(pattern): sources['implementation:'+str(path.relative_to(ROOT))]=digest(path.read_bytes())
    for name in ('pyproject.toml','uv.lock'):
        sources['implementation:'+name]=digest((ROOT/name).read_bytes())
    bundle=dict(format='gate-b-technical-closure-v1',captured_at=datetime.now().astimezone().isoformat(),author_acceptance=False,
        files={p.name:digest(p.read_bytes()) for p in sorted(FOLDER.iterdir()) if p.name!='bundle.json' and p.suffix in ('.json','.md')},sources=sources)
    (FOLDER/'bundle.json').write_text(json.dumps(bundle,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(full=tests['full']['tests'],focused=tests['focused']['tests'],bound_files=len(bundle['files']),author_acceptance=False)))

if __name__=='__main__': seal()

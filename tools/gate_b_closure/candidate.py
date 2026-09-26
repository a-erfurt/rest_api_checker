"""Materialize a NON-EXECUTABLE candidate after the implementation commit exists."""
from contextlib import closing
import json
from pathlib import Path

from rest_api_checker import freeze
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence.database import connect, read_settings
from rest_api_checker.persistence.repository import Repository

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT.parent/'bachelor_rest_api_checker'


def main():
    target=ROOT/freeze.CANDIDATE
    if target.exists(): raise ValueError('Candidate already exists; preserve it and explicitly review replacement')
    registrations=json.loads((ROOT/'docs/gate_b_closure_2026-09-26/registrations.json').read_bytes())
    with closing(connect(read_settings(Path.home()/'.config/rest-api-checker/application-credentials.env'),'rest_api_checker')) as cn:
        candidate=freeze.build(Repository(cn),ROOT,RESEARCH,registrations)
        freeze.verify_candidate(candidate,ROOT,RESEARCH,Repository(cn))
        freeze.verify_live(candidate,ROOT)
    target.parent.mkdir(parents=True,exist_ok=True)
    raw=encode(candidate)
    with target.open('xb') as stream: stream.write(raw)
    target.with_suffix('.sha256').write_text(digest(raw)+'  candidate.json\n')
    print(json.dumps(dict(path=str(target),sha256=digest(raw),implementation_commit=candidate['implementation_commit'],
                         status=candidate['status'],instruction=candidate['instruction'],sql_schedule_persisted=False)))

if __name__=='__main__': main()

"""Hash-bind captured artifacts and sources. Does not approve Gate B or dispatch."""
import json
from capture import ROOT,RESEARCH,OUT,digest,save
from rest_api_checker.experiment import request

sources={}
for folder,base in [('implementation',ROOT),('research',RESEARCH)]:
 paths=([*sorted((ROOT/'src/rest_api_checker/experiment').glob('*.py')),ROOT/'src/rest_api_checker/experiment/output_schema_v1.json',ROOT/'src/rest_api_checker/persistence/repository.py',ROOT/'docs/experiment_evidence/comparison_schedule_v1.json',ROOT/'docs/experiment_evidence/artifact_verification.json',ROOT/'docs/development_dataset_v1_release.json',*sorted((ROOT/'tools/runtime_qualification').glob('*.py'))] if folder=='implementation' else [RESEARCH/'03_research_design/prompt_development_protocol_v1.md',RESEARCH/'03_research_design/database_design_v1.md',*sorted((RESEARCH/'03_research_design/prompt_candidates_v1').glob('*'))])
 for path in paths:
  if path.is_file(): sources[folder+':'+str(path.relative_to(base))]=digest(path.read_bytes())
# Include frozen DEV closure, references and OpenAPI copies without copying bytes.
for path in sorted((ROOT/'artifacts/development_dataset_v1').rglob('*')):
 if path.is_file(): sources['implementation:'+str(path.relative_to(ROOT))]=digest(path.read_bytes())
files={p.name:digest(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ('bundle.json','database_after.json','preservation_after.json','full_suite.xml','targeted_suite.xml','report.md')}
save('bundle.json',dict(format='gate-b-runtime-evidence-v1',author_acceptance=False,files=files,sources=sources))

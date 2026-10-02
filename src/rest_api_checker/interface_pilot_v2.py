"""Prepare exactly 18 development-only interface requests, without SQL or HTTP."""
import argparse
from pathlib import Path

from .experiment import parser, renderer, request_v2
from .experiment.encoding import check, digest, encode, loads
from .experiment.request import MODELS, OPTIONS
from .persistence.importer import DEV_HASH, load_development

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent / 'bachelor_rest_api_checker'
DEV_CASES = tuple(f'DEV-{i:02}' for i in range(1, 13))
P2_PATH = '03_research_design/prompt_candidates_v1/p2_structured_checklist_v1.txt'


def pilot_files(cases, model_digests, *, root=ROOT, research=RESEARCH):
    """Explicit selection from already exposed DEV cases; no reference projection."""
    check(len(cases) == 2 and len(set(cases)) == 2 and set(cases) <= set(DEV_CASES),
          'EXACTLY_TWO_DISTINCT_RELEASED_DEV_CASES_REQUIRED')
    check(type(model_digests) is dict and set(model_digests) == set(MODELS),
          'EXACT_THREE_MODEL_DIGESTS_REQUIRED')
    root, research = Path(root), Path(research)
    manifest, closure = load_development(root/'artifacts/development_dataset_v1',
                                        root/'docs/development_dataset_v1_release.json', research)
    prompt = (research/P2_PATH).read_bytes()
    files = {'prompt/P2.txt': prompt,
             'schema/output_transport_schema_v2.json': request_v2.SCHEMA_PATH.read_bytes()}
    slots = []
    for code in cases:
        case = next(c for c in manifest['cases'] if c['case_id'] == code)
        contract = manifest['sources'][manifest['contracts'][case['api']]]
        evidence = renderer.Evidence(closure[contract['path']], case['operation']['method'],
            case['operation']['path'], case['status'], case['content_type'], closure[case['body']['path']])
        files[f'sources/{code}/contract.json'] = evidence.contract
        files[f'sources/{code}/body.bin'] = evidence.body
        rendered = renderer.render(evidence, contract_identity=contract['path'],
                                   body_identity=case['body']['path'])
        for model in MODELS:
            for mode in request_v2.MODES:
                request = request_v2.build_request_v2(rendered,
                    interface=request_v2.OutputInterfaceV2(mode), prompt=prompt,
                    model=model, model_digest=model_digests[model], repetition=1)
                request_v2.validate_request_v2(request)
                number = len(slots) + 1
                path, sidecar = f'requests/{number:02}.json', f'provenance/{number:02}.json'
                files[path], files[sidecar] = request.body, encode(request.metadata)
                slots.append(dict(slot=number, case=code, model=model, mode=mode, repetition=1,
                    seed=101, request_path=path, provenance_path=sidecar,
                    request_sha256=digest(request.body),
                    request_identity_sha256=request.metadata['request_identity_sha256']))
    plan = dict(format='output-interface-pilot-v2', status='PREPARED_NOT_EXECUTED',
        purpose='development_output_interface_pilot', planned_calls=18, completed_calls=0,
        cases=list(cases), models=model_digests,
        interfaces=[request_v2.OutputInterfaceV2(m).binding() for m in request_v2.MODES],
        generation_options=OPTIONS, num_predict=512, timeout_seconds=300,
        development_manifest_sha256=DEV_HASH, development_release_sha256=digest(closure['release.json']),
        prompt_sha256=digest(prompt), parser_version=parser.VERSION, parser_sha256=parser.artifact_hash(),
        renderer_sha256=renderer.artifact_hash(), request_builder_sha256=request_v2.artifact_hash(),
        pilot_preparer_sha256=digest(Path(__file__).read_bytes()), slots=slots,
        files=[dict(path=n, sha256=digest(b), bytes=len(b)) for n, b in sorted(files.items())])
    files['manifest.json'] = encode(plan)
    files['manifest.sha256'] = (digest(files['manifest.json']) + '  manifest.json\n').encode('ascii')
    return files


def prepare_pilot(cases, model_digests, output, *, root=ROOT, research=RESEARCH):
    output = Path(output).resolve()
    check(not output.is_relative_to(Path(research).resolve()), 'RESEARCH_REPOSITORY_READ_ONLY')
    files = pilot_files(cases, model_digests, root=root, research=research)
    output.mkdir(parents=True, exist_ok=False)  # Never replace a historical or earlier pilot directory.
    for name, raw in sorted(files.items()):
        path = output/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return loads(files['manifest.json'])


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--cases', nargs=2, choices=DEV_CASES, required=True)
    cli.add_argument('--model-digests', type=Path, required=True,
                     help='JSON object mapping the three model names to full, operator-verified digests')
    cli.add_argument('--output', type=Path, required=True, help='New directory; no existing files are overwritten')
    args = cli.parse_args(argv)
    plan = prepare_pilot(args.cases, loads(args.model_digests.read_bytes()), args.output)
    print(f"Prepared {plan['planned_calls']} requests; completed model calls: 0")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

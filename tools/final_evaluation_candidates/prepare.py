"""Offline, pre-reference materialization of the exact author-confirmed plan.

Standalone standard library only. Never import the application, Oracle, schema
validators, providers or database. The caller must supply explicit authorization.
"""
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess

PLAN = '03_research_design/final_case_construction_plan_v1.json'
PLAN_HASH = 'aefae56258323ad6da7edadf714c8ca01fadd5bb953efc4c479a5ec2bbb7227c'
MD_HASH = 'c6b145ecffdaaa50e9413fa6e18651c41aa424d9fcf9caba6342c8e1d5969e27'
TECH_BASE = '830b418f057775de38afbe208ed2184bea4aebb0'
RESEARCH_BASE = '3d21fef7743856bbfad51bcc306fa8499b0f2f90'
PREREQUISITES = ['e549cad575b34ada71b282fb0c2876acbb146ce0',
 'b7389dd0b84f7328d3a69bcb697259cbdb7c47a4',
 '13f91d011de6822ee538c5ee6f47122397ee3976',
 'f8de90eda451b96f08f1de56d4389f567d78ce16',
 '6c16278afdc70a7694669765fa327a433b9ca7a4', RESEARCH_BASE]
BASES = '04_case_studies/final_evaluation_bases_v1'
NATURAL = '04_case_studies/htts/parent_observations_v1/observations/HTTS-PO-0003'
NAT_REVIEW = '04_case_studies/htts/parent_observations_v1/reference_review/HTTS-PO-0003'
CORPUS = '03_research_design/parent_observation_novelty_review_v1.json'
AUTHORIZED = {f'FC-EDX-{i:03}' for i in (1, 2, 5, 6)} | {f'FC-HTTS-{i:03}' for i in range(1, 11)}
STATE = 'MATERIALIZED_REFERENCE_NOT_REVIEWED'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def document(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Non-JSON constant: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def record(path, raw):
    return {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def bound(path, digest, size=None):
    raw = path.read_bytes()
    require(sha(raw) == digest and (size is None or len(raw) == size), f'Source binding mismatch: {path}')
    return raw


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def children(text, start):
    # Byte-span strategy follows construction.py, without its Oracle coupling.
    decoder = json.JSONDecoder()
    is_object = text[start] == '{'
    require(is_object or text[start] == '[', 'Mutation path crosses scalar')
    pos, index, comma = start + 1, 0, None
    while True:
        while text[pos] in ' \t\r\n':
            pos += 1
        if text[pos] in '}]':
            return
        member_start = pos
        if is_object:
            key, pos = decoder.raw_decode(text, pos)
            while text[pos] in ' \t\r\n:':
                pos += 1
        else:
            key = str(index)
        value_start = pos
        _, pos = decoder.raw_decode(text, pos)
        yield key, member_start, value_start, pos, comma
        while text[pos] in ' \t\r\n':
            pos += 1
        if text[pos] != ',':
            return
        comma = pos
        pos += 1
        index += 1


def splice(body, change):
    original = strict_json(body)
    text = body.decode('utf-8')
    pointer = change['instance_pointer']
    require(pointer.startswith('/'), 'Non-root pointer required')
    parts = [p.replace('~1', '/').replace('~0', '~') for p in pointer[1:].split('/')]
    start = len(text) - len(text.lstrip())
    for part in parts:
        members = list(children(text, start))
        positions = [i for i, m in enumerate(members) if m[0] == part]
        require(len(positions) == 1, 'Missing or ambiguous target')
        position = positions[0]
        _, member_start, start, end, comma = members[position]
    expected = copy.deepcopy(original)
    container = expected
    for part in parts[:-1]:
        container = container[int(part)] if isinstance(container, list) else container[part]
    key = int(parts[-1]) if isinstance(container, list) else parts[-1]
    action = change['action']
    if action == 'remove_member':
        require(isinstance(container, dict), 'Only object member deletion permitted')
        start = comma if comma is not None else member_start
        if comma is None and len(members) > 1:
            end = members[1][1]
        replacement = b''
        del container[key]
    elif action == 'replace_value':
        kind = change['replacement_kind']
        value = change.get('replacement_literal')
        require(kind in ('integer', 'string', 'null'), 'Unsupported replacement kind')
        require(type(value) is {'integer': int, 'string': str, 'null': type(None)}[kind], 'Replacement kind mismatch')
        require(type(container[key]) is (str if kind == 'integer' else list), 'Unexpected target type')
        container[key] = value
        replacement = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    else:
        raise ValueError('Unsupported body action')
    start, end = len(text[:start].encode()), len(text[:end].encode())
    after = body[:start] + replacement + body[end:]
    require(after != body, 'No-op body mutation')
    # Independent parsed-tree comparison checks every non-target value as well.
    require(strict_json(after) == expected, 'Unintended second body mutation')
    return after, {'start_byte': start, 'end_byte_exclusive': end,
                   'removed_hex': body[start:end].hex(), 'replacement_hex': replacement.hex(),
                   'prefix_sha256': sha(body[:start]), 'suffix_sha256': sha(body[end:]),
                   'outside_span_identical': True, 'parsed_tree_exactly_planned': True}


def transform(body, status, media, change):
    strict_json(body)
    before = (body, status, media)
    edit = None
    if change:
        action = change['action']
        if action == 'replace_http_status':
            status = change['literal']
            require(type(status) is int, 'Status must be integer')
        elif action == 'replace_content_type':
            media = change['literal']
            require(type(media) is str, 'Media must be raw string')
        else:
            body, edit = splice(body, change)
        require(sum(a != b for a, b in zip(before, (body, status, media))) == 1,
                'Exactly one response layer must change')
    return body, status, media, edit


def shape(value):
    if isinstance(value, dict):
        return {'object': {k: shape(v) for k, v in sorted(value.items())}}
    if isinstance(value, list):
        return {'array': [shape(v) for v in value]}
    return {type(None): 'null', bool: 'boolean', int: 'integer', float: 'number', str: 'string'}[type(value)]


def group_check(cases, plan):
    by_id = {c['case_id']: c for c in cases}
    require(len(cases) == 14 and len(by_id) == 14 and set(by_id) == AUTHORIZED, 'Unexpected candidate register')
    for p in plan['primary_candidates']:
        c = by_id[p['case_id']]
        for key in ('api','operation','provenance_class','base_template_id','base_group_id',
                    'construction_family_id','cap_family_id','structural_pattern_group_id',
                    'parent_observation_id','parent_family_id','root_id','immediate_parent_id',
                    'fault_control_family','variant','sibling_ids','dependency_relation'):
            require(c[key] == p[key], 'Plan mapping mismatch: ' + key)
        require(len(c['sibling_ids']) == 1, 'Unexpected sibling count')
        sibling = by_id[c['sibling_ids'][0]]
        require(c['case_id'] in sibling['sibling_ids'] and c['cap_family_id'] == sibling['cap_family_id'], 'Asymmetric sibling mapping')
    families = Counter(c['cap_family_id'] for c in cases)
    groups = Counter(c['structural_pattern_group_id'] for c in cases)
    require(len(families) == 7 and set(families.values()) == {2}, 'Family cap violation')
    require(len(groups) == 4, 'Structure group violation')
    for family in plan['families']:
        require({c['case_id'] for c in cases if c['cap_family_id'] == family['family_id']} == set(family['primary_case_ids']), 'Family mapping drift')
    return {'family_counts': dict(families), 'structure_group_counts': dict(groups),
            'construction_families': 6, 'natural_families': 1, 'max_two_verified': True,
            'exact_authorized_ids_only': True, 'symmetric_siblings_verified': True}


def preflight(research, technical):
    plan = strict_json(bound(research / PLAN, PLAN_HASH))
    bound(research / PLAN.replace('.json', '.md'), MD_HASH)
    for commit in PREREQUISITES:
        subprocess.run(['git','-C',str(research),'merge-base','--is-ancestor',commit,'HEAD'], check=True)
    subprocess.run(['git','-C',str(technical),'merge-base','--is-ancestor',TECH_BASE,'HEAD'], check=True)
    # Original research packages remain bound to the manual-acceptance commit.
    packages = [BASES, NAT_REVIEW, NATURAL]
    package_sources = []
    for directory in packages:
        for name in git(research,'ls-tree','-r','--name-only',RESEARCH_BASE,'--',directory).decode().splitlines():
            old = git(research,'show',RESEARCH_BASE+':'+name)
            current = bound(research/name,sha(old),len(old))
            package_sources.append(record(name,current))
    prior = strict_json((research/BASES/'source_closure.json').read_bytes())
    source_records = []
    for source in plan['sources']:
        root = research if source['repository'] == 'research' else technical
        historical = git(root,'show',source['commit']+':'+source['path'])
        require(sha(historical) == source['sha256'], 'Historical source mismatch')
        # The approved base milestone already records this documentation delta.
        expected = next(s for s in prior['plan_sources'] if s['id'] == source['id'])
        if source['id'] == 'implementation_record':
            previous = git(root,'show',TECH_BASE+':'+source['path'])
            require(sha(previous) == expected['current_sha256'], 'Base milestone documentation mismatch')
            raw = (root/source['path']).read_bytes()
            require(raw.endswith(previous), 'Historical implementation documentation changed')
            require(raw == git(root,'show','HEAD:'+source['path']), 'Uncommitted implementation documentation')
        else:
            raw = bound(root/source['path'], expected['current_sha256'], expected['current_bytes'])
        source_records.append({**source,'current_sha256':sha(raw),'current_bytes':len(raw),
                               'difference_reason':expected['difference_reason'],
                               'current_commit':git(root,'rev-parse','HEAD').decode().strip()})
    for source in plan['natural_evidence']:
        bound(research/source['path'],source['sha256'],source['bytes'])
    corpus = strict_json((research/CORPUS).read_bytes())
    for source in corpus['comparison_source_inventory']:
        bound(Path(source['path']),source['sha256'],source['size_bytes'])
    for directory in (BASES, BASES+'/reference_review', NAT_REVIEW):
        for line in (research/directory/'hashes.sha256').read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            bound(research/directory/name.lstrip('*'),digest)
    decision_path = BASES+'/reference_review/manual_decision_2026-09-27.json'
    decision = strict_json((research/decision_path).read_bytes())
    natural_decision_path = NAT_REVIEW+'/manual_decision_2026-09-27.json'
    natural_decision = strict_json((research/natural_decision_path).read_bytes())
    require(decision['plan_binding']['sha256'] == PLAN_HASH and natural_decision['plan_binding']['sha256'] == PLAN_HASH, 'Review plan mismatch')
    expected_ids = {b['base_template_id'] for b in plan['base_templates']}
    require(len(decision['rows']) == 6 and {r['base_id'] for r in decision['rows']} == expected_ids, 'Base review coverage mismatch')
    # Load ONLY the standard-library serializer; never construction.py.
    spec = importlib.util.spec_from_file_location('base_serializer', technical/'tools/final_evaluation_bases/prepare.py')
    serializer_path = technical/'tools/final_evaluation_bases/prepare.py'
    require(serializer_path.read_bytes() == git(technical,'show',TECH_BASE+':tools/final_evaluation_bases/prepare.py'), 'Base serializer implementation mismatch')
    serializer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serializer)
    bases = {}
    for base in plan['base_templates']:
        ident = base['base_template_id']
        row = next(r for r in decision['rows'] if r['base_id'] == ident)
        require(row['human_decision'] == 'ACCEPT' and row['state'] == 'ACCEPTED', 'Base manual acceptance missing')
        require(row['confirmed_reference_vector'] == dict(c1='PASS',c2='PASS',c3='PASS'), 'Stored base review mismatch')
        prefix = BASES+'/bases/'+ident
        body = bound(research/prefix/'response_body.bin',row['body_sha256'])
        require(serializer.serialize_fields(base['field_specification']) == body, 'Base recipe drift')
        status = int((research/prefix/'status.txt').read_bytes())
        media = (research/prefix/'content_type.txt').read_bytes().decode()
        require((status,media) == (base['base_status'],base['base_content_type']), 'Base envelope drift')
        rr = row['oracle_result']
        result = strict_json(bound(research/BASES/'reference_review'/rr['path'],rr['sha256'],rr['bytes']))
        require(result['response']['body']['sha256'] == sha(body) and result['response']['status'] == status and result['response']['raw_content_type'] == media, 'Review response binding mismatch')
        require(result['openapi']['sha256'] == plan['contracts'][base['api']]['sha256'], 'Review contract binding mismatch')
        bases[ident] = (body,status,media,prefix+'/response_body.bin',decision_path)
    require(natural_decision['state'] == 'ACCEPTED' and natural_decision['decision'] == 'ACCEPT', 'Natural manual gate missing')
    require(natural_decision['confirmed_reference_vector'] == dict(c1='PASS',c2='PASS',c3='PASS'), 'Stored natural review mismatch')
    require(natural_decision['parent_family_id'] == 'HTTS-PF-0003', 'Natural family drift')
    observation = next(o for o in corpus['observations'] if o['id'] == 'HTTS-PO-0003')
    body = bound(research/NATURAL/'response_body.bin',natural_decision['body_sha256'])
    require(sha(body) == observation['body_sha256'] and observation['parent_family_id'] == 'HTTS-PF-0003', 'Natural observation binding mismatch')
    headers = (research/NATURAL/'response_headers.txt').read_bytes()
    require(headers.startswith(b'HTTP/1.1 422 ') and b'content-type: application/json\r\n' in headers.lower(), 'Natural envelope mismatch')
    bases['HTTS-PO-0003'] = (body,observation['http_status'],observation['content_type'],NATURAL+'/response_body.bin',natural_decision_path)
    report = {'state':'SOURCE_LOCK_VERIFIED','research_prerequisite_commit':RESEARCH_BASE,
              'technical_base_commit':TECH_BASE,'prerequisite_commits':PREREQUISITES,
              'plan_sources':source_records,'package_sources':package_sources,
              'comparison_source_inventory':corpus['comparison_source_inventory'],
              'natural_source_inventory':plan['natural_evidence'],
              'confirmed_base_ids':sorted(bases), 'stored_reviews_only_no_new_evaluation':True}
    return plan, corpus, bases, report


def compare(cases, payloads, corpus, bases):
    excluded = sum((corpus[k] for k in ('pilot_comparisons','development_comparisons','qualification_comparisons','supplemental_static_literals')), [])
    rows = excluded + corpus['observations']
    rows += [{'id':i,'group':'confirmed_base','body_hex':b[0].hex(),'body_sha256':sha(b[0]),'http_status':b[1],'content_type':b[2]} for i,b in bases.items() if i.startswith('BT-')]
    matrix, dependencies, blockers = [], [], []
    for c in cases:
        body = payloads[c['case_id']]
        instance = strict_json(body)
        for other in rows:
            other_body = bytes.fromhex(other['body_hex'])
            require(sha(other_body) == other['body_sha256'], 'Corpus payload binding mismatch')
            equal = body == other_body
            try:
                other_instance = strict_json(other_body)
                canonical_equal = json.dumps(instance,sort_keys=True,ensure_ascii=False) == json.dumps(other_instance,sort_keys=True,ensure_ascii=False)
                same_shape = shape(instance) == shape(other_instance)
            except (ValueError, UnicodeError):
                canonical_equal = same_shape = False
            allowed_source = ((c['case_id'] == 'FC-HTTS-009' and other['id'] == 'HTTS-PO-0003') or
                              (other['group'] == 'confirmed_base' and other['id'] == c['base_template_id']))
            is_excluded = other in excluded or (other['group'] == 'wave1' and other['id'] != 'HTTS-PO-0003')
            if is_excluded and (equal or canonical_equal or same_shape):
                blockers.append({'case_id':c['case_id'],'source':other['id'],'reason':'Excluded raw/canonical/typed-shape overlap requires review'})
            if equal and not allowed_source:
                blockers.append({'case_id':c['case_id'],'source':other['id'],'reason':'Unexpected source body duplicate'})
            matrix.append({'case_id':c['case_id'],'comparison_id':other['id'],'group':other['group'],
                           'body_equal':equal,'canonical_json_equal':canonical_equal,'typed_shape_equal':same_shape,
                           'triple_equal':equal and (c['supplied_http_status'],c['raw_content_type']) == (other['http_status'],other['content_type']),
                           'planned_source_dependency':allowed_source})
    for a,b in itertools.combinations(cases,2):
        equal = payloads[a['case_id']] == payloads[b['case_id']]
        triple = equal and (a['supplied_http_status'],a['raw_content_type']) == (b['supplied_http_status'],b['raw_content_type'])
        if triple or (equal and a['cap_family_id'] != b['cap_family_id']):
            blockers.append({'a':a['case_id'],'b':b['case_id'],'reason':'Unexpected candidate duplicate'})
        if equal:
            dependencies.append({'a':a['case_id'],'b':b['case_id'],'body_equal':True,'triple_equal':triple,
                                 'family':a['cap_family_id'],'reason':'Planned status/media-only siblings'})
    spike_matches = [{'case_id':c['case_id'],'source':s['source']} for c in cases for s in corpus['spike_instance_structures'] if shape(strict_json(payloads[c['case_id']])) == s['shape']]
    require(not spike_matches, 'Spike instance structure overlap')
    return {'state':'VERIFIED' if not blockers else 'BLOCKED','blockers':blockers,
            'comparison_artifact_count':len(rows),'comparison_count':len(matrix),'pairwise_candidate_count':len(cases)*(len(cases)-1)//2,
            'matrix':matrix,'shared_body_dependencies':dependencies,'spike_instance_comparisons':len(cases)*len(corpus['spike_instance_structures']),
            'dynamic_source_review':corpus['supplemental_dynamic_source_review'],
            'scope_note':'Exact bytes, parsed values and typed ordered shapes; source inventory and plan distinctness remain explicit. No independent sample or semantic contract verdict claim.'}


def prepare(research, technical, output, *, materialized_at):
    research,technical,output = map(Path,(research,technical,output))
    require(not output.exists(),'Output must not exist')
    plan,corpus,bases,source_lock = preflight(research,technical)
    files, cases, traces, payloads = {},[],[],{}
    keys = ['case_id','api','operation','provenance_class','basis_kind','parent_observation_id',
            'parent_family_id','natural_fields_null_reason','base_template_id','base_group_id',
            'construction_family_id','cap_family_id','structural_pattern_group_id','root_id',
            'immediate_parent_id','fault_control_family','variant','sibling_ids','dependency_relation',
            'base_branch','base_branch_context','response_context_source','contract_source_id','contract_sha256']
    by_id = {c['case_id']:c for c in plan['primary_candidates']}
    for ident in plan['finite_priority_order']:
        p = by_id[ident]
        source_id = p['base_template_id'] or p['parent_observation_id']
        before,status,media,source_path,review_path = bases[source_id]
        body,new_status,new_media,edit = transform(before,status,media,p['change'])
        require((new_status,new_media) == (p['planned_supplied_status'],p['planned_raw_content_type']), 'Planned envelope mismatch')
        prefix = 'cases/'+ident+'/'
        artifacts = {'response_body.bin':body, 'status.txt':str(new_status).encode(), 'content_type.txt':new_media.encode()}
        trace = {'case_id':ident,'recipe_id':ident+'/plan-recipe-v1','plan_pointer':'/primary_candidates/'+str(plan['primary_candidates'].index(p)),
                 'plan_sha256':PLAN_HASH,'recipe':p['recipe'],'change':p['change'],
                 'source_id':source_id,'source':record(source_path,before),
                 'before_status':status,'before_raw_content_type':media,
                 'after_body_sha256':sha(body),'after_status':new_status,'after_raw_content_type':new_media,
                 'byte_splice':edit,'valid_json_syntax':True,'isolation_verified':True,
                 'identity_copy':p['change'] is None,'no_contract_evaluation':True}
        artifacts['transformation.json'] = document(trace)
        c = {k:p[k] for k in keys}
        c.update(state=STATE,materialized_at=materialized_at,supplied_http_status=new_status,
                 raw_content_type=new_media,body_sha256=sha(body),body_bytes=len(body),recipe_id=trace['recipe_id'],
                 source_body=record(source_path,before),manual_base_review=record(review_path,(research/review_path).read_bytes()),
                 contract_snapshot=next(s for s in plan['sources'] if s['id']==p['contract_source_id']),
                 reference_review_state='NOT_STARTED',model_evidence_files=['response_body.bin','status.txt','content_type.txt'],
                 metadata_visibility='RESEARCH_ONLY_NEVER_MODEL_INPUT',
                 artifacts={name:record(prefix+name,raw) for name,raw in artifacts.items()})
        c['natural_source_bindings'] = plan['natural_evidence'] if p['parent_observation_id'] else None
        c['natural_limitations'] = plan['natural_limitations'] if p['parent_observation_id'] else None
        artifacts['metadata.json'] = document(c)
        files.update({prefix+name:raw for name,raw in artifacts.items()})
        cases.append(c); traces.append(trace); payloads[ident] = body
    groups = group_check(cases,plan)
    comparison = compare(cases,payloads,corpus,bases)
    if comparison['blockers']:
        raise ValueError('EXCLUSION_BLOCKERS: '+json.dumps(comparison['blockers']))
    manifest = {'format':'final-evaluation-candidates-v1','state':STATE,'case_count':14,
                'materialized_at':materialized_at,'plan':record(PLAN,(research/PLAN).read_bytes()),
                'plan_commit':PREREQUISITES[0],'research_prerequisite_commit':RESEARCH_BASE,
                'technical_commit':git(technical,'rev-parse','HEAD').decode().strip(),
                'implementation':record('tools/final_evaluation_candidates/prepare.py',Path(__file__).read_bytes()),
                'case_ids_in_planned_construction_review_order':plan['finite_priority_order'],
                'order_is_final_dataset_order':False,'final_dataset_membership_assigned':False,
                'final_reference_assigned':False,'database_imported':False,
                'cases':cases,'dependency_counts':groups,
                'next_gate':'Separate authorization for final Reference Oracle execution on these immutable candidates, then independent manual Ground-Truth review. No dataset freeze or Main authorization.'}
    files.update({'manifest.json':document(manifest),'source_lock.json':document(source_lock),
                  'construction_verification.json':document({'state':'VERIFIED','case_count':14,'traces':traces,'groups':groups,'contract_verdicts_assigned':False}),
                  'exclusion_verification.json':document(comparison)})
    lines = ['# Final candidate materialization v1','', '**State: '+STATE+'**','',
             'FACT FROM ARTIFACTS: Exactly 14 authorized candidates; deterministic transformations only. No reference labels or final dataset membership/order. Provenance classes below describe construction intent, not measured outcomes.','',
             '| ID | API | Provenance | Mechanism | Base / family / group | Status | Raw Content-Type | Body SHA-256 | Bytes |',
             '|---|---|---|---|---|---:|---|---|---:|']
    for c in sorted(cases,key=lambda c:c['case_id']):
        lines.append('| '+' | '.join(str(x) for x in [c['case_id'],c['api'],c['provenance_class'],c['fault_control_family'] or 'natural',
          (c['base_template_id'] or c['parent_observation_id'])+' / '+c['cap_family_id']+' / '+c['structural_pattern_group_id'],
          c['supplied_http_status'],c['raw_content_type'],c['body_sha256'],c['body_bytes']])+' |')
    lines += ['', 'FACT FROM VERIFICATION: Single-layer edits and independent parsed-tree checks pass for every construction; unaffected byte spans are preserved. Natural retention is byte-exact. All bodies are valid JSON; no malformed-body recipe is present.',
              '',f"Exclusion comparison: {comparison['comparison_count']} comparisons against {comparison['comparison_artifact_count']} records; 91 final-candidate pairs and 168 spike-structure comparisons; no blockers.",
              '', 'Six construction families and one natural family each contain two candidates. Four broad structure groups remain explicit. Three planned equal-body pairs differ in status or media and retain shared-family dependence. No statistical independence claim.',
              '', 'FACT FROM PROTOCOL: Contract-only ancestry and per-case scientific-distinctness rationales remain at the hash-bound plan pointers. Raw, canonical and typed-shape checks supplement that prior author decision, not replace it. Dynamic qualification contexts remain documented in exclusion_verification.json.',
              '', 'Natural limitation: Deployment identity and parity with the frozen OpenAPI snapshot remain unknown; client-side capture does not prove remote receipt.',
              '', 'Boundary: No API/network, Oracle or validator execution, new reference labels, dataset membership/freeze, DB import, model call, Main Evaluation or push. Research metadata/recipes never form model-visible evidence.',
              '', 'Next gate: Separately authorize final Reference Oracle execution on these exact 14 cases, then independent manual Ground-Truth review.']
    files['materialization_report.md'] = ('\n'.join(lines)+'\n').encode()
    files['release_integrity.json'] = document({'state':STATE,'kind':'CANDIDATE_MATERIALIZATION_ONLY',
        'release_complete':True,'dataset_released':False,'files':[record(p,b) for p,b in sorted(files.items())],
        'hash_scope':'Payload files; self included by hashes.sha256. Hash inventory excludes itself.'})
    files['hashes.sha256'] = ''.join(f'{sha(raw)}  {p}\n' for p,raw in sorted(files.items())).encode()
    output.mkdir(parents=True)
    for name,raw in files.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research',required=True,type=Path)
    parser.add_argument('--technical',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--materialized-at',required=True)
    args=parser.parse_args()
    result=prepare(args.research,args.technical,args.output,materialized_at=args.materialized_at)
    print(f"Materialized {result['case_count']} candidates: {STATE}")

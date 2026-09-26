"""Lossless adapters for released DEV v1 and approved prompt-candidates-v1.

Only reads existing artifacts. Deliberately does not import construction,
development_dataset or the Oracle. No expected-label or mutation-intent adapter.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from .database import json_bytes, lock, require, timestamp
from .repository import ORIGINS

DEV_HASH = '8cac438a328c67a550ba883cbf9953a4867dc17ad8b5ed1fdf0f2bb55b0bb974'
CONTRACT_HASHES = {'edx':'4fb9c2bf81b401463dcd66f463c214a3019b75b48f0a88db1cf541a770ea4fbc',
                  'htts':'084b2d72929226f0984cda1ce7758c8e7d9fb1aa7e1001e308160da440828e42'}
PROMPT_HASHES = {'P1':'f451d8bdc89cb1f3d8a2b2dbc0c86fc490f3033d98a689a128e3f4069aad1cc6',
                 'P2':'50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f',
                 'P3':'5561c7d953b7baf3bfcc72f7bfeeccec2c64f11b5b4989788e227270205a94fb'}


def read_bound(root, descriptor):
    relative = descriptor.get('archived_path',descriptor.get('path'))
    target = (root / relative).resolve()
    require(not Path(relative).is_absolute() and target.is_relative_to(root.resolve()), 'Source path escapes archive')
    raw = target.read_bytes()
    require(sha256(raw).hexdigest()==descriptor['sha256'], f'Source/hash binding mismatch: {relative}')
    length = descriptor.get('size_bytes',descriptor.get('byte_length'))
    require(length is None or len(raw)==length, f'Source size mismatch: {relative}')
    return relative, raw


def file_descriptors(value):
    if isinstance(value,dict):
        if {'path','sha256','size_bytes'} <= value.keys():
            yield value
        for child in value.values():
            yield from file_descriptors(child)
    elif isinstance(value,list):
        for child in value:
            yield from file_descriptors(child)


def response_digest(row, body):
    return sha256(json.dumps(['response-v1',row['status'],row['content_type'],body.hex()],
                             separators=(',',':')).encode('utf-8')).hexdigest()


def load_development(staging, tracked_release, research):
    staging, research = Path(staging), Path(research)
    raw = (staging/'manifest.json').read_bytes()
    manifest = json.loads(raw)
    require(sha256(raw).hexdigest()==DEV_HASH, 'Released DEV manifest hash mismatch; STOP, never regenerate')
    sidecar = (staging/'manifest.sha256').read_bytes()
    require(sidecar==f'{DEV_HASH}  manifest.json\n'.encode(), 'Manifest sidecar mismatch')
    release_raw = (staging/'release.json').read_bytes()
    require(release_raw==Path(tracked_release).read_bytes(), 'Tracked/staged release mismatch')
    release = json.loads(release_raw)
    require(release['approved_manifest_sha256']==DEV_HASH and release['release_status']=='AUTHOR_APPROVED_FOR_PROMPT_DEVELOPMENT',
            'Released source required')
    ids = [f'DEV-{i:02}' for i in range(1,13)]
    require(manifest['format']=='development-dataset-v1' and [r['case_id'] for r in manifest['cases']]==ids, 'Native format/order mismatch')
    require([r['case_id'] for r in release['cases']]==ids and all(r['approved'] and r['manually_reviewed'] for r in release['cases']), 'Release coverage mismatch')
    closure = {'manifest.json':raw,'manifest.sha256':sidecar,'release.json':release_raw}
    for descriptor in file_descriptors(manifest):
        name, content = read_bound(staging,descriptor)
        require(name not in closure or closure[name]==content, 'Conflicting source path')
        closure[name] = content
    # Current approval document is additional authority; never replace the historical staged document.
    name, content = read_bound(research,release['research_approval'])
    closure['release-authority/'+name] = content
    records = {}
    for row in manifest['cases']:
        body = closure[row['body']['path']]
        envelope = json.loads(closure[row['response']['path']])
        require(envelope=={'status':row['status'],'content_type':row['content_type'],'body':row['body']}, 'Response envelope mismatch')
        require(response_digest(row,body)==row['response_sha256'], 'Versioned response digest mismatch')
        root = manifest['roots'][row['root_family']]
        require(root['api']==row['api'] and row['api'] in CONTRACT_HASHES, 'Family/API mismatch')
        contract_desc = manifest['sources'][manifest['contracts'][row['api']]]
        require(row['contract_sha256']==contract_desc['sha256']==CONTRACT_HASHES[row['api']], 'Contract mismatch')
        parent = records.get(row['immediate_parent'])
        if row['immediate_parent'] is not None:
            require(parent is not None, 'Missing parent, cycle or wrong source order')
            require(parent['root_family']==row['root_family'] and parent['contract_sha256']==row['contract_sha256'], 'Lineage mismatch')
            for field in ('status','content_type','response_sha256'):
                require(row['parent_'+field]==parent[field], 'Parent projection mismatch')
            require(row['parent_body_sha256']==parent['body']['sha256'], 'Parent body mismatch')
            edit = (row['transformation'] or {}).get('body_edit')
            if edit is not None:
                before = closure[parent['body']['path']]
                require(0 <= edit['start'] <= edit['end'] <= len(before), 'Invalid recorded splice')
                require(before[:edit['start']]+closure[edit['replacement']['path']]+before[edit['end']:]==body, 'Recorded splice mismatch')
        else:
            require(all(row[k] is None for k in ('parent_status','parent_content_type','parent_body_sha256','parent_response_sha256')), 'Unexpected parent metadata')
        if row['origin']=='NATURAL':
            require(parent is None and row['observation_source']==root['source_directory'], 'Natural observation lineage mismatch')
            for filename in root['files']:
                require(f"{root['source_directory']}/{filename}" in manifest['sources'], 'Missing source companion')
        require(row['origin'] in ORIGINS, 'Unknown native origin')
        records[row['case_id']] = row
    require(Counter(r['origin'] for r in records.values())=={'NATURAL':3,'SYNTHETIC_CONFORMANT':2,'SYNTHETIC_INCONSISTENT':7}, 'Origin inventory mismatch')
    return manifest, closure


def import_development(repo, staging, tracked_release, research):
    manifest, closure = load_development(staging,tracked_release,research)
    with repo.transaction():
        lock(repo.cn,'import:development-dataset-v1')
        archive = {name:repo.archive(name,raw) for name,raw in closure.items()}
        source_id = archive['manifest.json']
        dataset_id = repo.dataset('development_dataset','v1','development')
        contracts, operations, families = {}, {}, {}
        for api, source in manifest['contracts'].items():
            api_id = repo.api(api)
            descriptor = manifest['sources'][source]
            contracts[api] = repo.contract(api_id,archive[descriptor['path']],json.loads(closure[descriptor['path']])['openapi'])
            for family, root in manifest['roots'].items():
                if root['api']==api:
                    families[family] = repo.family(api_id,family)
        cases, memberships = {}, []
        for i,row in enumerate(manifest['cases']):
            key = (row['api'],row['operation']['method'],row['operation']['path'])
            if key not in operations:
                operations[key] = repo.operation(contracts[key[0]],key[1],key[2])
            observed = None
            if row['origin']=='NATURAL':
                descriptor = manifest['sources'][row['observation_source']+'/request_metadata.txt']
                metadata = dict(line.split('=',1) for line in closure[descriptor['path']].decode().splitlines() if '=' in line)
                observed = timestamp(metadata.get('timestamp_utc'))
            existing = repo.cn.execute('SELECT id,response_id,source_file_id,source_pointer FROM dbo.test_cases WHERE source_namespace=? AND native_case_id=?',
                                       'development-dataset-v1',row['case_id']).fetchone()
            if existing:
                require(existing[2]==source_id and existing[3]==f'/cases/{i}', 'Changed source under native case identity')
                response_id = existing[1]
                equal_time = repo.cn.execute('''SELECT 1 FROM dbo.responses WHERE id=? AND
                    ((observed_at IS NULL AND ? IS NULL) OR observed_at=CONVERT(datetimeoffset(7),?,127))''',
                    response_id,observed,observed).fetchone()
                require(equal_time is not None, 'Stored/source acquisition timestamp mismatch')
            else:
                response_id = repo.response(row['status'],row['content_type'],archive[row['body']['path']],observed)
            case_id = repo.case(source_namespace='development-dataset-v1',native_case_id=row['case_id'],
                operation_id=operations[key],response_id=response_id,family_id=families[row['root_family']],
                origin=ORIGINS[row['origin']],parent_case_id=cases.get(row['immediate_parent']),
                source_file_id=source_id,source_pointer=f'/cases/{i}')
            cases[row['case_id']] = case_id
            reference_id = repo.reference(case_id,1,source_id,f'/cases/{i}/oracle')
            memberships.append(repo.membership(dataset_id,case_id,reference_id,row['case_id'],i+1))
        require(repo.cn.execute('SELECT COUNT(*) FROM dbo.dataset_cases WHERE dataset_id=?',dataset_id).fetchval()==12, 'Unexpected membership count')
        # This archive map makes closure portable without adding fields to datasets.
        receipt = dict(format='development-dataset-v1-import-receipt',adapter='development-v1',
            adapter_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),dataset_id=dataset_id,
            manifest_sha256=DEV_HASH,files=[dict(path=n,file_id=archive[n],sha256=sha256(b).hexdigest()) for n,b in closure.items()],
            case_ids=cases,membership_ids=memberships)
        receipt_id = repo.archive('development-import-receipt.json',json_bytes(receipt))
        return dict(dataset_id=dataset_id,case_ids=cases,membership_ids=memberships,receipt_file_id=receipt_id,files=archive)


def import_prompts(repo, research):
    root = Path(research)
    manifest_path = '03_research_design/prompt_candidates_v1/candidate_manifest_v1.json'
    raw = (root/manifest_path).read_bytes()
    manifest = json.loads(raw)
    require(manifest['format']=='prompt-candidates-v1' and manifest['approval']['exact_texts']=='AUTHOR_APPROVED', 'Approved candidate source required')
    closure = {manifest_path:raw}
    descriptors = (manifest['candidates']+manifest['shared_blocks']+[manifest['protocol_binding'],
        manifest['semantic_equivalence_review'],manifest['approval']['exact_text_approval_record']])
    for descriptor in descriptors:
        name, content = read_bound(root,descriptor)
        closure[name] = content
    approval = json.loads(closure[manifest['approval']['exact_text_approval_record']['path']])
    for descriptor in approval['historical_records']:
        name, content = read_bound(root,descriptor)
        closure[name] = content
    require([c['id'] for c in manifest['candidates']]==['P1','P2','P3'], 'Candidate inventory mismatch')
    with repo.transaction():
        lock(repo.cn,'import:prompt-candidates-v1')
        files = {name:repo.archive(name,content) for name,content in closure.items()}
        prompts = {}
        strategies = {'P1':('Minimal / Direct','direct'), 'P2':('Structured C1 → C2 → C3 Checklist','checklist'),
                      'P3':('Explicit Contract Interpretation','explicit')}
        for candidate in manifest['candidates']:
            cid = candidate['id']
            approved = next(c for c in approval['approved_candidates'] if c['id']==cid)
            require(candidate['sha256']==PROMPT_HASHES[cid]==approved['sha256'] and
                    candidate['byte_length']==approved['byte_length'] and candidate['path']==approved['path'], 'Prompt approval binding mismatch')
            require(candidate['strategy']==strategies[cid][0], 'Unknown source strategy')
            prompts[cid] = repo.prompt(cid,'v1',strategies[cid][1],files[candidate['path']])
        return dict(prompt_ids=prompts,files=files)

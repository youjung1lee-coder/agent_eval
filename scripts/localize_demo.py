"""Migrate this PoC's existing sample drafts to Korean; preserve Golden/trace history.

This maintenance script is sample integration work, not Evaluation Core discovery.
Only explicit sample contracts are optionally approved. Production candidates stay pending.
"""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from evaluation_platform.dataset.generator import generate, scenario
from evaluation_platform.models import AgentSpec, EvaluationCase
from evaluation_platform.service import Platform


def pairs(old, new, mapping):
    if isinstance(old, str) and isinstance(new, str) and old != new:
        mapping[old] = new
    elif isinstance(old, dict) and isinstance(new, dict):
        for key in old.keys() & new.keys():
            pairs(old[key], new[key], mapping)
    elif isinstance(old, list) and isinstance(new, list):
        for left, right in zip(old, new):
            pairs(left, right, mapping)


def translated(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [translated(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: translated(v, mapping) for k, v in value.items()}
    return value


def migrate(platform, path, approve_samples=False, previous_record=None):
    adapter_record = json.loads((Path(path) / 'eval_agent.json').read_text(encoding='utf-8'))
    agent_id = adapter_record['agent_id']
    old_record = previous_record or platform.store.get('agents', agent_id)
    old_spec = AgentSpec.model_validate(old_record['spec'])
    record = platform.register(path)
    new_spec = AgentSpec.model_validate(record['spec'])
    mapping = {'Available leave':'남은 연차','Access denied':'접근이 거부되었습니다',
               'unavailable':'이용할 수 없습니다','retry':'다시 시도',
               'No supporting document':'근거 문서를 찾지 못했습니다',
               'No support document':'지원 문서를 찾지 못했습니다'}
    for field in ['knowledge_sources', 'probes', 'tools']:
        pairs(old_record['spec'][field], record['spec'][field], mapping)
    fresh = {c.id: c for c in generate(new_spec, [])}
    previous_templates = {c.id:c for c in generate(old_spec, [])}
    with platform.store.transaction() as db:
        draft = platform.store.get('drafts', agent_id, db)
        registry = platform.registry(platform.store.list('judges', db))
        for original in draft['cases']:
            case = dict(original)
            for field in ['input','expected','input_variations']:
                case[field] = translated(case.get(field), mapping)
            if case['id'] in fresh:
                template = fresh[case['id']].model_dump()
                old_template = previous_templates.get(case['id'])
                # Preserve owner overrides; refresh only unchanged sample contracts.
                if old_template and original['expected'] == old_template.expected.model_dump():
                    case['expected'] = template['expected']
                case['evidence'] = template['evidence']
                case['candidate_reason'] = template['candidate_reason']
                if approve_samples and case['review_status'] == 'pending':
                    case['review_status'] = 'approved'
            case['scenario_id'] = scenario(case['input'])
            if case['review_status'] == 'approved':
                platform.validate_case(EvaluationCase.model_validate(case), registry)
            # Never translate/rewrite original input/output, trace/span or observed error.
            original.update(case)
        platform.store.put('drafts', agent_id, draft, db)
        platform.audit('localize_sample_draft_ko', agent_id, db)
    platform.generate(agent_id)
    return agent_id, mapping


def main():
    parser = argparse.ArgumentParser(description='기존 Sample 평가 후보를 한국어로 변환합니다.')
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--approve-sample-contracts', action='store_true')
    parser.add_argument('--finalize', action='store_true')
    parser.add_argument('--source-backup', help='재등록 후 재실행 시 이전 AgentSpec이 저장된 백업 경로')
    args = parser.parse_args()
    root = Path(args.data_dir)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    backup = root / f'platform-before-ko-{stamp}.sqlite'
    with sqlite3.connect(root/'platform.sqlite') as source, sqlite3.connect(backup) as target:
        source.backup(target)
    p = Platform(root)
    historical = json.dumps(p.store.list('golden')+p.store.list('runs'),sort_keys=True,ensure_ascii=False)
    snapshots = hashlib.sha256(historical.encode()).hexdigest()
    # Translate known demo evaluator criteria via the real sample→register flow.
    for definition in p.store.list('judges'):
        if not definition['name'].startswith('Browser Judge'):
            continue
        portal = 'HR portal' in definition['criteria']
        revised = {**definition, 'version':definition['version']+1,
            'name':('HR 포털 안내 평가' if portal else 'HR 필요 서류 평가')+' · '+definition['id'][-4:],
            'criteria':'답변에 HR 포털이 포함되어야 합니다.' if portal else '답변에 필요한 서류로 관리자 승인 문서가 포함되어야 합니다.'}
        question = '연차 신청 기간과 방법, 필요한 서류를 알려주세요.'
        answer = '연차는 최소 3일 전에 HR 포털에서 신청해야 합니다. 관리자 승인 문서를 첨부해 주세요.'
        preview = p.preview_judge(revised, {'input':question,'source':'owner_manual'}, answer)
        p.register_judge(revised, preview['id'])
        print('한국어 Custom Judge:', revised['name'], preview['result']['score'], flush=True)
    previous_records={}
    if args.source_backup:
        with sqlite3.connect(f'file:{Path(args.source_backup).resolve().as_posix()}?mode=ro',uri=True) as db:
            previous_records={json.loads(row[0])['spec']['agent_id']:json.loads(row[0])
                              for row in db.execute("SELECT value FROM records WHERE bucket='agents'")}
    agent_ids=[]
    for folder in ['langgraph_agent','langflow_agent','third_test_agent']:
        path=Path('sample_agents')/folder
        agent_id=json.loads((path/'eval_agent.json').read_text(encoding='utf-8'))['agent_id']
        agent_id,_ = migrate(p,path,args.approve_sample_contracts,previous_records.get(agent_id))
        agent_ids.append(agent_id)
    after = json.dumps(p.store.list('golden')+p.store.list('runs'),sort_keys=True,ensure_ascii=False)
    assert snapshots == hashlib.sha256(after.encode()).hexdigest(), 'Historical snapshots changed'
    print('기존 Golden / 실행 이력 보존:', snapshots, flush=True)
    if args.finalize:
        for agent_id in agent_ids:
            golden=p.golden(agent_id)
            print('한국어 Golden:', agent_id, golden['version'], len(golden['cases']), golden['id'],flush=True)
    p.phoenix.close()


if __name__ == '__main__':
    main()

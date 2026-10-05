import json
from evaluation_platform.models import AgentResult
from evaluation_platform.dataset.generator import generate
from scripts.localize_demo import migrate


def test_korean_migration_preserves_trace_provenance_and_golden_history(platform):
    old=platform.store.get('agents','hr-langgraph')
    old['spec']['probes'][0]['input']='What is the leave policy?'
    platform.store.put('agents','hr-langgraph',old)
    platform.generate('hr-langgraph')
    case=next(c for c in platform.candidates('hr-langgraph') if c.id=='definition_hr-policy')
    platform.save_case('hr-langgraph',case.id,{'review_status':'approved'})
    frozen=platform.golden('hr-langgraph')
    spec,_=platform.agent('hr-langgraph')
    result=AgentResult(output='original operational answer',status='error',error='observed exception',trace_id='trace-original',span_id='span-original')
    operational=generate(spec,[{'input':'What is the leave policy?','result':result.model_dump(),'evidence':'original span evidence'}])
    draft=platform.store.get('drafts','hr-langgraph')
    draft['cases'].extend(c.model_dump() for c in operational if c.trace_id)
    platform.store.put('drafts','hr-langgraph',draft)
    before=json.dumps(frozen,sort_keys=True)
    migrate(platform,'sample_agents/langgraph_agent',True)
    assert before==json.dumps(platform.store.get('golden',frozen['id']),sort_keys=True)
    translated=next(c for c in platform.candidates('hr-langgraph') if c.span_id=='span-original')
    assert translated.input=='연차 신청 기간과 방법, 필요한 서류를 알려주세요.'
    assert translated.original_input=='What is the leave policy?'
    assert translated.original_output=='original operational answer'
    assert translated.trace_id=='trace-original' and translated.error=='observed exception'
    assert translated.review_status=='pending'
    assert all(c.review_status=='approved' for c in platform.candidates('hr-langgraph') if c.source in ('workflow','rag'))

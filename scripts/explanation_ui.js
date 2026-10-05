'use strict';
const D=JSON.parse(document.getElementById('report-data').textContent);
const $=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const json=x=>JSON.stringify(x,null,2);
const srcId=p=>'src-'+p.replaceAll('/','-').replaceAll('.','-');
const sourceLink=p=>`<a href="#${srcId(p)}">${esc(p)}</a>`;
function code(sn){return `<div class="source-title">${sourceLink(sn.path)} · L${sn.start}–${sn.end} · ${esc(sn.symbol)}</div><div class="code-block">${sn.code.split('\n').map((s,i)=>`<div class="code-line"><span class="line-number">${sn.start+i}</span><span class="line-text">${esc(s)}</span></div>`).join('')}</div>`;}
const badge=(text,cls='')=>`<span class="badge ${cls}">${esc(text)}</span>`;
const bindings=bs=>bs.map(b=>`<a href="#eval-${esc(b.evaluator_id)}">${badge(b.evaluator_id,b.role)}</a>`).join(' ');
const nonempty=o=>Object.fromEntries(Object.entries(o).filter(([k,v])=>v!==null&&!(Array.isArray(v)&&!v.length)));
const areaNames={feature:'기능',workflow:'Workflow',branch:'Branch',tool:'Tool',rag:'RAG',failure:'실패',edge:'경계',production:'운영 질문'};
let agent='hr-langgraph';
$('capture-date').textContent=new Date(D.captured_at).toLocaleString('ko-KR')+' 촬영';
$('graph-adapter').innerHTML=code(D.pipeline_snippets[0]);
$('flow-adapter').innerHTML=code(D.pipeline_snippets[1]);
$('recommend-code').innerHTML=code(D.pipeline_snippets[3]);
$('flow-projection').textContent=json(D.flow_projection);
function pathRow(label,nodes){return `<div class="path-row"><span class="key">${esc(label)}</span>${nodes.map((n,i)=>(i?'<span class="arrow">→</span>':'')+`<span class="node">${esc(n)}</span>`).join('')}</div>`;}
$('graph-topology').innerHTML=pathRow('지식',['intent','knowledge','final'])+pathRow('Tool',['intent','balance','final'])+pathRow('일반',['intent','general','final']);
$('flow-topology').innerHTML=pathRow('RAG',['TextInput','Router','Search','AnswerRag'])+pathRow('Tool',['TextInput','Router','Service','AnswerTool'])+pathRow('일반',['TextInput','Router','Help','AnswerGeneral']);
function renderOptions(selected){
  const own=D.cases.filter(c=>c.agent_id===agent);
  $('case-select').innerHTML=own.map(c=>`<option value="${esc(c.base.id)}">${c.base.source==='rag'?'RAG 문서':'Workflow'} · ${esc(c.base.id)} · ${esc(c.base.input)}</option>`).join('');
  $('case-select').value=selected||own.find(c=>c.base.id.endsWith('balance')||c.base.id.endsWith('ticket'))?.base.id||own[0].base.id;
  $('agent-hr').classList.toggle('active',agent==='hr-langgraph');
  $('agent-lf').classList.toggle('active',agent==='support-langflow');renderCase();
}
function renderCase(){
  const c=D.cases.find(c=>c.base.id===$('case-select').value),b=c.base,expected=b.expected;
  const actual=c.run,current=c.current,active=D.agents.find(a=>a.id===agent);
  const signature=bs=>json(bs.map(x=>({id:x.evaluator_id,role:x.role,scope:x.scope,target:x.target})).sort((a,b)=>a.id.localeCompare(b.id)));
  const changed=current&&signature(current.bindings)!==signature(b.bindings);
  const left=`<div class="box"><div class="kicker">SOURCE EVIDENCE</div><h3>① 실제 Agent 코드</h3><p>${esc(c.conclusion)}</p>${c.snippets.map(code).join('<br>')}<h3>② Owner 선언: ${esc(c.pointer)}</h3><p>${sourceLink(c.manifest)} · <code>${esc(c.pointer)}</code></p>${code(c.manifest_snippet)}<p class="split-caption">${esc(c.caveat)}</p></div>`;
  const shotId=b.id==='definition_hr-balance'?'hr-review':b.id==='definition_support-ticket'?'lf-review':b.id==='knowledge_password-reset'?'lf-rag':agent==='hr-langgraph'?'hr-generation':'lf-generation';
  const shot=D.screenshots.find(s=>s.id===shotId);
  let right=`<div class="box"><div class="kicker">DERIVED CONTRACT</div><div>${badge(b.source)}${badge(b.capability)}${badge(b.id)}</div><div class="question">${esc(b.input)}</div><p class="evidence">${esc(b.evidence.join(' · '))}</p><div class="inline-shot"><button data-shot="${shot.id}" aria-label="선택 사례 관련 UI 스냅샷 확대"><img src="${shot.src}" alt="${esc(shot.title)} 실제 UI"></button><p>실제 UI · ${esc(shot.title)}. 선택한 사례와 직접 대응하지 않는 경우 Agent 구성의 대표 화면입니다. 눌러 확대할 수 있습니다.</p></div><h3>③ 생성된 ExpectedContract</h3><pre class="json">${esc(json(nonempty(expected)))}</pre><details class="json-details"><summary>Coverage Target 보기 (함수 입력과 구분)</summary><pre class="json">${esc(json(b.targets))}</pre></details><h3>④ 자동 추천: 필드 → 함수</h3><div class="binding-list">${b.bindings.map(x=>{const r=D.rules[x.evaluator_id];return `<div class="binding"><a href="#eval-${esc(x.evaluator_id)}">${esc(x.evaluator_id)} · ${esc(r?.name||x.evaluator_id)}</a> ${badge(x.role,x.role)}<small><code>${esc(r?.field)}</code> <span class="arrow">→</span> ${esc(r?.condition)}</small><small><code>${esc(r?.function)}</code></small></div>`;}).join('')}</div><h3>⑤ 현재 Draft / Owner 검토 설정</h3><p>${changed?'현재 저장된 설정에는 Owner 변경이 있습니다. 자동 추천 목록과 별도로 확인하세요.':'현재 Evaluator ID / Role이 자동 추천과 같습니다. 표시 순서는 다를 수 있습니다.'}</p><div>${current?current.bindings.map(x=>badge(x.evaluator_id,x.role)).join(' '):'현재 Draft 없음'}</div><p><small>Review: ${esc(current?.review_status||'없음')} · 자동 생성 직후 기본 상태는 pending입니다.</small></p><details class="json-details"><summary>현재 Draft의 전체 계약 / Binding 확인</summary><pre class="json">${esc(json({expected:current?.expected,bindings:current?.bindings}))}</pre></details><h3>⑥ 실제 Golden 실행 결과</h3>`;
  if(actual){right+=`<p>Golden v${active.run.dataset_version} · ${badge(actual.passed?'PASS':'FAIL',actual.passed?'pass':'fail')} · ${esc(active.run.id.slice(0,12))}</p><pre class="json">${esc(actual.actual.output)}</pre><p><small>상태 ${esc(actual.actual.status)} · ${actual.actual.latency_ms.toFixed(1)}ms<br>경로 ${esc(actual.actual.workflow_path.join(' → '))}<br>검색 문서 ${esc(actual.actual.documents.map(d=>d.id).join(', ')||'없음')}</small></p><div class="binding-list">${actual.evaluators.map(e=>`<div class="binding"><strong>${esc(e.evaluator_id)}</strong> ${badge(e.role,e.role)} ${badge((e.passed?'PASS':'FAIL')+' · '+e.score.toFixed(3),e.passed?'pass':'fail')}<small>${esc(e.reason)}</small></div>`).join('')}</div><details class="json-details"><summary>실행 당시 고정된 계약 / Tool / Trace 정보</summary><pre class="json">${esc(json({expected:actual.case.expected,tool_calls:actual.actual.tool_calls,documents:actual.actual.documents,trace_id:actual.actual.trace_id}))}</pre></details>`;}else{right+='<p>최신 실행 기록에 포함되지 않았습니다.</p>';}
  right+=`<p class="split-caption">현재 생성 계약·검토한 Draft·실행 시 Golden은 서로 다른 시점의 자료입니다. 실제 점수는 Golden의 고정된 계약을 사용합니다.</p><a href="#shot-${agent==='hr-langgraph'?'hr-review':'lf-review'}">검토 UI 보기</a> · <a href="#shot-${agent==='hr-langgraph'?'hr-results':'lf-results'}">결과 UI 보기</a></div>`;
  $('case-detail').innerHTML=left+right;
  $('case-detail').querySelectorAll('[data-shot]').forEach(b=>b.addEventListener('click',()=>openShot(b.dataset.shot)));
}
function chooseCase(id){const c=D.cases.find(c=>c.base.id===id);agent=c.agent_id;renderOptions(id);$('explore').scrollIntoView({behavior:'auto'});}
function renderMatrix(){
  const ag=$('matrix-agent').value,s=$('matrix-source').value,q=$('search').value.toLowerCase();
  const rows=D.cases.filter(c=>(ag==='all'||c.agent_id===ag)&&(s==='all'||c.base.source===s)&&json([c.base,c.conclusion]).toLowerCase().includes(q));
  $('matrix-count').textContent=rows.length+' / 14개';
  $('matrix-body').innerHTML=rows.map(c=>{const b=c.base;return `<tr><td><button class="case-link" data-case="${esc(b.id)}">${esc(b.input)}<small>${esc(c.agent_id)} · ${esc(b.id)}</small></button>${badge(b.source)}</td><td>${c.snippets.map(sn=>`<a href="#${srcId(sn.path)}">${esc(sn.path.split('/').slice(-1)[0])}:${sn.start}–${sn.end}</a> · <code>${esc(sn.symbol)}</code>`).join('<br>')}<br><code>eval_agent.json ${esc(c.pointer)}</code></td><td>${esc(c.conclusion)}<br><small>${esc(Object.keys(nonempty(b.expected)).join(' / '))}</small></td><td>${bindings(b.bindings)}</td></tr>`;}).join('')||'<tr><td colspan="4" class="no-match">검색 결과가 없습니다.</td></tr>';
  $('matrix-body').querySelectorAll('[data-case]').forEach(b=>b.addEventListener('click',()=>chooseCase(b.dataset.case)));
}
const activeIds=new Set(D.cases.flatMap(c=>c.base.bindings.map(b=>b.evaluator_id)));
$('evaluator-catalog').innerHTML=Object.entries(D.rules).map(([id,r])=>`<article id="eval-${id}" class="box eval-card"><h3><code>${id}</code> · ${esc(r.name)} ${badge(r.role,r.role)} ${!activeIds.has(id)?badge('확장용 · 기본 14개 미적용'):''}</h3><dl><dt>배정 조건</dt><dd><code>${esc(r.condition)}</code></dd><dt>계약 필드</dt><dd><code>${esc(r.field)}</code></dd><dt>실제 함수</dt><dd><code>${esc(r.function)}</code></dd><dt>점수 / PASS 근거</dt><dd>${esc(r.meaning)}</dd><dt>구현 위치</dt><dd>${sourceLink('evaluation_platform/evaluators/registry.py')}${id==='faithfulness'?' · '+sourceLink('evaluation_platform/evaluators/custom_llm.py'):''}</dd></dl><details class="json-details"><summary>평가 함수의 실제 코드 펼치기</summary>${r.snippets.map(code).join('<br>')}</details></article>`).join('');
const hr=D.agents.find(a=>a.id==='hr-langgraph');
const attached=hr.run.cases.find(r=>r.case.id==='definition_hr-policy')?.evaluators.filter(e=>e.evaluator_id.startsWith('owner_'))||[];
$('custom-table').innerHTML='<div class="table-wrap"><table><thead><tr><th>Owner 기준 / ID</th><th>Golden Criteria</th><th>범위 / Threshold</th><th>실제 결과</th></tr></thead><tbody>'+attached.map(e=>{const d=hr.run.evaluator_definitions.find(d=>d.id===e.evaluator_id);return `<tr id="eval-${esc(e.evaluator_id)}"><td>${esc(d?.name)}<br><code>${esc(e.evaluator_id)}</code><br>v${d?.version}</td><td>${esc(d?.criteria)}</td><td>${esc(d?.scope)} / ${esc(d?.target||'사례 Binding')}<br>${d?.score_min}–${d?.score_max} · threshold ${d?.pass_threshold}<br>${badge(e.role,e.role)}</td><td>${badge((e.passed?'PASS':'FAIL')+' / '+e.score,e.passed?'pass':'fail')}<br><small>${esc(e.reason)}</small></td></tr>`;}).join('')+'</tbody></table></div><p class="split-caption"><code>CustomLLMEvaluator.evaluate()</code>는 모델 점수(0–1)를 Owner scale로 환산해 threshold와 비교합니다. score 필드는 정규화된 점수이고 scaled_score는 details에 남깁니다. 이 사례에는 Case Binding으로 연결되어 실행됩니다.</p>';
$('screenshots').innerHTML=D.screenshots.map(s=>`<figure class="box screenshot" id="shot-${s.id}"><button data-shot="${s.id}" aria-label="${esc(s.title)} 확대"><img src="${s.src}" alt="${esc(s.title)} 실제 UI 스냅샷" loading="lazy"></button><figcaption><h3>${esc(s.title)}</h3><p>${esc(s.caption)}</p></figcaption></figure>`).join('');
function openShot(id){const s=D.screenshots.find(s=>s.id===id);$('large-image').src=s.src;$('large-image').alt=s.title;$('image-title').textContent=s.title;$('image-caption').textContent=s.caption;$('image-dialog').showModal();}
$('screenshots').querySelectorAll('[data-shot]').forEach(b=>b.addEventListener('click',()=>openShot(b.dataset.shot)));
$('image-close').addEventListener('click',()=>$('image-dialog').close());
$('run-comparison').innerHTML=D.agents.map(a=>`<article class="box"><h3>${esc(a.title)}</h3>${badge(a.run.decision,a.run.passed?'pass':'fail')}<div class="stats" style="grid-template-columns:1fr 1fr"><div class="stat"><b>${(a.run.overall_score*100).toFixed(2)}%</b><small>Quality Evaluator 평균</small></div><div class="stat"><b>${a.run.cases.length}</b><small>Golden v${a.run.dataset_version} · 실패 ${a.run.failure_count}개</small></div></div><p><code>run_id: ${esc(a.run.id)}</code><br><small>${esc(a.run.created_at)}</small></p><p>${a.id==='hr-langgraph'?'기본 8개 + 승인된 운영 복구 1개 + Owner 사례 2개 = 11개. 미복구 운영 사례의 Gate 실패로 HOLD.':'기본 6개가 모두 통과했습니다. 최초 Framework 실행과 재사용 실행의 지연은 다를 수 있습니다.'}</p></article>`).join('');
const incident=hr.run.cases.find(r=>r.case.source==='phoenix_failure_candidate'&&!r.passed);
$('incident-detail').innerHTML=incident?`<h3>실제 실패 → Golden 연결</h3><p class="muted">이 원본 Trace는 한국어 전환 이전에 발생한 운영 시뮬레이션입니다. 원문 입력·응답은 영문 이력으로 보존하고, 새 평가 질문과 복구 계약은 한국어로 작성했습니다.</p><div class="grid"><div><p>Source: <code>${esc(incident.case.source)}</code><br>Failure Type: <code>${esc(incident.case.failure_type)}</code><br>원본 Trace: <code>${esc(incident.case.trace_id)}</code><br>원본 Span: <code>${esc(incident.case.span_id)}</code></p><p>추천 이유: ${esc(incident.case.candidate_reason)}</p><pre class="json">${esc(json({original_input:incident.case.original_input,original_output:incident.case.original_output,error:incident.case.error,latency_ms:incident.case.latency_ms}))}</pre></div><div><p>Owner가 승인한 기대 계약</p><pre class="json">${esc(json(nonempty(incident.case.expected)))}</pre><p style="margin-top:13px">새 평가 Trace: <code>${esc(incident.actual.trace_id)}</code></p>${incident.evaluators.map(e=>`<p>${badge(e.evaluator_id,e.role)}${badge(e.passed?'PASS':'FAIL',e.passed?'pass':'fail')} ${esc(e.reason)}</p>`).join('')}</div></div><p class="split-caption">Production / Failure Candidate는 생성 단계에서 bindings가 비어 있습니다. 운영 응답을 정답으로 복제하지 않고 Owner가 substantive expected와 Evaluator를 작성·승인한 뒤 Golden에 추가합니다. Failure Detector는 관찰된 status/error/tool status/retrieval/retry 신호만 사용합니다.</p>`:'<p>승인된 운영 실패 사례가 없습니다.</p>';
$('coverage-comparison').innerHTML=D.agents.map(a=>`<h4>${esc(a.id)} · 현재 승인된 Draft 기준</h4><div class="coverage-list">${a.analysis.reviewed_coverage.map(r=>`<div class="coverage-item">${esc(areaNames[r.dimension]||r.dimension)}<b>${r.covered}/${r.total??'?'}${r.percent===null?'':` · ${r.percent}%`}</b>${r.unknown?'unknown 범위 있음':''}</div>`).join('')}</div>`).join('<br>');
$('source-library').innerHTML=Object.entries(D.sources).map(([p,s])=>`<details id="${srcId(p)}"><summary>${esc(p)} · ${s.split('\n').length} lines</summary><div class="hash">SHA-256: ${D.source_hashes[p]}</div>${code({path:p,start:1,end:s.split('\n').length,symbol:'전체 원문',code:s})}</details>`).join('');
function revealSource(){const el=$(location.hash.slice(1));if(el?.tagName==='DETAILS')el.open=true;}
window.addEventListener('hashchange',revealSource);revealSource();
$('agent-hr').addEventListener('click',()=>{agent='hr-langgraph';renderOptions();});
$('agent-lf').addEventListener('click',()=>{agent='support-langflow';renderOptions();});
$('case-select').addEventListener('change',renderCase);
for(const id of ['matrix-agent','matrix-source','search'])$(id).addEventListener('input',renderMatrix);
$('print').addEventListener('click',()=>window.print());
renderOptions();renderMatrix();

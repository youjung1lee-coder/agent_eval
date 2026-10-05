const dimensionNames={feature:'기능',workflow:'Workflow Node',branch:'조건부 분기',tool:'Tool',rag:'RAG 지식 문서',failure:'실패 / 오류',edge:'경계 사례',production:'운영 질문'};
const reviewNames={pending:'검토 대기',approved:'승인',excluded:'제외'};
const runKinds={registration:'등록평가',regression:'회귀평가',platform_quality:'플랫폼 품질평가'};
const evaluatorNames={exact:'문자열 일치',tool_call:'Tool 호출 정확성',workflow_path:'Workflow 경로 정확성',rag_retrieval:'RAG 검색 정확성',latency:'응답 시간',error_detection:'실행 상태 / 오류',behavior:'필수 / 금지 응답',permission:'접근 권한',output_schema:'출력 JSON Schema',runtime_reference:'Tool 결과 참조',llm_judge:'LLM 정확성 Judge',semantic_similarity:'의미 유사성 Judge',faithfulness:'답변 근거 충실도'};
const failureNames={timeout:'시간 초과',execution_error:'실행 오류',tool_failure:'Tool 호출 실패',empty_retrieval:'RAG 검색 결과 없음',empty_response:'빈 응답',high_latency:'응답 지연',workflow_interrupted:'Workflow 중단',repeated_retry:'반복 재시도'};
const legacyReasons={
  'Owner-supplied integration probe mapped to discovered definition; not inferred business truth':'Owner의 평가 계약을 발견된 Agent 구성에 매핑했습니다. 업무 정답을 임의로 추론하지 않았습니다.',
  'Observed production input. Owner must supply expected contract; output is NOT ground truth':'실제 운영 질문에서 생성했습니다. Owner가 기대 응답과 평가 계약을 작성해야 하며, 운영 응답을 정답으로 간주하지 않습니다.',
  'execution status explicitly reports timeout':'실행 상태에 시간 초과가 명시되어 있습니다.',
  'tool call result explicitly reports error':'Tool 호출 결과에 오류가 명시되어 있습니다.',
  'retrieval attempted, returned zero documents':'RAG 검색을 수행했지만 반환된 문서가 없습니다.',
  'observed final response is empty':'관찰된 최종 응답이 비어 있습니다.',
  'runtime explicitly reports interrupted workflow':'Runtime에 Workflow 중단이 명시되어 있습니다.'
};
function reasonText(value){return legacyReasons[value] || String(value||'').replace('observed status/error:', '관찰된 실행 상태 / 오류:');}
function evaluatorName(id){return custom.find(d=>d.id===id)?.name || evaluatorNames[id] || id;}
function contractSummary(c){
  const e=c.expected;if(e.reference_output)return e.reference_output;
  const parts=[];
  if(e.required_output.length)parts.push('필수 문구: '+e.required_output.join(', '));
  if(e.tool_calls.length)parts.push('Tool: '+e.tool_calls.map(t=>t.name+' '+JSON.stringify(t.args||{})).join(', '));
  if(e.required_nodes.length)parts.push('필수 Node: '+e.required_nodes.join(' → '));
  if(e.valid_paths.length)parts.push('실행 경로: '+e.valid_paths.map(p=>p.join(' → ')).join(' / '));
  if(e.document_ids.length)parts.push('기준 문서: '+e.document_ids.join(', '));
  if(e.forbidden_tools.length)parts.push('금지 Tool: '+e.forbidden_tools.join(', '));
  if(e.permission_denied!==null)parts.push('접근 차단: '+(e.permission_denied?'필요':'불필요'));
  if(parts.length)parts.push('기대 상태: '+e.expected_status);
  return parts.join(' · ') || 'Owner가 기대 응답과 평가 계약을 작성해야 합니다.';
}
const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const json = value => JSON.stringify(value, null, 2);
let agents = [], cases = [], catalog = [], custom = [], analysis = null, runs = [], goldens = [], editing = null;
let judgeId = '', judgeVersion = 1, preview = null;
const sourceNames = {workflow:'Workflow',rag:'RAG / 지식 문서',production_trace:'운영 Trace',phoenix_failure_candidate:'실패 후보',owner_manual:'Owner 직접 작성'};
const descriptions = {generation:['데이터셋 생성 · Coverage','Agent 기능을 분석하고 근거가 있는 평가 데이터셋을 생성합니다.'],review:['Owner 검토','평가 후보를 검토하고 버전이 있는 Golden Dataset으로 확정합니다.'],results:['평가 결과','점수·실패 이유·Gate 판정과 원본 Trace를 확인합니다.']};

async function api(path, method='GET', data) {
  const response = await fetch('/api' + path, {method, headers:{'Content-Type':'application/json'}, body:data === undefined ? undefined : JSON.stringify(data)});
  const payload = await response.json();
  if (!response.ok) throw Error(typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail ?? payload));
  return payload;
}
function notice(message, error=false) { $('notice').hidden = false; $('notice').className = error ? 'error' : ''; $('notice').textContent = message; }
function action(id, fn) {
  $(id).addEventListener('click', async () => { const b=$(id); b.disabled=true; try {await fn();} catch(e){notice(e.message,true);} finally {b.disabled=false;} });
}
function agentId() { if (!$('agent').value) throw Error('먼저 Agent를 등록하거나 선택하세요.'); return $('agent').value; }
function tab(name) { for (const [key, desc] of Object.entries(descriptions)) {$(key).hidden=key!==name; if (key===name){$('page-title').textContent=desc[0];$('page-desc').textContent=desc[1];}} document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name)); }
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>$(b.dataset.close).close()));

async function loadAgents(preferred) {
  agents=await api('/agents'); const selected=preferred || $('agent').value || agents[0]?.spec.agent_id;
  $('agent').innerHTML=agents.length ? agents.map(a=>`<option value="${escape(a.spec.agent_id)}">${escape(a.spec.agent_id)}</option>`).join('') : '<option value="">Agent를 등록하세요</option>';
  if (selected) $('agent').value=selected;
  await refresh();
}
async function refresh() {
  const health=await api('/health'); $('phoenix-status').textContent='Phoenix · '+({connected:'연결됨',disabled:'비활성',unavailable:'연결 불가'}[health.phoenix.status] || health.phoenix.status);
  const ev=await api('/evaluators');catalog=ev.catalog;custom=ev.custom;
  if (!$('agent').value) return;
  [analysis,cases,goldens,runs]=await Promise.all([api(`/agents/${agentId()}/analysis`),api(`/agents/${agentId()}/cases`),api('/golden'),api('/runs')]);
  $('framework').textContent=analysis.spec.framework + ' · v' + analysis.spec.version;
  renderGeneration();renderCases();renderVersions();
}
function renderGeneration() {
  $('sources').innerHTML=Object.entries(analysis.counts).map(([key,count])=>`<div class="card"><span class="label">${sourceNames[key]}</span><span class="number">${count}</span><small>${key==='phoenix_failure_candidate'?'관찰된 실패 신호':'Owner 검토 필요'}</small></div>`).join('');
  const spec=analysis.spec;
  $('inventory').innerHTML=[['WORKFLOW NODE',spec.nodes],['조건부 분기',spec.branches],['TOOL 목록',spec.tools.map(t=>t.name)],['RAG 지식 문서',spec.knowledge_sources.map(d=>d.id)],['CAPABILITY',spec.capabilities]].map(([label,values])=>`<div class="inventory-group"><strong>${label}</strong>${values.map(v=>`<span class="badge">${escape(v)}</span>`).join('') || '<small>unknown / 미선언</small>'}</div>`).join('');
  $('failures').innerHTML=`<p class="muted">${analysis.production_trace_count}개 운영 Root Span 수집 · 실패 유형: ${analysis.failure_types.map(t=>escape(failureNames[t] || t)).join(', ') || '관찰된 실패 없음'}</p>`;
  renderCoverage();
}
function renderCoverage() {
  if (!analysis) return;
  const rows=analysis[$('coverage-mode').value];
  $('coverage').innerHTML=rows.map(c=>`<div class="coverage-row"><span>${escape(dimensionNames[c.dimension] || c.dimension)}</span><div class="bar ${c.percent<100?'low':''}"><span></span></div><b>${c.covered} / ${c.total ?? '?'} ${c.percent===null?'':`· ${c.percent}%`}</b><small>${escape(c.basis)}${c.unknown?' · 전체 또는 미래 범위 unknown':''}${c.missing.length?' · 미커버 항목: '+c.missing.map(escape).join(', '):''}</small></div>`).join('');
  $('coverage').querySelectorAll('.bar span').forEach((bar,i)=>{bar.style.width=(rows[i].percent ?? 0)+'%';});
}
// CSP prohibits inline styling; assign the bar widths via DOM style properties instead.
function renderCases() {
  const filtered=cases.filter(c=>($('source-filter').value==='all'||c.source===$('source-filter').value)&&($('status-filter').value==='all'||c.review_status===$('status-filter').value)&&json([c.input,c.trace_id]).toLowerCase().includes($('case-search').value.toLowerCase()));
  $('case-count').textContent=`${filtered.length} / ${cases.length}개 후보`;
  $('case-table').innerHTML=filtered.map(c=>`<tr><td><b>${escape(c.input)}</b><small>기대 응답: ${escape(contractSummary(c))}</small></td><td><span class="badge">${sourceNames[c.source]}</span><small>${escape(c.evidence.join(' · '))}</small><small>생성 신뢰도 ${c.confidence}</small></td><td><small>${escape(c.trace_id || '—')}</small>${c.failure_type?`<span class="pill fail">${escape(failureNames[c.failure_type] || c.failure_type)} · ${escape(c.failure_type)}</span>`:''}<small>${escape(reasonText(c.candidate_reason))}</small></td><td>${c.bindings.map(b=>`<span class="badge">${escape(evaluatorName(b.evaluator_id))} · ${b.role}</span>`).join(' ')||'<small>Owner 평가 계약 필요</small>'}</td><td><span class="pill ${c.review_status}">${reviewNames[c.review_status] || c.review_status}</span><br><button class="secondary edit-button" data-id="${escape(c.id)}">검토</button></td></tr>`).join('') || '<tr><td colspan="5">후보가 없습니다. 평가 후보를 생성하거나 직접 작성하세요.</td></tr>';
  document.querySelectorAll('.edit-button').forEach(b=>b.addEventListener('click',()=>openCase(b.dataset.id)));
}
function renderVersions() {
  const old=$('golden-select').value, previous=$('run-select').value;
  $('golden-select').innerHTML=goldens.filter(g=>g.agent_id===agentId()).sort((a,b)=>b.version-a.version).map(g=>`<option value="${g.id}">Golden v${g.version} · ${g.cases.length}개 사례 · ${g.id.slice(0,8)}</option>`).join('')||'<option value="">먼저 Golden Dataset을 확정하세요</option>';
  if (old && goldens.some(g=>g.id===old&&g.agent_id===agentId())) $('golden-select').value=old;
  const own=runs.filter(r=>r.agent_id===agentId()).reverse();
  $('run-select').innerHTML='<option value="">실행 이력을 선택하세요</option>'+own.map(r=>`<option value="${r.id}">${r.decision} · v${r.dataset_version} · ${runKinds[r.kind] || r.kind} · ${new Date(r.created_at).toLocaleString()}</option>`).join('');
  if (own.some(r=>r.id===previous)) {$('run-select').value=previous;renderRun();} else {$('run-summary').innerHTML='';$('result-details').innerHTML='<p class="muted">실행 이력을 선택하면 평가 근거를 확인할 수 있습니다.</p>';}
}
function openCase(id=null) {
  editing=id?cases.find(c=>c.id===id):null;
  $('case-heading').textContent=editing?'평가 후보 검토':'Owner 사례 직접 작성';
  $('edit-question').value=editing?.input || '';
  $('edit-output').value=editing?.expected.reference_output || '';
  $('edit-contract').value=json(editing?.expected || {expected_status:'ok',max_latency_ms:5000});
  $('edit-status').value=editing?.review_status || 'pending';
  $('case-lineage').textContent=editing?json({source:editing.source,evidence:editing.evidence,confidence:editing.confidence,trace_id:editing.trace_id,span_id:editing.span_id,failure_type:editing.failure_type,candidate_reason:editing.candidate_reason,original_input:editing.original_input,original_output:editing.original_output,error:editing.error,latency_ms:editing.latency_ms}):'Owner 직접 작성';
  $('trace-link').href=analysis?.phoenix.url || 'http://127.0.0.1:6006';$('trace-link').hidden=!editing?.trace_id;
  $('delete-case').hidden=!editing;renderBindings();$('case-dialog').showModal();
}
function renderBindings() {
  $('binding-picker').innerHTML=catalog.map(e=>{const binding=editing?.bindings.find(b=>b.evaluator_id===e.id);return `<div class="binding-row"><label><input type="checkbox" data-evaluator="${escape(e.id)}" ${binding?'checked':''}>${escape(evaluatorName(e.id))} <span class="badge">${e.kind==='custom_llm'?'Owner Custom':'플랫폼 기본'}</span></label><select data-role="${escape(e.id)}"><option value="quality" ${binding?.role==='quality'?'selected':''}>Quality 점수</option><option value="gate" ${binding?.role==='gate'?'selected':''}>Gate 필수 조건</option></select></div>`;}).join('');
}
function bindingsFromPicker() {
  return [...$('binding-picker').querySelectorAll('input:checked')].map(b=>({evaluator_id:b.dataset.evaluator,role:[...$('binding-picker').querySelectorAll('select')].find(s=>s.dataset.role===b.dataset.evaluator).value,scope:'case'}));
}
$('case-form').addEventListener('submit',async event=>{event.preventDefault();try {
  const expected=JSON.parse($('edit-contract').value);expected.reference_output=$('edit-output').value.trim() || null;
  const body={input:$('edit-question').value,expected,bindings:bindingsFromPicker(),review_status:$('edit-status').value};
  if (editing) await api(`/agents/${agentId()}/cases/${editing.id}`,'PATCH',body);
  else {const created=await api(`/agents/${agentId()}/cases`,'POST',body); if(body.review_status!=='pending') await api(`/agents/${agentId()}/cases/${created.id}`,'PATCH',{review_status:body.review_status});}
  $('case-dialog').close();await refresh();notice('검토를 저장했습니다. 기존 Golden 버전은 유지됩니다.');
}catch(e){notice(e.message,true);}});
action('delete-case',async()=>{await api(`/agents/${agentId()}/cases/${editing.id}`,'DELETE');$('case-dialog').close();await refresh();notice('평가 후보를 삭제했습니다. 기존 Golden Snapshot은 유지됩니다.');});
action('manual',()=>openCase());
action('register',async()=>{const record=await api('/agents','POST',{path:$('repo-path').value});await loadAgents(record.spec.agent_id);notice(record.spec.framework+' Adapter로 Agent를 등록했습니다.');});
action('generate',async()=>{await api(`/agents/${agentId()}/generate`,'POST',{});await refresh();notice('평가 후보를 생성했습니다. 생성 근거를 검토한 뒤 Golden Dataset을 확정하세요.');});
action('execute',async()=>{$('execution-output').textContent='Agent 실행 및 Phoenix Trace 전송 중…';const r=await api(`/agents/${agentId()}/execute`,'POST',{input:$('production-query').value});$('execution-output').textContent=json(r);notice('운영 질문을 실행했습니다. 평가 후보 생성으로 Phoenix 관찰 결과를 가져오세요.');});
action('finalize',async()=>{const g=await api(`/agents/${agentId()}/golden`,'POST',{bindings:JSON.parse($('dataset-bindings').value)});await refresh();$('golden-select').value=g.id;tab('results');notice(`검토한 ${g.cases.length}개 사례로 Golden v${g.version}을 확정했습니다.`);});
action('run-evaluation',async()=>{if(!$('golden-select').value) throw Error('먼저 Golden Dataset을 확정하세요.');notice('평가 실행 중입니다. 최초 실행 시 LLM 로딩에 시간이 걸릴 수 있습니다.');const r=await api('/runs','POST',{dataset_id:$('golden-select').value,kind:$('run-kind').value});await refresh();$('run-select').value=r.id;renderRun();notice(`평가 ${r.decision} · 실패 ${r.failure_count}개 사례`);});
function renderRun() {
  const r=runs.find(r=>r.id===$('run-select').value);if(!r)return;
  $('run-summary').innerHTML=[['QUALITY 점수',r.overall_score===null?'N/A':(100*r.overall_score).toFixed(1)+'%', 'Gate 점수 제외'],['GATE 판정',r.decision,r.gate_passed?'필수 Gate 통과':'Gate 실패 → HOLD'],['평가 사례',r.cases.length,`Golden v${r.dataset_version}`],['실패 사례',r.failure_count,'아래에서 평가 이유를 확인하세요']].map(([label,value,sub])=>`<div class="card"><span class="label">${label}</span><span class="number">${value}</span><small>${sub}</small></div>`).join('');
  $('result-details').innerHTML=r.cases.filter(row=>!$('fail-only').checked||!row.passed).map(row=>`<details class="result-case" ${!row.passed?'open':''}><summary><span>${escape(row.case.input)}</span><span class="pill ${row.passed?'pass':'fail'}">${row.passed?'PASS':'FAIL'}</span></summary><div class="compare"><div><h3>기대 응답 / 평가 계약</h3><pre>${escape(json(row.case.expected))}</pre></div><div><h3>실제 응답</h3><pre>${escape(row.actual.output)}</pre><p class="muted">실행 상태: ${escape(row.actual.status)} · ${row.actual.latency_ms.toFixed(1)} ms · ${escape(row.actual.error||'')}</p></div></div><div class="path">실행 경로: ${row.actual.workflow_path.map(escape).join(' → ')}<br>Trace: ${escape(row.actual.trace_id)}<br>원본 실패 Trace: ${escape(row.case.trace_id || '—')}</div><details><summary>Tool 호출 · RAG 검색</summary><pre>${escape(json({tools:row.actual.tool_calls,documents:row.actual.documents,branches:row.actual.branches}))}</pre></details>${row.evaluators.map(e=>`<div class="eval-row"><b>${escape(evaluatorName(e.evaluator_id))}</b> <span class="badge">${e.role}</span> <span class="pill ${e.passed?'pass':'fail'}">${e.passed?'PASS':'FAIL'} · ${e.score.toFixed(3)}</span><small>${escape(e.reason)}</small><details><summary>평가 근거 · Custom Judge 응답</summary><pre>${escape(json(e.details))}</pre></details></div>`).join('')}</details>`).join('')||'<p class="muted">조건에 맞는 평가 사례가 없습니다.</p>';
}

function openJudge() {
  const sample=editing || cases.find(c=>c.source==='rag' && c.expected.reference_output) || cases.find(c=>c.expected.reference_output) || cases[0];
  preview=null;judgeId='owner_'+crypto.randomUUID().replaceAll('-','').slice(0,12);judgeVersion=1;
  $('judge-existing').innerHTML='<option value="">새 Evaluator 만들기</option>'+custom.map(d=>`<option value="${escape(d.id)}">${escape(d.name)} · v${d.version} · ${d.active?'활성':'비활성'}</option>`).join('');
  $('judge-existing').value='';$('judge-name').value='';$('judge-description').value='';$('judge-criteria').value='';$('judge-active').checked=true;
  $('judge-answer').value=sample?.expected.reference_output || sample?.original_output || sample?.expected.reference_context?.[0] || '';
  $('judge-question').value=sample?.input || '';$('judge-register').disabled=true;
  $('judge-dialog').showModal();
}
function judgeDefinition() {return {id:judgeId,name:$('judge-name').value,description:$('judge-description').value,criteria:$('judge-criteria').value,score_min:+$('judge-min').value,score_max:+$('judge-max').value,pass_threshold:+$('judge-threshold').value,scope:$('judge-scope').value,target:$('judge-target').value||null,active:$('judge-active').checked,version:judgeVersion};}
$('judge-form').addEventListener('input',()=>{preview=null;$('judge-register').disabled=true;});
$('judge-existing').addEventListener('change',()=>{const d=custom.find(d=>d.id===$('judge-existing').value);if(!d){judgeId='owner_'+crypto.randomUUID().replaceAll('-','').slice(0,12);judgeVersion=1;return;}judgeId=d.id;judgeVersion=d.version+1;for(const [field,id] of [['name','judge-name'],['description','judge-description'],['criteria','judge-criteria'],['score_min','judge-min'],['score_max','judge-max'],['pass_threshold','judge-threshold'],['scope','judge-scope'],['target','judge-target']])$(id).value=d[field]??'';$('judge-active').checked=d.active;preview=null;$('judge-register').disabled=true;});
action('open-judge',openJudge);action('new-case-judge',openJudge);
action('judge-preview',async()=>{const d=judgeDefinition();$('judge-result').textContent='실제 LLM Judge 실행 중…';preview=await api('/evaluators/preview','POST',{definition:d,case:{input:$('judge-question').value,source:'owner_manual',expected:editing?.expected || {}},answer:$('judge-answer').value});$('judge-result').textContent=json(preview.result);$('judge-register').disabled=false;});
$('judge-form').addEventListener('submit',async event=>{event.preventDefault();try {if(!preview)throw Error('먼저 Sample 평가를 실행하세요.');await api('/evaluators','POST',{definition:judgeDefinition(),preview_id:preview.id});$('judge-dialog').close();await refresh();if($('case-dialog').open)renderBindings();notice('사용자 정의 Evaluator를 등록했습니다. 사례 또는 데이터셋에 연결하세요.');}catch(e){notice(e.message,true);}});
$('agent').addEventListener('change',()=>refresh().catch(e=>notice(e.message,true)));
$('coverage-mode').addEventListener('change',renderCoverage);
for(const id of ['source-filter','status-filter','case-search'])$(id).addEventListener('input',renderCases);
$('run-select').addEventListener('change',renderRun);$('fail-only').addEventListener('change',renderRun);
loadAgents().catch(e=>notice(e.message,true));

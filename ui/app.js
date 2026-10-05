const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const json = value => JSON.stringify(value, null, 2);
let agents = [], cases = [], catalog = [], custom = [], analysis = null, runs = [], goldens = [], editing = null;
let judgeId = '', judgeVersion = 1, preview = null;
const sourceNames = {workflow:'Workflow',rag:'RAG / Knowledge',production_trace:'Production Trace',phoenix_failure_candidate:'Failure Candidate',owner_manual:'Owner Manual'};
const descriptions = {generation:['Generate & Coverage','Discover capabilities. Build a dataset with evidence.'],review:['Owner Review','Turn evidence into versioned evaluation contracts.'],results:['Evaluation Results','Understand quality, failures and deployment gates.']};

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
function agentId() { if (!$('agent').value) throw Error('Register or select an agent first.'); return $('agent').value; }
function tab(name) { for (const [key, desc] of Object.entries(descriptions)) {$(key).hidden=key!==name; if (key===name){$('page-title').textContent=desc[0];$('page-desc').textContent=desc[1];}} document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name)); }
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>$(b.dataset.close).close()));

async function loadAgents(preferred) {
  agents=await api('/agents'); const selected=preferred || $('agent').value || agents[0]?.spec.agent_id;
  $('agent').innerHTML=agents.length ? agents.map(a=>`<option value="${escape(a.spec.agent_id)}">${escape(a.spec.agent_id)}</option>`).join('') : '<option value="">Register an agent</option>';
  if (selected) $('agent').value=selected;
  await refresh();
}
async function refresh() {
  const health=await api('/health'); $('phoenix-status').textContent='Phoenix · '+health.phoenix.status;
  const ev=await api('/evaluators');catalog=ev.catalog;custom=ev.custom;
  if (!$('agent').value) return;
  [analysis,cases,goldens,runs]=await Promise.all([api(`/agents/${agentId()}/analysis`),api(`/agents/${agentId()}/cases`),api('/golden'),api('/runs')]);
  $('framework').textContent=analysis.spec.framework + ' · v' + analysis.spec.version;
  renderGeneration();renderCases();renderVersions();
}
function renderGeneration() {
  $('sources').innerHTML=Object.entries(analysis.counts).map(([key,count])=>`<div class="card"><span class="label">${sourceNames[key]}</span><span class="number">${count}</span><small>${key==='phoenix_failure_candidate'?'Observed failure signals':'Review required'}</small></div>`).join('');
  const spec=analysis.spec;
  $('inventory').innerHTML=[['WORKFLOW NODES',spec.nodes],['CONDITIONAL BRANCHES',spec.branches],['TOOLS',spec.tools.map(t=>t.name)],['RAG KNOWLEDGE',spec.knowledge_sources.map(d=>d.id)],['CAPABILITIES',spec.capabilities]].map(([label,values])=>`<div class="inventory-group"><strong>${label}</strong>${values.map(v=>`<span class="badge">${escape(v)}</span>`).join('') || '<small>Unknown / not declared</small>'}</div>`).join('');
  $('failures').innerHTML=`<p class="muted">${analysis.production_trace_count} production root spans imported · failures: ${analysis.failure_types.map(escape).join(', ') || 'none observed'}</p>`;
  renderCoverage();
}
function renderCoverage() {
  if (!analysis) return;
  const rows=analysis[$('coverage-mode').value];
  $('coverage').innerHTML=rows.map(c=>`<div class="coverage-row"><span>${escape(c.dimension)}</span><div class="bar ${c.percent<100?'low':''}"><span></span></div><b>${c.covered} / ${c.total ?? '?'} ${c.percent===null?'':`· ${c.percent}%`}</b><small>${escape(c.basis)}${c.unknown?' · unknown total / future universe':''}${c.missing.length?' · gaps: '+c.missing.map(escape).join(', '):''}</small></div>`).join('');
  $('coverage').querySelectorAll('.bar span').forEach((bar,i)=>{bar.style.width=(rows[i].percent ?? 0)+'%';});
}
// CSP prohibits inline styling; assign the bar widths via DOM style properties instead.
function renderCases() {
  const filtered=cases.filter(c=>($('source-filter').value==='all'||c.source===$('source-filter').value)&&($('status-filter').value==='all'||c.review_status===$('status-filter').value)&&json([c.input,c.trace_id]).toLowerCase().includes($('case-search').value.toLowerCase()));
  $('case-count').textContent=`${filtered.length} / ${cases.length} candidates`;
  $('case-table').innerHTML=filtered.map(c=>`<tr><td><b>${escape(c.input)}</b><small>Expected: ${escape(c.expected.reference_output ?? json(c.expected))}</small></td><td><span class="badge">${sourceNames[c.source]}</span><small>${escape(c.evidence.join(' · '))}</small><small>Confidence ${c.confidence}</small></td><td><small>${escape(c.trace_id || '—')}</small>${c.failure_type?`<span class="pill fail">${escape(c.failure_type)}</span>`:''}<small>${escape(c.candidate_reason)}</small></td><td>${c.bindings.map(b=>`<span class="badge">${escape(b.evaluator_id)} · ${b.role}</span>`).join(' ')||'<small>Owner contract required</small>'}</td><td><span class="pill ${c.review_status}">${c.review_status}</span><br><button class="secondary edit-button" data-id="${escape(c.id)}">Review</button></td></tr>`).join('') || '<tr><td colspan="5">No candidates. Generate or add an owner case.</td></tr>';
  document.querySelectorAll('.edit-button').forEach(b=>b.addEventListener('click',()=>openCase(b.dataset.id)));
}
function renderVersions() {
  const old=$('golden-select').value, previous=$('run-select').value;
  $('golden-select').innerHTML=goldens.filter(g=>g.agent_id===agentId()).map(g=>`<option value="${g.id}">Golden v${g.version} · ${g.cases.length} cases · ${g.id.slice(0,8)}</option>`).join('')||'<option value="">Finalize a golden dataset first</option>';
  if (old && goldens.some(g=>g.id===old&&g.agent_id===agentId())) $('golden-select').value=old;
  const own=runs.filter(r=>r.agent_id===agentId()).reverse();
  $('run-select').innerHTML='<option value="">Select a run</option>'+own.map(r=>`<option value="${r.id}">${r.decision} · v${r.dataset_version} · ${r.kind} · ${new Date(r.created_at).toLocaleString()}</option>`).join('');
  if (own.some(r=>r.id===previous)) {$('run-select').value=previous;renderRun();} else {$('run-summary').innerHTML='';$('result-details').innerHTML='<p class="muted">Select a run to see its evidence.</p>';}
}
function openCase(id=null) {
  editing=id?cases.find(c=>c.id===id):null;
  $('case-heading').textContent=editing?'Review candidate':'Add owner case';
  $('edit-question').value=editing?.input || '';
  $('edit-output').value=editing?.expected.reference_output || '';
  $('edit-contract').value=json(editing?.expected || {expected_status:'ok',max_latency_ms:5000});
  $('edit-status').value=editing?.review_status || 'pending';
  $('case-lineage').textContent=editing?json({source:editing.source,evidence:editing.evidence,confidence:editing.confidence,trace_id:editing.trace_id,span_id:editing.span_id,failure_type:editing.failure_type,candidate_reason:editing.candidate_reason,original_input:editing.original_input,original_output:editing.original_output,error:editing.error,latency_ms:editing.latency_ms}):'Owner manual input';
  $('trace-link').href=analysis?.phoenix.url || 'http://127.0.0.1:6006';$('trace-link').hidden=!editing?.trace_id;
  $('delete-case').hidden=!editing;renderBindings();$('case-dialog').showModal();
}
function renderBindings() {
  $('binding-picker').innerHTML=catalog.map(e=>{const binding=editing?.bindings.find(b=>b.evaluator_id===e.id);return `<div class="binding-row"><label><input type="checkbox" data-evaluator="${escape(e.id)}" ${binding?'checked':''}>${escape(e.id)} <span class="badge">${e.kind}</span></label><select data-role="${escape(e.id)}"><option value="quality" ${binding?.role==='quality'?'selected':''}>Quality</option><option value="gate" ${binding?.role==='gate'?'selected':''}>Gate</option></select></div>`;}).join('');
}
function bindingsFromPicker() {
  return [...$('binding-picker').querySelectorAll('input:checked')].map(b=>({evaluator_id:b.dataset.evaluator,role:[...$('binding-picker').querySelectorAll('select')].find(s=>s.dataset.role===b.dataset.evaluator).value,scope:'case'}));
}
$('case-form').addEventListener('submit',async event=>{event.preventDefault();try {
  const expected=JSON.parse($('edit-contract').value);expected.reference_output=$('edit-output').value.trim() || null;
  const body={input:$('edit-question').value,expected,bindings:bindingsFromPicker(),review_status:$('edit-status').value};
  if (editing) await api(`/agents/${agentId()}/cases/${editing.id}`,'PATCH',body);
  else {const created=await api(`/agents/${agentId()}/cases`,'POST',body); if(body.review_status!=='pending') await api(`/agents/${agentId()}/cases/${created.id}`,'PATCH',{review_status:body.review_status});}
  $('case-dialog').close();await refresh();notice('Review saved. Golden versions stay immutable.');
}catch(e){notice(e.message,true);}});
action('delete-case',async()=>{await api(`/agents/${agentId()}/cases/${editing.id}`,'DELETE');$('case-dialog').close();await refresh();notice('Candidate deleted; existing golden snapshots preserved.');});
action('manual',()=>openCase());
action('register',async()=>{const record=await api('/agents','POST',{path:$('repo-path').value});await loadAgents(record.spec.agent_id);notice('Agent registered through '+record.spec.framework+' adapter.');});
action('generate',async()=>{await api(`/agents/${agentId()}/generate`,'POST',{});await refresh();notice('Candidates generated. Review their evidence before finalizing.');});
action('execute',async()=>{$('execution-output').textContent='Executing and exporting Phoenix trace…';const r=await api(`/agents/${agentId()}/execute`,'POST',{input:$('production-query').value});$('execution-output').textContent=json(r);notice('Production request complete. Generate candidates to import Phoenix observations.');});
action('finalize',async()=>{const g=await api(`/agents/${agentId()}/golden`,'POST',{bindings:JSON.parse($('dataset-bindings').value)});await refresh();$('golden-select').value=g.id;tab('results');notice(`Golden v${g.version} finalized with ${g.cases.length} reviewed cases.`);});
action('run-evaluation',async()=>{if(!$('golden-select').value) throw Error('Finalize a golden dataset first.');notice('Evaluation running. LLM loading may take a moment on first use.');const r=await api('/runs','POST',{dataset_id:$('golden-select').value,kind:$('run-kind').value});await refresh();$('run-select').value=r.id;renderRun();notice(`Evaluation ${r.decision}. ${r.failure_count} failed cases.`);});
function renderRun() {
  const r=runs.find(r=>r.id===$('run-select').value);if(!r)return;
  $('run-summary').innerHTML=[['QUALITY SCORE',r.overall_score===null?'N/A':(100*r.overall_score).toFixed(1)+'%', 'Gate scores excluded'],['DEPLOYMENT',r.decision,r.gate_passed?'Required gates passed':'Gate failure → HOLD'],['TEST CASES',r.cases.length,`Golden v${r.dataset_version}`],['FAILED CASES',r.failure_count,'Inspect evaluator reasons below']].map(([label,value,sub])=>`<div class="card"><span class="label">${label}</span><span class="number">${value}</span><small>${sub}</small></div>`).join('');
  $('result-details').innerHTML=r.cases.filter(row=>!$('fail-only').checked||!row.passed).map(row=>`<details class="result-case" ${!row.passed?'open':''}><summary><span>${escape(row.case.input)}</span><span class="pill ${row.passed?'pass':'fail'}">${row.passed?'PASS':'FAIL'}</span></summary><div class="compare"><div><h3>EXPECTED CONTRACT</h3><pre>${escape(json(row.case.expected))}</pre></div><div><h3>ACTUAL RESPONSE</h3><pre>${escape(row.actual.output)}</pre><p class="muted">Status: ${escape(row.actual.status)} · ${row.actual.latency_ms.toFixed(1)} ms · ${escape(row.actual.error||'')}</p></div></div><div class="path">Path: ${row.actual.workflow_path.map(escape).join(' → ')}<br>Trace: ${escape(row.actual.trace_id)}<br>Original failure trace: ${escape(row.case.trace_id || '—')}</div><details><summary>Tool calls & RAG retrieval</summary><pre>${escape(json({tools:row.actual.tool_calls,documents:row.actual.documents,branches:row.actual.branches}))}</pre></details>${row.evaluators.map(e=>`<div class="eval-row"><b>${escape(e.evaluator_id)}</b> <span class="badge">${e.role}</span> <span class="pill ${e.passed?'pass':'fail'}">${e.passed?'PASS':'FAIL'} · ${e.score.toFixed(3)}</span><small>${escape(e.reason)}</small><details><summary>Evaluator evidence / custom judge output</summary><pre>${escape(json(e.details))}</pre></details></div>`).join('')}</details>`).join('')||'<p class="muted">No cases match this filter.</p>';
}

function openJudge() {
  preview=null;judgeId='owner_'+crypto.randomUUID().replaceAll('-','').slice(0,12);judgeVersion=1;
  $('judge-existing').innerHTML='<option value="">Create new evaluator</option>'+custom.map(d=>`<option value="${escape(d.id)}">${escape(d.name)} · v${d.version} · ${d.active?'active':'inactive'}</option>`).join('');
  $('judge-existing').value='';$('judge-name').value='';$('judge-description').value='';$('judge-criteria').value='';$('judge-active').checked=true;
  $('judge-answer').value=editing?.expected.reference_output || editing?.original_output || 'Apply for leave at least 3 days in advance using the HR portal. Attach a manager approval document.';
  $('judge-question').value=editing?.input || 'What is the leave policy?';$('judge-register').disabled=true;
  $('judge-dialog').showModal();
}
function judgeDefinition() {return {id:judgeId,name:$('judge-name').value,description:$('judge-description').value,criteria:$('judge-criteria').value,score_min:+$('judge-min').value,score_max:+$('judge-max').value,pass_threshold:+$('judge-threshold').value,scope:$('judge-scope').value,target:$('judge-target').value||null,active:$('judge-active').checked,version:judgeVersion};}
$('judge-form').addEventListener('input',()=>{preview=null;$('judge-register').disabled=true;});
$('judge-existing').addEventListener('change',()=>{const d=custom.find(d=>d.id===$('judge-existing').value);if(!d){judgeId='owner_'+crypto.randomUUID().replaceAll('-','').slice(0,12);judgeVersion=1;return;}judgeId=d.id;judgeVersion=d.version+1;for(const [field,id] of [['name','judge-name'],['description','judge-description'],['criteria','judge-criteria'],['score_min','judge-min'],['score_max','judge-max'],['pass_threshold','judge-threshold'],['scope','judge-scope'],['target','judge-target']])$(id).value=d[field]??'';$('judge-active').checked=d.active;preview=null;$('judge-register').disabled=true;});
action('open-judge',openJudge);action('new-case-judge',openJudge);
action('judge-preview',async()=>{const d=judgeDefinition();$('judge-result').textContent='Running actual LLM judge…';preview=await api('/evaluators/preview','POST',{definition:d,case:{input:$('judge-question').value,source:'owner_manual',expected:editing?.expected || {}},answer:$('judge-answer').value});$('judge-result').textContent=json(preview.result);$('judge-register').disabled=false;});
$('judge-form').addEventListener('submit',async event=>{event.preventDefault();try {if(!preview)throw Error('Run a sample first.');await api('/evaluators','POST',{definition:judgeDefinition(),preview_id:preview.id});$('judge-dialog').close();await refresh();if($('case-dialog').open)renderBindings();notice('Custom evaluator registered. Select it in a case or dataset binding.');}catch(e){notice(e.message,true);}});
$('agent').addEventListener('change',()=>refresh().catch(e=>notice(e.message,true)));
$('coverage-mode').addEventListener('change',renderCoverage);
for(const id of ['source-filter','status-filter','case-search'])$(id).addEventListener('input',renderCases);
$('run-select').addEventListener('change',renderRun);$('fail-only').addEventListener('change',renderRun);
loadAgents().catch(e=>notice(e.message,true));

// Real browser interaction against the running platform; no route mocking.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.EVAL_URL || 'http://127.0.0.1:8000';
const run = async () => {
  const browser = await chromium.launch({headless:true, channel: process.env.BROWSER_CHANNEL || 'msedge'});
  const page = await browser.newPage({viewport:{width:1440,height:1080}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const nonce=Date.now().toString();
  try {
    await page.goto(base);
    await page.locator('#agent').selectOption('hr-langgraph');
    await page.waitForFunction(()=>document.querySelector('#framework').textContent.includes('langgraph'));
    await page.locator('#generate').click();
    await page.getByRole('status').filter({hasText:'Candidates generated'}).waitFor();
    assert(await page.locator('#sources .card').count()===5);
    fs.mkdirSync('artifacts/ui',{recursive:true});
    await page.screenshot({path:'artifacts/ui/01-generation.png',fullPage:true});
    await page.locator('[data-tab="review"]').click();
    await page.locator('#source-filter').selectOption('phoenix_failure_candidate');
    await page.locator('#case-search').fill('balance error');
    const failureRow=page.locator('#case-table tr').filter({hasText:'tool_failure'}).first();
    await failureRow.locator('button').click();
    await page.locator('#case-lineage').filter({hasText:'tool_failure'}).waitFor();
    assert((await page.locator('#case-lineage').textContent()).includes('trace_id'));
    await page.locator('#edit-contract').fill(JSON.stringify({expected_status:'ok',required_output:['Available leave']}));
    await page.locator('#edit-output').fill('');
    await page.locator('#edit-status').selectOption('approved');
    await page.getByRole('button',{name:'Save Review',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('#case-dialog').open);
    await page.locator('#source-filter').selectOption('all');
    await page.locator('#case-search').fill('');
    await page.locator('#manual').click();
    await page.locator('#edit-question').fill('Hello');
    await page.locator('#edit-output').fill('I can help with leave policy and leave balance.');
    await page.locator('#edit-status').selectOption('approved');
    await page.getByRole('button',{name:'Save Review',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('#case-dialog').open);
    // Custom creation sample → register → attach to a specific case, twice.
    const customIds=[];
    for(let index=1;index<=2;index++) {
      await page.locator('#open-judge').click();
      await page.locator('#judge-name').fill(`Browser Judge ${index} ${nonce}`);
      await page.locator('#judge-criteria').fill(index===1?'The answer must mention the HR portal.':'The answer must mention a manager approval document.');
      await page.locator('#judge-preview').click();
      await page.waitForFunction(()=>!document.querySelector('#judge-register').disabled,{},{timeout:120000});
      assert((await page.locator('#judge-result').textContent()).includes('raw_response'));
      await page.locator('#judge-register').click();
      await page.waitForFunction(()=>!document.querySelector('#judge-dialog').open);
      const definitions=await (await page.request.get(base+'/api/evaluators')).json();
      customIds.push(definitions.custom.find(d=>d.name===`Browser Judge ${index} ${nonce}`).id);
    }
    await page.locator('#source-filter').selectOption('workflow');
    await page.locator('#case-search').fill('What is the leave policy?');
    await page.locator('#case-table .edit-button').first().click();
    for(const id of customIds) await page.locator(`input[data-evaluator="${id}"]`).check();
    await page.locator('#edit-status').selectOption('approved');
    await page.getByRole('button',{name:'Save Review',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('#case-dialog').open);
    await page.locator('#source-filter').selectOption('all');await page.locator('#case-search').fill('');
    await page.screenshot({path:'artifacts/ui/02-review.png',fullPage:true});
    await page.locator('#finalize').click();
    await page.waitForFunction(()=>!document.querySelector('#results').hidden);
    await page.locator('#run-evaluation').click();
    await page.waitForFunction(()=>document.querySelector('#run-summary').textContent.includes('HOLD'),{},{timeout:120000});
    assert((await page.locator('#result-details').textContent()).includes('error_detection'));
    assert((await page.locator('#result-details').textContent()).includes(customIds[1]));
    await page.screenshot({path:'artifacts/ui/03-results.png',fullPage:true});
    const history=await (await page.request.get(base+'/api/runs')).json();
    const latest=history.at(-1);
    assert(latest.cases.some(c=>c.case.source==='phoenix_failure_candidate'&&c.case.trace_id&&!c.passed));
    assert.equal(errors.length,0,errors.join('\n'));
    fs.writeFileSync('artifacts/ui/report.json',JSON.stringify({status:'passed',run_id:latest.id,decision:latest.decision,custom_evaluators:customIds,screenshots:3,page_errors:errors},null,2));
    console.log('Browser E2E passed:',latest.id,latest.decision);
  } finally {await browser.close();}
};
run().catch(e=>{console.error(e);process.exitCode=1;});

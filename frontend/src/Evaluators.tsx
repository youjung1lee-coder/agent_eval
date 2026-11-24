import { useState } from "react";
import { api, Badge, Json, Props, Row, Tree, val, PageList } from "./common";
import { RuleEditor, SpanTree } from "./RuleEditor";
export function Evaluators({
  state,
  version,
  samples,
  refresh,
  act,
  busy,
}: Props) {
  const [model, Model] = useState(""),
    [timeout, Timeout] = useState(60),
    [q, Q] = useState(""),
    [filters, F] = useState<Row>({}),
    [key, K] = useState(""),
    [id, I] = useState(""),
    [name, N] = useState(""),
    [desc, D] = useState(""),
    [threshold, T] = useState(0.5),
    [rules, R] = useState("{}"),
    [variable, V] = useState(""),
    [result, O] = useState<Row | null>(null),
    [query, H] = useState(""),
    [family, Y] = useState(""),
    [prompt, P] = useState("{{input}}\n{{actual_output}}"),
    [rubric, U] = useState("응답의 정확성과 관련성"),
    [schema,Schema] = useState("number"), [cats,Cats] = useState('{"pass":1,"fail":0}'),[retries,Retry]=useState(0),[temp, E] = useState(0),
    [saved, S] = useState(""),
    [traceFilter, Z] = useState(false);
  const m = state.metrics.find((x: Row) => x.metric_id === key),
    sample = samples.find((x) => x.id === id) || samples[0];
  async function select(metric: Row, existing?: Row) {
    const sp = existing?.definition.spec;
    K(metric.metric_id);
    Schema(sp?.score_type||"number");Cats(JSON.stringify(sp?.categories||{pass:1,fail:0}));Retry(sp?.retries||0);
    Model(sp?.model || "");
    Timeout(sp?.timeout || 60);
    N(sp?.name || metric.display_name);
    D(sp?.description || "");
    T(sp?.threshold ?? 0.5);
    P(sp?.prompt || "{{input}}\n{{actual_output}}");
    U(sp?.rubric || "응답의 정확성과 관련성");
    E(sp?.temperature || 0);
    V(metric.required_inputs[0]);
    Y(existing?.definition.family || "");
    O(null);
    S("");
    R(
      JSON.stringify(
        existing?.rules ||
          (sample
            ? await api("/recommend/" + sample.id + "/" + metric.metric_id)
            : {}),
        null,
        2,
      ),
    );
  }
  function setRule(v: Row) {
    const parsed = JSON.parse(rules);
    R(JSON.stringify({ ...parsed, [variable]: v }, null, 2));
    O(null);
  }
  async function action(a: string) {
    const body = {
      version,
      sample: sample.id,
      spec: {
        name,
        description: desc,
        metric: key,
        threshold,
        model,
        timeout,
        prompt,
        rubric,
        temperature: temp, score_type:schema,categories:JSON.parse(cats),retries,
      },
      rules: JSON.parse(rules),
      family: family || null,
    };
    const r = await api("/mapping/" + a, body);
    O(r);
    if (a === "publish") {
      await refresh();
      S("Evaluator와 매핑 버전을 발행했습니다.");
    }
  }
  return (
    <>
      <div className="heading">
        <div>
          <div className="eyebrow">EVALUATORS</div>
          <h1>평가함수 관리</h1>
          <p>평가 지표를 선택하고 실제 케이스로 입력 매핑을 검증하세요.</p>
        </div>
      </div>
      <section>
        <header>
          <h2>평가함수 카탈로그</h2>
          <input
            className="search"
            placeholder="이름 또는 설명 검색"
            value={q}
            onChange={(e) => Q(e.target.value)}
          />
        </header>
        <div className="line">
          {Object.entries({
            provider: ["엔진", "DeepEval", "Ragas", "Custom"],
            category: ["범주", "Task", "Tool", "RAG", "General", "Workflow"],
            scope: ["단위", "응답", "Trace", "Session"],
            model: ["모델", "결정론적", "LLM"],
            expected: ["기대값", "필요", "선택"],
            available: ["실행 상태", "사용 가능", "설정 필요"],
            input: ["샘플 입력", "필수값 보유", "누락 있음"],
          }).map(([k, [title, ...options]]) => (
            <select
              aria-label={title}
              key={k}
              value={filters[k] || ""}
              onChange={(e) => F({ ...filters, [k]: e.target.value })}
            >
              <option value="">{title} 전체</option>
              {options.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          ))}
        </div>
        <div className="cards">
          {state.metrics
            .filter((x: Row) => {
              const meta: Row = {
                ...x,
                model: x.model_requirement ? "LLM" : "결정론적",
                expected: x.required_inputs.some((a: string) =>
                  a.startsWith("expected"),
                )
                  ? "필요"
                  : "선택",
                available: x.available ? "사용 가능" : "설정 필요",
                input: x.required_inputs.every(
                  (k: string) =>
                    ["value", "minimum"].includes(k) ||
                    Boolean(sample?.record[k]?.length ?? sample?.record[k]),
                )
                  ? "필수값 보유"
                  : "누락 있음",
              };
              return (
                (x.display_name + x.description)
                  .toLowerCase()
                  .includes(q.toLowerCase()) &&
                Object.entries(filters).every(([k, v]) => !v || meta[k] === v)
              );
            })
            .map((x: Row) => (
              <article key={x.metric_id}>
                <Badge>{x.provider}</Badge>
                <h3>{x.display_name}</h3>
                <p>{x.description}</p>
                <small>
                  {x.scope} · {x.score_schema} ·{" "}
                  {x.available ? "사용 가능" : "설정 필요"}
                </small>
                <small>{x.required_inputs.join(" · ")}</small>
                <a href={x.docs} target="_blank" rel="noreferrer">
                  문서 ↗
                </a>{" "}
                <button disabled={busy} onClick={() => act(() => select(x))}>
                  선택 / 설정
                </button>
              </article>
            ))}
        </div>
      </section>
      <section>
        <header>
          <h2>발행된 Evaluator</h2>
        </header>
        {state.mappings.map((x: Row) => (
          <button
            key={x.id}
            className="chip"
            onClick={() =>
              act(() =>
                select(
                  state.metrics.find(
                    (y: Row) => y.metric_id === x.definition.spec.metric,
                  ),
                  x,
                ),
              )
            }
          >
            {x.definition.spec.name} · v{x.definition.number} /{" "}
            {x.id.slice(0, 5)}
          </button>
        ))}
      </section>
      {m && (
        <div className="split">
          <section>
            <h2>Evaluator 정의</h2>
            <label>
              이름
              <input value={name} onChange={(e) => N(e.target.value)} />
            </label>
            <label>
              설명
              <input value={desc} onChange={(e) => D(e.target.value)} />
            </label>
            <label>
              통과 기준
              <input
                type="number"
                min="0"
                max="1"
                step=".05"
                value={threshold}
                onChange={(e) => T(+e.target.value)}
              />
            </label>
            {m.model_requirement && (
              <>
                <label>
                  Judge 모델
                  <input
                    placeholder="서버 기본 모델"
                    value={model}
                    onChange={(e) => Model(e.target.value)}
                  />
                </label>
                <label>
                  통신 오류 재시도 횟수<input type="number" min="0" max="2" value={retries} onChange={e=>Retry(+e.target.value)}/></label><label>제한 시간(초)
                  <input
                    type="number"
                    min="1"
                    max="120"
                    value={timeout}
                    onChange={(e) => Timeout(+e.target.value)}
                  />
                </label>
              </>
            )}
            {key === "judge" && (
              <>
                <label>
                  점수 형식<select value={schema} onChange={e=>Schema(e.target.value)}>{["number","boolean","category"].map(x=><option key={x}>{x}</option>)}</select></label>{schema==="category"&&<label>범주별 점수 JSON<input value={cats} onChange={e=>Cats(e.target.value)}/></label>}<label>
                  Judge prompt
                  <textarea
                    value={prompt}
                    onChange={(e) => P(e.target.value)}
                  />
                </label>
                <label>
                  Rubric
                  <textarea
                    value={rubric}
                    onChange={(e) => U(e.target.value)}
                  />
                </label>
                <label>
                  온도
                  <input
                    type="number"
                    value={temp}
                    onChange={(e) => E(+e.target.value)}
                  />
                </label>
              </>
            )}
            <label>
              매핑할 입력 변수
              <select value={variable} onChange={(e) => V(e.target.value)}>
                {[...new Set<string>([...m.required_inputs,...(key==="judge"?Array.from(prompt.matchAll(/\{\{(\w+)\}\}/g),m=>m[1]):[])])].map((k: string) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </label>
            <RuleEditor
              apply={(r) =>
                act(async () =>
                  setRule(
                    "literal" in r
                      ? { fixed: JSON.parse(r.literal) }
                      : "attrs" in r
                        ? {
                            path: r.path,
                            policy: r.policy,
                            selector: {
                              kind: r.kind,
                              name_contains: r.contains,
                              attributes: JSON.parse(r.attrs),
                            },
                          }
                        : r,
                  ),
                )
              }
            />
            <label>
              입력 매핑 JSON
              <textarea
                rows={10}
                value={rules}
                onChange={(e) => {
                  R(e.target.value);
                  O(null);
                }}
              />
            </label>
            <details>
              <summary>경로 · 선택 정책 도움말</summary>
              <Json
                value={[
                  { path: "/expected_output" },
                  { fixed: 1 },
                  { join: ["/input/text", "/actual_output/text"] },
                  {
                    selector: {
                      kind: "RETRIEVER",
                      attributes: { operation: "search" },
                    },
                    policy: "first",
                    path: "/attributes/documents",
                  },
                ]}
              />
              <p>
                추천은 같은 이름의 공통 필드를 사용합니다. 미리보기에서 실제
                경로와 타입을 확인하세요. first/last는 순서에 의존합니다.
              </p>
            </details>
            <div className="line">
              {[
                ["preview", "매핑 미리보기"],
                ["validate", "전체 검증"],
                ["test", "시험 평가"],
                ["publish", "버전 발행"],
              ].map(([a, t]) => (
                <button
                  disabled={!sample || busy || !name.trim()}
                  key={a}
                  onClick={() => act(() => action(a))}
                >
                  {t}
                </button>
              ))}
            </div>
            {saved && <p>{saved}</p>}
            {result && (
              <>
                <h3>검증 결과</h3>
                {result.total !== undefined && (
                  <Badge>
                    {result.valid} / {result.total}건 매핑 성공
                  </Badge>
                )}
                <Json value={result} />
              </>
            )}
          </section>
          <section>
            <h2>샘플 Trace</h2>
            <input
              placeholder="Trace 질문 검색"
              value={query}
              onChange={(e) => H(e.target.value)}
            />
            <label>
              <input
                type="checkbox"
                checked={traceFilter}
                onChange={(e) => Z(e.target.checked)}
              />{" "}
              Trace 연결 항목만
            </label>
            <PageList
              items={samples.filter(
                (x) =>
                  val(x.data.input).includes(query) &&
                  (!traceFilter || x.record.trace.spans.length),
              )}
              render={(x) => (
                <button
                  className={"pick " + (sample?.id === x.id ? "active" : "")}
                  onClick={() => {
                    I(x.id);
                    O(null);
                  }}
                >
                  {val(x.data.input)}
                </button>
              )}
            />
            {sample && (
              <>
                <h3>{val(sample.data.input)}</h3>
                <p>필드를 펼쳐 {variable}에 연결하세요.</p>
                <details>
                  <summary>Span 계층 구조</summary>
                  <SpanTree
                    spans={sample.record.trace?.spans || []}
                    pick={(p) => act(async () => setRule({ path: p }))}
                  />
                </details>
                <Tree
                  node={sample.record}
                  pick={(p) => act(async () => setRule({ path: p }))}
                />
              </>
            )}
          </section>
        </div>
      )}
    </>
  );
}

import { useEffect, useState } from "react";
import { api, Badge, Json, Props, Row, val, date, PageList } from "./common";
import { resultMatches } from "./model.js";
export function Results({
  state,
  version,
  samples,
  refresh,
  act,
  busy,
}: Props) {
  const [baseline, Base] = useState(""),
    [preflight, Pre] = useState<Row | null>(null),
    [mode, M] = useState("historical"),
    [env, E] = useState("STG"),
    [name, N] = useState("평가 실험"),
    [ids, S] = useState<string[]>([]),
    [id, I] = useState(""),
    [exp, X] = useState<Row | null>(null),
    [a, A] = useState(""),
    [b, B] = useState(""),
    [cmp, C] = useState<Row | null>(null),
    [filter, F] = useState(""),
    [selected, J] = useState<Row | null>(null),
    [error, Err] = useState(""),
    [reg, R] = useState(false),
    [setup, U] = useState(false);
  const runs = state.experiments as Row[],
    ds = state.datasets.find((d: Row) =>
      d.versions.some((v: Row) => v.id === version),
    ),
    maps = state.mappings.filter((x: Row) => x.agent === ds?.agent);
  useEffect(() => {
    if (!id) return;
    let live = true,
      t: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const r = await api("/experiments/" + id);
        if (!live) return;
        X(r);
        Err("");
        if (["QUEUED", "RUNNING"].includes(r.status))
          t = setTimeout(poll, 1000);
        else await refresh();
      } catch (e) {
        if (live) {
          Err(String(e));
          t = setTimeout(poll, 3000);
        }
      }
    }
    poll();
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [id]);
  function inspect(k: string) {
    J(null);
    I(k);
    if (k === id) act(async () => X(await api("/experiments/" + id)));
  }
  const mname = (k: string) =>
    state.mappings.find((m: Row) => m.id === k)?.definition.spec.name ||
    k.slice(0, 8);
  async function control(action: string, job?: string) {
    await api(
      "/experiments/" + id + "/" + action + (job ? "?job=" + job : ""),
      {},
    );
    I("");
    setTimeout(() => I(id), 0);
  }
  return (
    <>
      <div className="heading">
        <div>
          <div className="eyebrow">EXPERIMENTS</div>
          <h1>평가결과 관리</h1>
          <p>실험을 실행하고 케이스별 변화와 회귀를 확인하세요.</p>
        </div>
        <button className="primary" onClick={() => U(!setup)}>
          ＋　평가 실행
        </button>
      </div>
      {setup && (
        <section>
          <h2>실험 설정</h2>
          <div className="line">
            <label>
              평가 방식
              <select value={mode} onChange={(e) => M(e.target.value)}>
                <option value="historical">기존 결과 평가</option>
                <option value="single">신규 실행 평가</option>
                <option value="ab">A/B 비교 평가</option>
              </select>
            </label>
            <label>
              실험 이름
              <input value={name} onChange={(e) => N(e.target.value)} />
            </label>
            {mode === "historical" && (
              <label>
                기존 실행 세트
                <select value={baseline} onChange={(e) => Base(e.target.value)}>
                  <option value="">가져온 Phoenix Trace</option>
                  {runs
                    .filter((r) => r.version === version && r.status === "DONE")
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                </select>
              </label>
            )}
            {mode === "single" && (
              <label>
                환경
                <select value={env} onChange={(e) => E(e.target.value)}>
                  <option>STG</option>
                  <option>PRD</option>
                </select>
              </label>
            )}
          </div>
          <p>
            {ds?.name} · {ds?.agent} · {samples.length}건 · Agent 호출{" "}
            {mode === "historical"
              ? 0
              : samples.length * (mode === "ab" ? 2 : 1)}
            회
          </p>
          {mode === "historical" ? (
            <p>
              기존 Trace를 사용합니다. 모델 기반 지표는 Judge 호출 비용이 발생할
              수 있습니다.
            </p>
          ) : (
            <p>
              Agent 모드 {state.agent_mode} · 실제 PRD 호출 차단 · 외부 상태와
              시점에 따라 결과가 달라질 수 있습니다.
            </p>
          )}
          {maps.map((m: Row) => (
            <label key={m.id}>
              <input
                type="checkbox"
                checked={ids.includes(m.id)}
                onChange={(e) =>
                  S(
                    e.target.checked
                      ? [...ids, m.id]
                      : ids.filter((x) => x !== m.id),
                  )
                }
              />{" "}
              {m.definition.spec.name} · v{m.definition.number} /{" "}
              {m.id.slice(0, 5)}
            </label>
          ))}
          <button
            disabled={!ids.length || busy}
            onClick={() =>
              act(async () =>
                Pre(
                  await api("/preflight", {
                    version,
                    mode,
                    environment: env,
                    name,
                    selection: ids,
                    request_id: "preview",
                  }),
                ),
              )
            }
          >
            실행 전 매핑 검증
          </button>
          {preflight && <Json value={preflight} />}
          <button
            className="primary"
            disabled={!ids.length || !name.trim() || busy}
            onClick={() =>
              act(async () => {
                const r = await api("/experiments", {
                  version,
                  mode,
                  environment: env,
                  name,
                  selection: ids,
                  baseline: mode === "historical" ? baseline || null : null,
                  request_id: crypto.randomUUID(),
                });
                await refresh();
                inspect(r.id);
                if (r.baseline) {
                  A(r.baseline);
                  B(r.id);
                }
                U(false);
              })
            }
          >
            실험 시작
          </button>
        </section>
      )}
      <section>
        <header>
          <h2>실험 이력</h2>
          <button onClick={() => act(refresh)}>새로고침</button>
        </header>
        <PageList
          items={runs}
          render={(r) => (
            <button className="row" onClick={() => inspect(r.id)}>
              <span>
                <strong>{r.name}</strong>
                <small>
                  {r.environment} · {r.mode} · {r.agent} · Dataset{" "}
                  {r.version.slice(0, 6)} · {date(r.created)}
                </small>
              </span>
              <Badge>{r.status}</Badge>
            </button>
          )}
        />
      </section>
      {error && <p role="alert">{error}</p>}
      {exp && (
        <section>
          <header>
            <h2>{exp.name}</h2>
            <Badge>{exp.status}</Badge>
          </header>
          <p>
            처리 {exp.summary.finished} / {exp.summary.count}건　 평균{" "}
            {exp.summary.mean?.toFixed(3) ?? "—"}　 통과율{" "}
            {exp.summary.pass_rate == null
              ? "—"
              : (exp.summary.pass_rate * 100).toFixed(1) + "%"}
          </p>
          <small>
            평균과 통과율의 분모는 점수가 있는 평가 {exp.summary.scored}
            건입니다.
          </small>
          <div className="line">
            {Object.entries(exp.summary.statuses).map(([k, v]) => (
              <Badge key={k}>
                {k} {String(v)}
              </Badge>
            ))}
            <button
              disabled={busy}
              onClick={() => act(() => control("cancel"))}
            >
              대기 건 취소
            </button>
            <button disabled={busy} onClick={() => act(() => control("retry"))}>
              오류 재시도
            </button>
          </div>
          <details>
            <summary>지표별 집계 · 점수 분포</summary>
            <p>
              평균 Agent 지연 시간{" "}
              {exp.summary.agent_mean_latency_ms?.toFixed(0) ?? "—"} ms
            </p>
            <Json value={exp.summary.distribution} />
            {Object.entries(exp.summary.metric_means).map(([k, v]) => (
              <p key={k}>
                {mname(k)} · {Number(v).toFixed(3)}
              </p>
            ))}
          </details>
          <select
            aria-label="결과 필터"
            value={filter}
            onChange={(e) => F(e.target.value)}
          >
            {[
              ["", "전체 케이스"],
              ["FAILED", "낮은 점수 / 미완료"],
              ["NOT_EVALUABLE", "평가 불가"],
              ["ERROR", "엔진 / 실행 오류"],
              ["docs", "검색 문서 부재"],
              ["tool", "Tool 실패"],
            ].map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <PageList
            items={exp.cases.filter((x: Row) => resultMatches(x, filter))}
            render={(x) => (
              <button className="row" onClick={() => J(x)}>
                <span>
                  <strong>{val(x.record.input)}</strong>
                  <small>{val(x.record.actual_output)}</small>
                </span>
                <span>
                  {Object.values(x.scores)
                    .map((s: any) => s.score ?? s.status)
                    .join(" / ") || x.status}
                </span>
              </button>
            )}
          />
        </section>
      )}
      <section>
        <h2>실험 비교</h2>
        <div className="line">
          {[
            ["기준 A", a, A],
            ["후보 B", b, B],
          ].map(([label, value, set]: any) => (
            <label key={label}>
              {label}
              <select
                value={value}
                onChange={(e) => {
                  set(e.target.value);
                  C(null);
                }}
              >
                <option value="">실험 선택</option>
                {runs.map((r) => (
                  <option value={r.id} key={r.id}>
                    {r.name} · {r.id.slice(0, 5)}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <button
            disabled={!a || !b || a === b || busy}
            onClick={() =>
              act(async () => C(await api("/compare?a=" + a + "&b=" + b)))
            }
          >
            비교하기
          </button>
        </div>
        {cmp && (
          <>
            <p>
              동일 케이스·지표 기준　
              {Object.entries(cmp.counts)
                .map(([k, v]) => k + " " + v)
                .join("　")}
            </p>
            <label>
              <input
                type="checkbox"
                checked={reg}
                onChange={(e) => R(e.target.checked)}
              />{" "}
              회귀만 보기
            </label>
            <PageList
              items={cmp.pairs
                .filter((p: Row) => !reg || p.label === "regression")
                .map((p: Row) => ({ ...p, id: p.case_id + p.mapping }))}
              render={(p) => (
                <details>
                  <summary>
                    {val(p.a.record.input)} · {mname(p.mapping)} · {p.label} · Δ{" "}
                    {p.delta ?? "—"}
                  </summary>
                  <div className="split">
                    {[p.a, p.b].map((side, i) => (
                      <div key={i}>
                        <h3>{i ? "후보 B" : "기준 A"}</h3>
                        <p>{val(side.record.actual_output)}</p>
                        <Json
                          value={{
                            tools: side.record.tools_called,
                            documents: side.record.retrieval_context,
                            result: side.scores[p.mapping],
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </details>
              )}
            />
          </>
        )}
      </section>
      {selected && (
        <dialog open>
          <header>
            <h2>케이스 평가 상세</h2>
            <button onClick={() => J(null)}>닫기</button>
          </header>
          <div className="split">
            <div>
              <h3>질문과 실행 결과</h3>
              <Json value={selected.record} />
            </div>
            <div>
              <h3>점수 · 이유 · 매핑 경로</h3>
              <Json value={selected.scores} />
              {selected.error && (
                <>
                  <p>{selected.error}</p>
                  <button
                    onClick={() =>
                      act(async () => {
                        await control("retry", selected.id);
                        J(null);
                      })
                    }
                  >
                    케이스 재시도
                  </button>
                </>
              )}
            </div>
          </div>
        </dialog>
      )}
    </>
  );
}

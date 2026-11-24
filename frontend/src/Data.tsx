import { useState } from "react";
import { api, Badge, date, Json, PageList, Props, Row, val } from "./common";
export function Data({
  state,
  version,
  setVersion,
  samples,
  refresh,
  act,
  busy,
}: Props) {
  const [sources, S] = useState<Row[] | null>(null),
    [src, A] = useState(""),
    [versions, V] = useState<Row[]>([]),
    [sv, B] = useState(""),
    [preview, P] = useState<Row | null>(null),
    [agent, G] = useState("policy-agent"),
    [msg, M] = useState(""),
    [q, Q] = useState(""),
    [sel, F] = useState(""),
    [ed, E] = useState(""),
    [behavior, H] = useState(""),
    [input, I] = useState("");
  const sample = samples.find((x) => x.id === sel);
  async function choose(id: string) {
    A(id);
    P(null);
    const vs = await api("/sources/" + encodeURIComponent(id) + "/versions");
    V(vs);
    B(vs[0]?.id || "");
  }
  function open(x: Row) {
    F(x.id);
    E(JSON.stringify(x.data.expected_output ?? null, null, 2));
    H(JSON.stringify(x.data.expected_behavior ?? null, null, 2));
    I(JSON.stringify(x.data.input, null, 2));
  }
  return (
    <>
      <div className="heading">
        <div>
          <div className="eyebrow">DATASETS</div>
          <h1>평가데이터 관리</h1>
          <p>평가 케이스와 원본 Trace를 확인하고 기대값을 관리하세요.</p>
        </div>
        <button
          className="primary"
          disabled={busy}
          onClick={() =>
            act(async () => {
              const all = await api("/sources");
              S(all);
              M("");
              if (all.length) await choose(all[0].id);
            })
          }
        >
          ↓　Phoenix 가져오기
        </button>
      </div>
      {sources && (
        <section>
          <header>
            <h2>Phoenix Dataset 가져오기</h2>
            <button onClick={() => S(null)}>닫기</button>
          </header>
          <Badge>{state.phoenix} 연결됨</Badge>
          <div className="line">
            <label>
              원본 Dataset
              <select
                value={src}
                onChange={(e) => act(() => choose(e.target.value))}
              >
                {sources.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              원본 버전
              <select
                value={sv}
                onChange={(e) => {
                  B(e.target.value);
                  P(null);
                }}
              >
                {versions.map((x) => (
                  <option key={x.id}>{x.id}</option>
                ))}
              </select>
            </label>
            <label>
              에이전트
              <input value={agent} onChange={(e) => G(e.target.value)} />
            </label>
          </div>
          <button
            disabled={busy || !sv}
            onClick={() =>
              act(async () =>
                P(
                  await api(
                    "/sources/" +
                      encodeURIComponent(src) +
                      "/preview?version=" +
                      encodeURIComponent(sv),
                  ),
                ),
              )
            }
          >
            가져올 항목 미리보기
          </button>
          {preview && (
            <>
              <p>{preview.count}개 케이스</p>
              {preview.samples.map((x: Row) => (
                <div key={x.source.dataset_item_id}>{val(x.input)}</div>
              ))}
              <button
                className="primary"
                disabled={busy || !agent.trim()}
                onClick={() =>
                  act(async () => {
                    const r = await api("/imports", {
                      source: src,
                      version: sv,
                      agent,
                    });
                    await refresh();
                    setVersion(r.version);
                    M(
                      r.duplicate
                        ? "이미 가져온 원본 버전입니다."
                        : r.imported + "건 가져오기 완료",
                    );
                  })
                }
              >
                가져오기
              </button>
            </>
          )}
          {busy && <progress />}
          <p role="status">{msg}</p>
        </section>
      )}
      <div className="stats">
        {[
          ["데이터셋", state.datasets.length, "▤"],
          ["선택 버전 케이스", samples.length, "▦"],
          [
            "연결된 Trace",
            samples.filter((x) => x.record.trace?.spans?.length).length,
            "⑂",
          ],
        ].map(([t, n, icon]) => (
          <div key={t}>
            <span>{t}</span>
            <b>{n}</b>
            <i>{icon}</i>
          </div>
        ))}
      </div>
      <section>
        <header>
          <h2>데이터셋 목록</h2>
          <Badge>{state.datasets.length}개</Badge>
        </header>
        {state.datasets.map((d: Row) => (
          <div className="dataset" key={d.id}>
            <div className="dbicon">▤</div>
            <div>
              <strong>{d.name}</strong>
              <small>
                {d.agent}　·　생성 {date(d.created)}
              </small>
            </div>
            <label className="push">
              버전
              <select
                aria-label={d.name + " 버전"}
                value={
                  d.versions.some((x: Row) => x.id === version) ? version : ""
                }
                onChange={(e) => setVersion(e.target.value)}
              >
                <option value="" disabled>
                  선택
                </option>
                {d.versions.map((x: Row) => (
                  <option key={x.id} value={x.id}>
                    v{x.number} · {x.count}건 · {date(x.created)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ))}
        {!state.datasets.length && <p>첫 Phoenix Dataset을 가져오세요.</p>}
      </section>
      <section>
        <header>
          <h2>평가 케이스</h2>
          <input
            className="search"
            placeholder="질문 또는 케이스 ID 검색"
            value={q}
            onChange={(e) => Q(e.target.value)}
          />
        </header>
        <div className="row caption">
          <span>질문 / CASE ID</span>
          <span>원본 Trace</span>
        </div>
        <PageList
          items={samples.filter((x) =>
            (val(x.data.input) + x.case_id).includes(q),
          )}
          render={(x) => (
            <button className="row" onClick={() => open(x)}>
              <span>
                <strong>{val(x.data.input)}</strong>
                <small>{x.case_id.slice(0, 8)}</small>
              </span>
              <Badge>{x.record.trace.spans.length ? "연결됨" : "미연결"}</Badge>
            </button>
          )}
        />
      </section>
      {sample && (
        <dialog open>
          <header>
            <h2>케이스 상세</h2>
            <button onClick={() => F("")}>닫기</button>
          </header>
          {sample.data.warnings.map((w: string) => (
            <p key={w}>{w}</p>
          ))}
          <details>
            <summary>원본 응답 · Trace · Tool 호출</summary>
            <Json value={sample.record} />
          </details>
          {[
            ["입력 JSON", input, I],
            ["기대 응답 JSON", ed, E],
            ["기대 동작 JSON", behavior, H],
          ].map(([label, value, set]: any) => (
            <label key={label}>
              {label}
              <textarea value={value} onChange={(e) => set(e.target.value)} />
            </label>
          ))}
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              act(async () => {
                const r = await api(
                  "/versions/" + version + "/cases/" + sample.case_id,
                  {
                    input: JSON.parse(input),
                    expected_output: JSON.parse(ed),
                    expected_behavior: JSON.parse(behavior),
                  },
                  "PATCH",
                );
                await refresh();
                setVersion(r.version);
                F("");
              })
            }
          >
            새 버전 저장
          </button>
        </dialog>
      )}
    </>
  );
}

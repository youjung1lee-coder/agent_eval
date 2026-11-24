import { useState } from "react";
import { Row, Tree } from "./common";

export function RuleEditor({ apply }: { apply: (r: Row) => void }) {
  const [type, T] = useState("path"),
    [path, P] = useState("/actual_output/text"),
    [kind, K] = useState("RETRIEVER"),
    [contains, N] = useState(""),
    [policy, S] = useState("unique"),
    [attrs, A] = useState("{}"),
    [fixed, F] = useState("null"),
    [paths, J] = useState("/input/text\n/actual_output/text");
  return (
    <details>
      <summary>변수 경로 설정</summary>
      <label>
        데이터 출처
        <select value={type} onChange={(e) => T(e.target.value)}>
          {[
            ["path", "필드 경로"],
            ["expected", "Dataset 기대 응답"],
            ["span", "Span 선택 조건"],
            ["fixed", "고정 JSON 값"],
            ["join", "여러 경로를 줄바꿈으로 결합"],
          ].map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      {type === "span" && (
        <>
          <label>
            Span kind
            <input value={kind} onChange={(e) => K(e.target.value)} />
          </label>
          <label>
            Span 이름 포함
            <input value={contains} onChange={(e) => N(e.target.value)} />
          </label>
          <label>
            속성 필터 JSON
            <input value={attrs} onChange={(e) => A(e.target.value)} />
          </label>
          <label>
            일치 정책
            <select value={policy} onChange={(e) => S(e.target.value)}>
              {["unique", "first", "last", "all"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </>
      )}
      {["path", "span"].includes(type) && (
        <label>
          JSON Pointer
          <input value={path} onChange={(e) => P(e.target.value)} />
        </label>
      )}
      {type === "fixed" && (
        <label>
          고정값
          <input value={fixed} onChange={(e) => F(e.target.value)} />
        </label>
      )}
      {type === "join" && (
        <label>
          한 줄에 경로 하나
          <textarea value={paths} onChange={(e) => J(e.target.value)} />
        </label>
      )}
      <button
        onClick={() =>
          apply(
            type === "fixed"
              ? { literal: fixed }
              : type === "join"
                ? { join: paths.split("\n") }
                : type === "expected"
                  ? { path: "/expected_output" }
                  : type === "span"
                    ? { path, policy, kind, contains, attrs }
                    : { path },
          )
        }
      >
        변수에 적용
      </button>
    </details>
  );
}

export function SpanTree({
  spans,
  pick,
}: {
  spans: Row[];
  pick: (p: string) => void;
}) {
  const id = (s: Row) => s.context?.span_id || s.id;
  const ids = new Set(spans.map(id));
  function render(s: Row, seen: Set<Row>): React.ReactNode {
    if (seen.has(s)) return null;
    const next = new Set(seen).add(s),
      idx = spans.indexOf(s);
    return (
      <details key={idx}>
        <summary>{s.name || s.kind || s.span_kind || id(s)}</summary>
        <Tree node={s} path={"/trace/spans/" + idx} pick={pick} />
        <div className="tree">
          {spans
            .filter((x) => x.parent_id && x.parent_id === id(s))
            .map((x) => render(x, next))}
        </div>
      </details>
    );
  }
  return (
    <div className="tree">
      {spans
        .filter((s) => !s.parent_id || !ids.has(s.parent_id))
        .map((s) => render(s, new Set()))}
    </div>
  );
}

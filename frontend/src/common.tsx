import React, { useState } from "react";
import { pageWindow } from "./model.js";
export type Row = Record<string, any>;
export async function api(path: string, body?: unknown, method?: string) {
  const key = sessionStorage.getItem("gaia-key");
  const r = await fetch("/api" + path, {
    method: method || (body === undefined ? "GET" : "POST"),
    headers: {
      "Content-Type": "application/json",
      ...(key ? { Authorization: "Bearer " + key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
export function val(x: any): string {
  return typeof x === "string" ? x : (x?.text ?? JSON.stringify(x) ?? "—");
}
export const date = (s: string) =>
  new Date(s).toLocaleString("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  });
export function Json({ value }: { value: any }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}
export function Badge({ children }: { children: React.ReactNode }) {
  return <span className="badge">{children}</span>;
}
export function PageList({
  items,
  render,
}: {
  items: Row[];
  render: (x: Row) => React.ReactNode;
}) {
  const [page, set] = useState(0),
    { last, current: p, visible } = pageWindow(items, page);
  return (
    <>
      {visible.map((x: Row) => (
        <React.Fragment key={x.id ?? x.case_id}>{render(x)}</React.Fragment>
      ))}
      {!items.length && <p className="muted">조건에 맞는 항목이 없습니다.</p>}
      {last > 0 && (
        <footer>
          <button disabled={!p} onClick={() => set(p - 1)}>
            이전
          </button>
          <span>
            {p + 1} / {last + 1}
          </span>
          <button disabled={p === last} onClick={() => set(p + 1)}>
            다음
          </button>
        </footer>
      )}
    </>
  );
}
export function Tree({
  node,
  path = "",
  pick,
}: {
  node: any;
  path?: string;
  pick: (p: string) => void;
}) {
  if (node === null || typeof node !== "object")
    return (
      <button className="leaf" onClick={() => pick(path)}>
        {val(node)}
      </button>
    );
  return (
    <div className="tree">
      {Object.entries(node).map(([k, v]) => {
        const p = path + "/" + k.replaceAll("~", "~0").replaceAll("/", "~1");
        return (
          <details key={k}>
            <summary>
              {k}{" "}
              <small>
                {Array.isArray(v) ? "[" + v.length + "]" : typeof v}
              </small>
            </summary>
            <button className="link" onClick={() => pick(p)}>
              이 경로 선택
            </button>
            <Tree node={v} path={p} pick={pick} />
          </details>
        );
      })}
    </div>
  );
}
export type Props = {
  state: Row;
  version: string;
  setVersion: (id: string) => void;
  samples: Row[];
  refresh: () => Promise<void>;
  act: (fn: () => Promise<any>) => Promise<void>;
  busy: boolean;
};

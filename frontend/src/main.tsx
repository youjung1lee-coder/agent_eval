import { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, Props, Row } from "./common";
import { Data } from "./Data";
import { Evaluators } from "./Evaluators";
import { Results } from "./Results";
import "./style.css";

const tabs = [
  ["data", "▤", "평가데이터 관리"],
  ["evaluators", "⌘", "평가함수 관리"],
  ["results", "▥", "평가결과 관리"],
];
function route() {
  return tabs.find((t) => t[0] === location.hash.slice(1))?.[0] || "data";
}
function App() {
  const [tab, T] = useState(route),
    [state, S] = useState<Row | null>(null),
    [version, V] = useState(""),
    [samples, L] = useState<Row[]>([]),
    [busy, B] = useState(false),
    [loading, H] = useState(false),
    [error, E] = useState(""),
    [token, K] = useState("");
  const refresh = useCallback(async () => {
    const r = await api("/state");
    S(r);
    V((prev) => prev || r.datasets[0]?.versions[0]?.id || "");
  }, []);
  const act = useCallback(async (fn: () => Promise<any>) => {
    B(true);
    E("");
    try {
      await fn();
    } catch (e) {
      E(e instanceof Error ? e.message : String(e));
    } finally {
      B(false);
    }
  }, []);
  useEffect(() => {
    act(refresh);
    const handler = () => T(route());
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  useEffect(() => {
    let live = true;
    L([]);
    if (version) {
      H(true);
      api("/versions/" + version + "/cases")
        .then((x) => {
          if (live) L(x);
        })
        .catch((e) => {
          if (live) E(String(e));
        })
        .finally(() => {
          if (live) H(false);
        });
    }
    return () => {
      live = false;
    };
  }, [version]);
  const props = {
    state,
    version,
    setVersion: V,
    samples,
    refresh,
    act,
    busy: busy || loading,
  } as Props;
  return (
    <div className="workspace">
      <aside>
        <div className="brand">
          <i>G</i> GAIA
        </div>
        <div className="navtitle">평가 워크스페이스</div>
        <nav>
          {tabs.map(([id, icon, label]) => (
            <a key={id} href={"#" + id} className={tab === id ? "active" : ""}>
              <b>{icon}</b>
              {label}
            </a>
          ))}
        </nav>
        <div className="env">
          <i /> {state?.mode || "연결 중"} Workspace
        </div>
      </aside>
      <main>
        <div className="bar">
          워크스페이스 <span>/</span> {tabs.find((t) => t[0] === tab)?.[2]}
          <b>{state?.mode || "GAIA"}</b>
        </div>
        <div className="content">
          {error && (
            <div role="alert" className="alert">
              {error} <button onClick={() => act(refresh)}>다시 조회</button>
            </div>
          )}
          {!state ? (
            error ? (
              <section>
                <h2>워크스페이스 접속</h2>
                <label>
                  API 키
                  <input
                    type="password"
                    value={token}
                    onChange={(e) => K(e.target.value)}
                  />
                </label>
                <button
                  onClick={() =>
                    act(async () => {
                      sessionStorage.setItem("gaia-key", token);
                      await refresh();
                    })
                  }
                >
                  접속
                </button>
              </section>
            ) : (
              <p>워크스페이스를 불러오는 중…</p>
            )
          ) : (
            <>
              {tab !== "data" && (
                <label className="context">
                  평가 Dataset
                  <select value={version} onChange={(e) => V(e.target.value)}>
                    {state.datasets.flatMap((d: Row) =>
                      d.versions.map((v: Row) => (
                        <option key={v.id} value={v.id}>
                          {d.name} · v{v.number}
                        </option>
                      )),
                    )}
                  </select>
                </label>
              )}
              {tab === "data" ? (
                <Data {...props} />
              ) : tab === "evaluators" ? (
                <Evaluators key={version} {...props} />
              ) : (
                <Results key={version} {...props} />
              )}
            </>
          )}
          {(busy || loading) && (
            <div className="working" role="status">
              처리 중…
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

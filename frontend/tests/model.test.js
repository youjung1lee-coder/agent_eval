import { test } from "node:test";
import assert from "node:assert/strict";
import { pageWindow, resultMatches } from "../src/model.js";
test("pagination clamps the page when a search narrows the results", () => {
  assert.deepEqual(pageWindow([1, 2], 5), {
    current: 0,
    last: 0,
    visible: [1, 2],
  });
  assert.equal(pageWindow(Array(20).fill(1), 2).visible.length, 4);
});
test("unscorable, zero score and execution errors have distinct filters", () => {
  const row = {
    record: {},
    scores: { m: { status: "NOT_EVALUABLE", score: null } },
    status: "DONE",
  };
  assert.ok(resultMatches(row, "NOT_EVALUABLE"));
  assert.equal(resultMatches(row, "FAILED"), false);
  assert.ok(resultMatches({ ...row, status: "ERROR" }, "ERROR"));
  assert.ok(
    resultMatches(
      { ...row, scores: { m: { status: "FAILED", score: 0 } } },
      "FAILED",
    ),
  );
});
test("retrieval and tool heuristics read the execution snapshot", () => {
  const row = {
    record: { retrieval_context: ["doc"], tools_called: [{ status: "error" }] },
    scores: {},
  };
  assert.equal(resultMatches(row, "docs"), false);
  assert.ok(resultMatches(row, "tool"));
});

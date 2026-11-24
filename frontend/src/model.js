export function pageWindow(items, page, size = 8) {
  const last = Math.max(0, Math.ceil(items.length / size) - 1);
  const current = Math.max(0, Math.min(page, last));
  return {
    current,
    last,
    visible: items.slice(current * size, (current + 1) * size),
  };
}
export function resultMatches(row, filter) {
  if (!filter || row.status === filter) return true;
  if (filter === "docs") return !row.record.retrieval_context?.length;
  if (filter === "tool")
    return row.record.tools_called?.some((t) => t.status === "error") ?? false;
  return Object.values(row.scores).some((metric) => metric.status === filter);
}

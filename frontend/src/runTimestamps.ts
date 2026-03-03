import type { TestRun } from "@/types";

export function getRunTimestamp(run: TestRun): Date | null {
  const candidate = run.started_at || run.completed_at || run.created_at;
  if (!candidate) {
    return null;
  }

  const date = new Date(candidate);
  return Number.isNaN(date.getTime()) ? null : date;
}

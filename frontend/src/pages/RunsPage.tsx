import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Loader2,
  Play,
  ChevronLeft,
  ChevronRight,
  Filter,
} from "lucide-react";
import { format } from "date-fns";
import { getRuns, getSuites } from "@/api";
import type { TestRun, Suite, PaginatedResponse } from "@/types";
import StatusBadge from "@/components/StatusBadge";

export default function RunsPage() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [suites, setSuites] = useState<Suite[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterSuite, setFilterSuite] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const perPage = 20;

  useEffect(() => {
    getSuites()
      .then(setSuites)
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    getRuns({
      suite_id: filterSuite || undefined,
      status: filterStatus || undefined,
      page,
      limit: perPage,
    })
      .then((res: PaginatedResponse<TestRun>) => {
        setRuns(res.items);
        setTotal(res.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, filterSuite, filterStatus]);

  const totalPages = Math.ceil(total / perPage) || 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Test Runs</h1>
        <p className="text-gray-400 mt-1">
          Browse and filter all evaluation runs
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Filter size={16} className="text-gray-500" />
        <select
          className="select max-w-[200px]"
          value={filterSuite}
          onChange={(e) => {
            setFilterSuite(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Suites</option>
          {suites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          className="select max-w-[160px]"
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Statuses</option>
          <option value="passed">Passed</option>
          <option value="failed">Failed</option>
          <option value="running">Running</option>
          <option value="pending">Pending</option>
          <option value="error">Error</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="animate-spin text-drift-400" size={32} />
        </div>
      ) : runs.length > 0 ? (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700">
                <th className="table-header">Run ID</th>
                <th className="table-header">Suite</th>
                <th className="table-header">Status</th>
                <th className="table-header">Pass Rate</th>
                <th className="table-header">Tests</th>
                <th className="table-header">Trigger</th>
                <th className="table-header">Duration</th>
                <th className="table-header">Date</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  className="border-b border-surface-700/50 hover:bg-surface-800/50 transition-colors"
                >
                  <td className="table-cell">
                    <Link
                      to={`/runs/${run.id}`}
                      className="font-mono text-sm text-drift-400 hover:text-drift-300"
                    >
                      {run.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="table-cell font-medium text-white">
                    {run.suite_name || run.suite_id.slice(0, 8)}
                  </td>
                  <td className="table-cell">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="table-cell">
                    {run.pass_rate != null ? (
                      <span
                        className={
                          run.pass_rate >= 90
                            ? "text-emerald-400"
                            : run.pass_rate >= 70
                              ? "text-amber-400"
                              : "text-red-400"
                        }
                      >
                        {run.pass_rate}%
                      </span>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                  <td className="table-cell">
                    <span className="text-emerald-400">{run.passed_tests}</span>
                    <span className="text-gray-500"> / </span>
                    {run.total_tests}
                  </td>
                  <td className="table-cell capitalize text-gray-300">
                    {run.trigger}
                  </td>
                  <td className="table-cell text-gray-300">
                    {run.duration_ms != null
                      ? `${(run.duration_ms / 1000).toFixed(1)}s`
                      : "—"}
                  </td>
                  <td className="table-cell text-gray-400">
                    {run.started_at
                      ? format(new Date(run.started_at), "MMM dd, HH:mm")
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="p-4 flex items-center justify-between border-t border-surface-700">
            <span className="text-sm text-gray-400">
              {total} total run{total !== 1 ? "s" : ""}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="btn-secondary text-sm flex items-center gap-1"
              >
                <ChevronLeft size={14} />
                Prev
              </button>
              <span className="text-sm text-gray-400 px-2">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
                className="btn-secondary text-sm flex items-center gap-1"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="card p-16 text-center">
          <Play className="mx-auto text-gray-600 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-300 mb-2">
            No runs found
          </h3>
          <p className="text-gray-500">
            {filterSuite || filterStatus
              ? "Try adjusting your filters."
              : "Trigger a run from a test suite to see results here."}
          </p>
        </div>
      )}
    </div>
  );
}

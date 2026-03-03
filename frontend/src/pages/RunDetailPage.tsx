import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  RotateCw,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  Clock,
  Zap,
  Coins,
} from "lucide-react";
import { format } from "date-fns";
import { getRun, triggerRun } from "@/api";
import type { TestRun, TestResult, AssertionResult } from "@/types";
import StatusBadge from "@/components/StatusBadge";
import clsx from "clsx";

function AssertionRow({ assertion }: { assertion: AssertionResult }) {
  return (
    <div className="flex items-start gap-3 py-2 px-4 bg-surface-900/50 rounded-lg">
      <div className="mt-0.5">
        {assertion.passed ? (
          <Check size={14} className="text-emerald-400" />
        ) : (
          <X size={14} className="text-red-400" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">
            {assertion.name}
          </span>
          <span className="text-xs text-gray-500 bg-surface-800 px-2 py-0.5 rounded">
            {assertion.type}
          </span>
        </div>
        {!assertion.passed && assertion.message && (
          <p className="text-xs text-red-400 mt-1">{assertion.message}</p>
        )}
        {assertion.expected && (
          <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-gray-500">Expected:</span>
              <pre className="mt-1 bg-surface-950 text-emerald-300 p-2 rounded overflow-x-auto">
                {assertion.expected}
              </pre>
            </div>
            {assertion.actual && (
              <div>
                <span className="text-gray-500">Actual:</span>
                <pre className="mt-1 bg-surface-950 text-red-300 p-2 rounded overflow-x-auto">
                  {assertion.actual}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ResultRow({ result }: { result: TestResult }) {
  const [expanded, setExpanded] = useState(!result.passed);

  return (
    <>
      <tr
        className="border-b border-surface-700/50 hover:bg-surface-800/50 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="table-cell">
          <div className="flex items-center gap-2">
            {expanded ? (
              <ChevronDown size={14} className="text-gray-500" />
            ) : (
              <ChevronRight size={14} className="text-gray-500" />
            )}
            <span className="font-medium text-white">{result.test_name}</span>
          </div>
        </td>
        <td className="table-cell">
          <span className="text-xs bg-surface-700 text-gray-300 px-2 py-0.5 rounded font-mono">
            {result.model}
          </span>
        </td>
        <td className="table-cell">
          {result.passed ? (
            <div className="flex items-center gap-1.5 text-emerald-400">
              <Check size={15} />
              Passed
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-red-400">
              <X size={15} />
              Failed
            </div>
          )}
        </td>
        <td className="table-cell">
          <div className="flex items-center gap-1.5 text-gray-300">
            <Clock size={13} className="text-gray-500" />
            {result.latency_ms}ms
          </div>
        </td>
        <td className="table-cell">
          <div className="flex items-center gap-1.5 text-gray-300">
            <Zap size={13} className="text-gray-500" />
            {result.tokens_used}
          </div>
        </td>
        <td className="table-cell">
          {result.cost != null && (
            <div className="flex items-center gap-1.5 text-gray-300">
              <Coins size={13} className="text-gray-500" />$
              {result.cost.toFixed(4)}
            </div>
          )}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} className="px-4 py-4 bg-surface-900/30">
            <div className="space-y-3">
              <div>
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Model Output
                </span>
                <pre className="mt-2 bg-surface-950 text-gray-300 p-4 rounded-lg text-sm overflow-x-auto whitespace-pre-wrap border border-surface-700">
                  {result.output}
                </pre>
              </div>

              {result.assertions.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                    Assertions ({result.assertions.filter((a) => a.passed).length}
                    /{result.assertions.length} passed)
                  </span>
                  <div className="mt-2 space-y-2">
                    {result.assertions.map((a, i) => (
                      <AssertionRow key={i} assertion={a} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<TestRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);

  useEffect(() => {
    if (!id) return;
    getRun(id)
      .then(setRun)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  async function handleRerun() {
    if (!run) return;
    setRerunning(true);
    try {
      await triggerRun(run.suite_id);
    } catch {
      // error
    } finally {
      setRerunning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-drift-400" size={32} />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="card p-16 text-center">
        <h3 className="text-lg font-medium text-gray-300">Run not found</h3>
        <Link to="/runs" className="text-drift-400 hover:text-drift-300 mt-2 inline-block">
          Back to runs
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to="/runs"
          className="p-2 rounded-lg hover:bg-surface-800 text-gray-400 transition-colors"
        >
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">
              {run.suite_name || "Run Details"}
            </h1>
            <StatusBadge status={run.status} />
          </div>
          <p className="text-gray-400 mt-1 font-mono text-sm">{run.id}</p>
        </div>
        <button
          onClick={handleRerun}
          disabled={rerunning}
          className="btn-secondary flex items-center gap-2"
        >
          <RotateCw
            size={15}
            className={clsx(rerunning && "animate-spin")}
          />
          Re-run
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wider">
            Pass Rate
          </p>
          <p
            className={clsx("text-2xl font-bold mt-1", {
              "text-emerald-400": (run.pass_rate ?? 0) >= 90,
              "text-amber-400":
                (run.pass_rate ?? 0) >= 70 && (run.pass_rate ?? 0) < 90,
              "text-red-400": (run.pass_rate ?? 0) < 70,
            })}
          >
            {run.pass_rate != null ? `${run.pass_rate}%` : "—"}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wider">
            Tests
          </p>
          <p className="text-2xl font-bold text-white mt-1">
            <span className="text-emerald-400">{run.passed_tests}</span>
            <span className="text-gray-500 text-lg"> / {run.total_tests}</span>
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wider">
            Trigger
          </p>
          <p className="text-2xl font-bold text-white mt-1 capitalize">
            {run.trigger}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wider">
            Duration
          </p>
          <p className="text-2xl font-bold text-white mt-1">
            {run.duration_ms != null
              ? `${(run.duration_ms / 1000).toFixed(1)}s`
              : "—"}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-6 text-sm text-gray-400">
        {run.started_at && (
          <span>
            Started: {format(new Date(run.started_at), "MMM dd, yyyy HH:mm:ss")}
          </span>
        )}
        {run.completed_at && (
          <span>
            Completed:{" "}
            {format(new Date(run.completed_at), "MMM dd, yyyy HH:mm:ss")}
          </span>
        )}
      </div>

      <div className="card overflow-hidden">
        <div className="p-6 pb-0">
          <h2 className="text-lg font-semibold text-white">Test Results</h2>
        </div>
        {run.results && run.results.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full mt-4">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="table-header">Test Name</th>
                  <th className="table-header">Model</th>
                  <th className="table-header">Result</th>
                  <th className="table-header">Latency</th>
                  <th className="table-header">Tokens</th>
                  <th className="table-header">Cost</th>
                </tr>
              </thead>
              <tbody>
                {run.results.map((result) => (
                  <ResultRow key={result.id} result={result} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-gray-500">
            No test results available.
          </div>
        )}
      </div>
    </div>
  );
}

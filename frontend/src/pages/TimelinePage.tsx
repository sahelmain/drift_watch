import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Loader2, Activity, TrendingDown } from "lucide-react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { format } from "date-fns";
import { getSuites, getDriftTimeline, getRuns } from "@/api";
import type { Suite, DriftScore, TestRun } from "@/types";
import StatusBadge from "@/components/StatusBadge";
import { getRunTimestamp } from "@/runTimestamps";

const DRIFT_THRESHOLD = 0.3;

export default function TimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedSuiteId = searchParams.get("suite") || "";
  const [suites, setSuites] = useState<Suite[]>([]);
  const [timeline, setTimeline] = useState<DriftScore[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSuites()
      .then(setSuites)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedSuiteId) {
      setTimeline([]);
      setRuns([]);
      return;
    }
    setLoading(true);
    Promise.all([
      getDriftTimeline(selectedSuiteId).catch(() => []),
      getRuns({ suite_id: selectedSuiteId, limit: 50 }).catch(() => ({
        items: [],
        total: 0,
        page: 1,
        limit: 50,
        pages: 1,
      })),
    ])
      .then(([drift, runsRes]) => {
        setTimeline(drift);
        setRuns(runsRes.items);
      })
      .finally(() => setLoading(false));
  }, [selectedSuiteId]);

  function selectSuite(id: string) {
    setSearchParams(id ? { suite: id } : {});
  }

  const driftViolations = timeline.filter(
    (d) => d.drift_score > DRIFT_THRESHOLD,
  );

  const chartData = timeline.map((d) => ({
    ...d,
    date: format(new Date(d.date), "MMM dd"),
    pass_rate_pct: Math.round(d.pass_rate * 100 * 100) / 100,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Drift Timeline</h1>
        <p className="text-gray-400 mt-1">
          Track evaluation quality drift over time
        </p>
      </div>

      <div className="flex items-center gap-4">
        <select
          className="select max-w-xs"
          value={selectedSuiteId}
          onChange={(e) => selectSuite(e.target.value)}
        >
          <option value="">Select a suite...</option>
          {suites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        {driftViolations.length > 0 && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-1.5">
            <TrendingDown size={14} />
            {driftViolations.length} drift threshold violation
            {driftViolations.length > 1 ? "s" : ""}
          </div>
        )}
      </div>

      {!selectedSuiteId ? (
        <div className="card p-16 text-center">
          <Activity className="mx-auto text-gray-600 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-300 mb-2">
            Select a Suite
          </h3>
          <p className="text-gray-500">
            Choose a test suite to view its drift timeline.
          </p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="animate-spin text-drift-400" size={32} />
        </div>
      ) : timeline.length === 0 ? (
        <div className="card p-16 text-center">
          <Activity className="mx-auto text-gray-600 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-300 mb-2">
            No Timeline Data
          </h3>
          <p className="text-gray-500">
            Run this suite a few times to start seeing drift trends.
          </p>
        </div>
      ) : (
        <>
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Pass Rate Over Time
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
                <XAxis dataKey="date" stroke="#5e7299" tick={{ fontSize: 12 }} />
                <YAxis
                  stroke="#5e7299"
                  tick={{ fontSize: 12 }}
                  domain={[0, 100]}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#162037",
                    border: "1px solid #1e2d4a",
                    borderRadius: "8px",
                    color: "#e0e7f5",
                  }}
                  formatter={(value: number) => [`${value}%`, "Pass Rate"]}
                />
                <ReferenceLine
                  y={70}
                  stroke="#ef4444"
                  strokeDasharray="6 4"
                  label={{
                    value: "Min Threshold",
                    fill: "#ef4444",
                    fontSize: 11,
                  }}
                />
                {driftViolations.map((v, i) => {
                  const idx = chartData.findIndex(
                    (d) => d.run_id === v.run_id,
                  );
                  if (idx < 0) return null;
                  const d = chartData[idx];
                  return (
                    <ReferenceArea
                      key={i}
                      x1={d?.date}
                      x2={d?.date}
                      fill="#ef4444"
                      fillOpacity={0.08}
                    />
                  );
                })}
                <Line
                  type="monotone"
                  dataKey="pass_rate_pct"
                  stroke="#3b6eff"
                  strokeWidth={2.5}
                  dot={{ fill: "#3b6eff", r: 4 }}
                  activeDot={{ r: 6, fill: "#5c94ff" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Drift Score
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
                <XAxis dataKey="date" stroke="#5e7299" tick={{ fontSize: 12 }} />
                <YAxis
                  stroke="#5e7299"
                  tick={{ fontSize: 12 }}
                  domain={[0, 1]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#162037",
                    border: "1px solid #1e2d4a",
                    borderRadius: "8px",
                    color: "#e0e7f5",
                  }}
                  formatter={(value: number) => [
                    value.toFixed(3),
                    "Drift Score",
                  ]}
                />
                <ReferenceLine
                  y={DRIFT_THRESHOLD}
                  stroke="#f59e0b"
                  strokeDasharray="6 4"
                  label={{
                    value: "Threshold",
                    fill: "#f59e0b",
                    fontSize: 11,
                  }}
                />
                <defs>
                  <linearGradient
                    id="driftGradient"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="5%"
                      stopColor="#f59e0b"
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="95%"
                      stopColor="#f59e0b"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="drift_score"
                  stroke="#f59e0b"
                  fill="url(#driftGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <div className="p-6 pb-0">
              <h2 className="text-lg font-semibold text-white">
                Historical Runs
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full mt-4">
                <thead>
                  <tr className="border-b border-surface-700">
                    <th className="table-header">Run ID</th>
                    <th className="table-header">Status</th>
                    <th className="table-header">Pass Rate</th>
                    <th className="table-header">Tests</th>
                    <th className="table-header">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => {
                    const runTimestamp = getRunTimestamp(run);

                    return (
                      <tr
                        key={run.id}
                        className="border-b border-surface-700/50 hover:bg-surface-800/50 transition-colors"
                      >
                        <td className="table-cell">
                          <Link
                            to={`/runs/${run.id}`}
                            className="font-mono text-drift-400 hover:text-drift-300 text-sm"
                          >
                            {run.id.slice(0, 8)}
                          </Link>
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
                            "—"
                          )}
                        </td>
                        <td className="table-cell">
                          <span className="text-emerald-400">
                            {run.passed_tests}
                          </span>
                          <span className="text-gray-500"> / </span>
                          {run.total_tests}
                        </td>
                        <td className="table-cell text-gray-400">
                          {runTimestamp
                            ? format(runTimestamp, "MMM dd, HH:mm")
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

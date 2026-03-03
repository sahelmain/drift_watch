import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  FlaskConical,
  Play,
  TrendingUp,
  Bell,
  ArrowRight,
  Loader2,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format } from "date-fns";
import { getSuites, getRuns, getAlerts } from "@/api";
import type { Suite, TestRun, AlertConfig } from "@/types";
import StatusBadge from "@/components/StatusBadge";
import { getRunTimestamp } from "@/runTimestamps";

interface Stats {
  totalSuites: number;
  totalRuns: number;
  avgPassRate: number;
  activeAlerts: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({
    totalSuites: 0,
    totalRuns: 0,
    avgPassRate: 0,
    activeAlerts: 0,
  });
  const [recentRuns, setRecentRuns] = useState<TestRun[]>([]);
  const [trendData, setTrendData] = useState<
    { date: string; pass_rate: number }[]
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [suites, runsRes, alerts] = await Promise.all([
          getSuites().catch(() => [] as Suite[]),
          getRuns({ limit: 30 }).catch(() => ({
            items: [],
            total: 0,
            page: 1,
            limit: 30,
            pages: 1,
          })),
          getAlerts().catch(() => [] as AlertConfig[]),
        ]);

        const runs = runsRes.items;
        const avgRate =
          runs.length > 0
            ? runs.reduce((s, r) => s + (r.pass_rate ?? 0), 0) / runs.length
            : 0;

        setStats({
          totalSuites: suites.length,
          totalRuns: runsRes.total,
          avgPassRate: Math.round(avgRate * 100) / 100,
          activeAlerts: alerts.filter((a) => a.enabled).length,
        });

        setRecentRuns(runs.slice(0, 10));

        const grouped = new Map<string, number[]>();
        for (const run of runs) {
          const runTimestamp = getRunTimestamp(run);
          if (!runTimestamp) {
            continue;
          }

          const day = format(runTimestamp, "MMM dd");
          const existing = grouped.get(day) || [];
          existing.push(run.pass_rate ?? 0);
          grouped.set(day, existing);
        }
        setTrendData(
          Array.from(grouped.entries()).map(([date, rates]) => ({
            date,
            pass_rate:
              Math.round(
                (rates.reduce((a, b) => a + b, 0) / rates.length) * 100,
              ) / 100,
          })),
        );
      } catch {
        // Silently handle — empty state will show
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statCards = [
    {
      label: "Total Suites",
      value: stats.totalSuites,
      icon: FlaskConical,
      color: "text-drift-400",
      bg: "bg-drift-500/10",
    },
    {
      label: "Total Runs (30d)",
      value: stats.totalRuns,
      icon: Play,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
    },
    {
      label: "Avg Pass Rate",
      value: `${stats.avgPassRate}%`,
      icon: TrendingUp,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
    },
    {
      label: "Active Alerts",
      value: stats.activeAlerts,
      icon: Bell,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-drift-400" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">
          Overview of your LLM evaluation health
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div key={card.label} className="card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">{card.label}</p>
                <p className="text-2xl font-bold text-white mt-1">
                  {card.value}
                </p>
              </div>
              <div className={`${card.bg} p-3 rounded-xl`}>
                <card.icon className={card.color} size={22} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white">
            Pass Rate Trend
          </h2>
          <span className="text-sm text-gray-400">Last 30 days</span>
        </div>
        {trendData.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
              <XAxis
                dataKey="date"
                stroke="#5e7299"
                tick={{ fontSize: 12 }}
              />
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
              <Line
                type="monotone"
                dataKey="pass_rate"
                stroke="#3b6eff"
                strokeWidth={2.5}
                dot={{ fill: "#3b6eff", r: 4 }}
                activeDot={{ r: 6, fill: "#5c94ff" }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-64 text-gray-500">
            No run data available yet. Create a suite and run it to see trends.
          </div>
        )}
      </div>

      <div className="card">
        <div className="flex items-center justify-between p-6 pb-0">
          <h2 className="text-lg font-semibold text-white">Recent Runs</h2>
          <Link
            to="/runs"
            className="text-sm text-drift-400 hover:text-drift-300 flex items-center gap-1"
          >
            View all <ArrowRight size={14} />
          </Link>
        </div>
        {recentRuns.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full mt-4">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="table-header">Suite</th>
                  <th className="table-header">Status</th>
                  <th className="table-header">Pass Rate</th>
                  <th className="table-header">Tests</th>
                  <th className="table-header">Trigger</th>
                  <th className="table-header">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => {
                  const runTimestamp = getRunTimestamp(run);

                  return (
                    <tr
                      key={run.id}
                      className="border-b border-surface-700/50 hover:bg-surface-800/50 transition-colors"
                    >
                      <td className="table-cell font-medium text-white">
                        <Link
                          to={`/runs/${run.id}`}
                          className="hover:text-drift-400"
                        >
                          {run.suite_name || run.suite_id}
                        </Link>
                      </td>
                      <td className="table-cell">
                        <StatusBadge status={run.status} />
                      </td>
                      <td className="table-cell">
                        {run.pass_rate != null ? `${run.pass_rate}%` : "—"}
                      </td>
                      <td className="table-cell">
                        <span className="text-emerald-400">
                          {run.passed_tests}
                        </span>
                        <span className="text-gray-500"> / </span>
                        <span>{run.total_tests}</span>
                      </td>
                      <td className="table-cell capitalize">{run.trigger}</td>
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
        ) : (
          <div className="p-12 text-center text-gray-500">
            No runs yet. Create a test suite to get started.
          </div>
        )}
      </div>
    </div>
  );
}

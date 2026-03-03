import { useState, useEffect } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  X,
  Loader2,
  Bell,
  Send,
  MessageSquare,
  Mail,
  AlertTriangle,
  Ticket,
} from "lucide-react";
import {
  getAlerts,
  createAlert,
  updateAlert,
  deleteAlert,
  testWebhook,
  getSuites,
} from "@/api";
import type { AlertConfig, Suite } from "@/types";

const channelIcons: Record<string, typeof Bell> = {
  slack: MessageSquare,
  email: Mail,
  pagerduty: AlertTriangle,
  jira: Ticket,
};

const channelOptions = [
  { value: "slack", label: "Slack" },
  { value: "email", label: "Email" },
  { value: "pagerduty", label: "PagerDuty" },
  { value: "jira", label: "Jira" },
];

const metricOptions = [
  { value: "pass_rate", label: "Pass Rate" },
  { value: "drift_score", label: "Drift Score" },
  { value: "latency_p95", label: "Latency (p95)" },
  { value: "failure_count", label: "Failure Count" },
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertConfig[]>([]);
  const [suites, setSuites] = useState<Suite[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AlertConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);

  const [formChannel, setFormChannel] = useState("slack");
  const [formDest, setFormDest] = useState("");
  const [formMetric, setFormMetric] = useState("pass_rate");
  const [formThreshold, setFormThreshold] = useState("");
  const [formSuiteId, setFormSuiteId] = useState("");
  const [formEnabled, setFormEnabled] = useState(true);

  useEffect(() => {
    Promise.all([
      getAlerts().catch(() => []),
      getSuites().catch(() => []),
    ])
      .then(([a, s]) => {
        setAlerts(a);
        setSuites(s);
      })
      .finally(() => setLoading(false));
  }, []);

  function openCreate() {
    setEditing(null);
    setFormChannel("slack");
    setFormDest("");
    setFormMetric("pass_rate");
    setFormThreshold("");
    setFormSuiteId("");
    setFormEnabled(true);
    setModalOpen(true);
  }

  function openEdit(alert: AlertConfig) {
    setEditing(alert);
    setFormChannel(alert.channel);
    setFormDest(alert.destination);
    setFormMetric(alert.threshold_metric);
    setFormThreshold(String(alert.threshold_value));
    setFormSuiteId(alert.suite_id || "");
    setFormEnabled(alert.enabled);
    setModalOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload: Partial<AlertConfig> = {
        channel: formChannel as AlertConfig["channel"],
        destination: formDest,
        threshold_metric: formMetric,
        threshold_value: parseFloat(formThreshold),
        suite_id: formSuiteId || undefined,
        enabled: formEnabled,
      };
      if (editing) {
        const updated = await updateAlert(editing.id, payload);
        setAlerts((prev) =>
          prev.map((a) => (a.id === editing.id ? updated : a)),
        );
      } else {
        const created = await createAlert(payload);
        setAlerts((prev) => [...prev, created]);
      }
      setModalOpen(false);
    } catch {
      // error
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this alert configuration?")) return;
    try {
      await deleteAlert(id);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // error
    }
  }

  async function handleToggle(alert: AlertConfig) {
    try {
      const updated = await updateAlert(alert.id, {
        enabled: !alert.enabled,
      });
      setAlerts((prev) =>
        prev.map((a) => (a.id === alert.id ? updated : a)),
      );
    } catch {
      // error
    }
  }

  async function handleTest(alert: AlertConfig) {
    setTesting(alert.id);
    try {
      await testWebhook({
        channel: alert.channel,
        destination: alert.destination,
      });
    } catch {
      // error
    } finally {
      setTesting(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-drift-400" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Alerts</h1>
          <p className="text-gray-400 mt-1">
            Configure notifications for drift events
          </p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus size={16} />
          New Alert
        </button>
      </div>

      {alerts.length > 0 ? (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700">
                <th className="table-header">Channel</th>
                <th className="table-header">Destination</th>
                <th className="table-header">Condition</th>
                <th className="table-header">Suite</th>
                <th className="table-header">Enabled</th>
                <th className="table-header text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => {
                const Icon = channelIcons[alert.channel] || Bell;
                return (
                  <tr
                    key={alert.id}
                    className="border-b border-surface-700/50 hover:bg-surface-800/50 transition-colors"
                  >
                    <td className="table-cell">
                      <div className="flex items-center gap-2">
                        <Icon size={16} className="text-drift-400" />
                        <span className="capitalize">{alert.channel}</span>
                      </div>
                    </td>
                    <td className="table-cell font-mono text-sm text-gray-300 max-w-xs truncate">
                      {alert.destination}
                    </td>
                    <td className="table-cell">
                      <span className="text-gray-200">
                        {alert.threshold_metric} &lt; {alert.threshold_value}
                      </span>
                    </td>
                    <td className="table-cell text-gray-400">
                      {alert.suite_id
                        ? suites.find((s) => s.id === alert.suite_id)?.name ||
                          alert.suite_id.slice(0, 8)
                        : "All"}
                    </td>
                    <td className="table-cell">
                      <button
                        onClick={() => handleToggle(alert)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          alert.enabled ? "bg-drift-600" : "bg-surface-600"
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            alert.enabled ? "translate-x-6" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </td>
                    <td className="table-cell text-right">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => handleTest(alert)}
                          disabled={testing === alert.id}
                          className="p-2 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-gray-200 transition-colors"
                          title="Test webhook"
                        >
                          {testing === alert.id ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <Send size={14} />
                          )}
                        </button>
                        <button
                          onClick={() => openEdit(alert)}
                          className="p-2 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-gray-200 transition-colors"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => handleDelete(alert.id)}
                          className="p-2 rounded-lg hover:bg-red-500/10 text-gray-400 hover:text-red-400 transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card p-16 text-center">
          <Bell className="mx-auto text-gray-600 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-300 mb-2">
            No alerts configured
          </h3>
          <p className="text-gray-500 mb-6">
            Set up notifications to get alerted when evaluation quality drifts.
          </p>
          <button
            onClick={openCreate}
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus size={16} />
            Create Alert
          </button>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="card w-full max-w-lg p-6 mx-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">
                {editing ? "Edit Alert" : "New Alert"}
              </h2>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1 rounded-lg hover:bg-surface-700 text-gray-400"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Channel
                </label>
                <select
                  className="select"
                  value={formChannel}
                  onChange={(e) => setFormChannel(e.target.value)}
                >
                  {channelOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Destination
                </label>
                <input
                  className="input"
                  value={formDest}
                  onChange={(e) => setFormDest(e.target.value)}
                  placeholder={
                    formChannel === "slack"
                      ? "https://hooks.slack.com/..."
                      : formChannel === "email"
                        ? "team@company.com"
                        : "Webhook URL or integration key"
                  }
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">
                    Metric
                  </label>
                  <select
                    className="select"
                    value={formMetric}
                    onChange={(e) => setFormMetric(e.target.value)}
                  >
                    {metricOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">
                    Threshold
                  </label>
                  <input
                    type="number"
                    step="any"
                    className="input"
                    value={formThreshold}
                    onChange={(e) => setFormThreshold(e.target.value)}
                    placeholder="0.8"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Suite Filter
                </label>
                <select
                  className="select"
                  value={formSuiteId}
                  onChange={(e) => setFormSuiteId(e.target.value)}
                >
                  <option value="">All Suites</option>
                  {suites.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setFormEnabled(!formEnabled)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    formEnabled ? "bg-drift-600" : "bg-surface-600"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      formEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
                <span className="text-sm text-gray-300">Enabled</span>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  {saving && <Loader2 size={16} className="animate-spin" />}
                  {editing ? "Update" : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

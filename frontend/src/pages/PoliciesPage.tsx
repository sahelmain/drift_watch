import { useState, useEffect } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  X,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import {
  getPolicies,
  createPolicy,
  updatePolicy,
  deletePolicy,
} from "@/api";
import type { Policy } from "@/types";
import StatusBadge from "@/components/StatusBadge";

const metricOptions = [
  { value: "pass_rate", label: "Pass Rate" },
  { value: "drift_score", label: "Drift Score" },
  { value: "latency_p95", label: "Latency (p95)" },
  { value: "failure_count", label: "Failure Count" },
  { value: "cost_per_run", label: "Cost per Run" },
];

const operatorOptions = [
  { value: "lt", label: "< (less than)" },
  { value: "lte", label: "<= (less or equal)" },
  { value: "gt", label: "> (greater than)" },
  { value: "gte", label: ">= (greater or equal)" },
  { value: "eq", label: "= (equal)" },
];

const actionOptions = [
  { value: "block", label: "Block Deployment" },
  { value: "warn", label: "Warn Only" },
  { value: "notify", label: "Send Notification" },
];

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Policy | null>(null);
  const [saving, setSaving] = useState(false);

  const [formName, setFormName] = useState("");
  const [formMetric, setFormMetric] = useState("pass_rate");
  const [formOperator, setFormOperator] = useState("lt");
  const [formThreshold, setFormThreshold] = useState("");
  const [formAction, setFormAction] = useState("warn");
  const [formEnabled, setFormEnabled] = useState(true);

  useEffect(() => {
    getPolicies()
      .then(setPolicies)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function openCreate() {
    setEditing(null);
    setFormName("");
    setFormMetric("pass_rate");
    setFormOperator("lt");
    setFormThreshold("");
    setFormAction("warn");
    setFormEnabled(true);
    setModalOpen(true);
  }

  function openEdit(policy: Policy) {
    setEditing(policy);
    setFormName(policy.name);
    setFormMetric(policy.metric);
    setFormOperator(policy.operator);
    setFormThreshold(String(policy.threshold));
    setFormAction(policy.action);
    setFormEnabled(policy.enabled);
    setModalOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: formName,
        metric: formMetric,
        operator: formOperator as Policy["operator"],
        threshold: parseFloat(formThreshold),
        action: formAction as Policy["action"],
        enabled: formEnabled,
      };
      if (editing) {
        const updated = await updatePolicy(editing.id, payload);
        setPolicies((prev) =>
          prev.map((p) => (p.id === editing.id ? updated : p)),
        );
      } else {
        const created = await createPolicy(payload);
        setPolicies((prev) => [...prev, created]);
      }
      setModalOpen(false);
    } catch {
      // error
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this policy?")) return;
    try {
      await deletePolicy(id);
      setPolicies((prev) => prev.filter((p) => p.id !== id));
    } catch {
      // error
    }
  }

  async function handleToggle(policy: Policy) {
    try {
      const updated = await updatePolicy(policy.id, {
        enabled: !policy.enabled,
      });
      setPolicies((prev) =>
        prev.map((p) => (p.id === policy.id ? updated : p)),
      );
    } catch {
      // error
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
          <h1 className="text-2xl font-bold text-white">Quality Policies</h1>
          <p className="text-gray-400 mt-1">
            Define quality gates for your LLM evaluations
          </p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus size={16} />
          New Policy
        </button>
      </div>

      {policies.length > 0 ? (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700">
                <th className="table-header">Name</th>
                <th className="table-header">Rule</th>
                <th className="table-header">Action</th>
                <th className="table-header">Enabled</th>
                <th className="table-header text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((policy) => (
                <tr
                  key={policy.id}
                  className="border-b border-surface-700/50 hover:bg-surface-800/50 transition-colors"
                >
                  <td className="table-cell font-medium text-white">
                    {policy.name}
                  </td>
                  <td className="table-cell">
                    <code className="text-sm text-gray-300 bg-surface-900 px-2 py-1 rounded">
                      {policy.metric} {policy.operator} {policy.threshold}
                    </code>
                  </td>
                  <td className="table-cell">
                    <StatusBadge status={policy.action} />
                  </td>
                  <td className="table-cell">
                    <button
                      onClick={() => handleToggle(policy)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        policy.enabled ? "bg-drift-600" : "bg-surface-600"
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          policy.enabled ? "translate-x-6" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </td>
                  <td className="table-cell text-right">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => openEdit(policy)}
                        className="p-2 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-gray-200 transition-colors"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(policy.id)}
                        className="p-2 rounded-lg hover:bg-red-500/10 text-gray-400 hover:text-red-400 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card p-16 text-center">
          <ShieldCheck className="mx-auto text-gray-600 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-300 mb-2">
            No policies defined
          </h3>
          <p className="text-gray-500 mb-6 max-w-md mx-auto">
            Quality policies act as gates — block deployments, warn, or notify
            when evaluation metrics cross thresholds.
          </p>
          <button
            onClick={openCreate}
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus size={16} />
            Create Policy
          </button>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="card w-full max-w-lg p-6 mx-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">
                {editing ? "Edit Policy" : "New Policy"}
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
                  Policy Name
                </label>
                <input
                  className="input"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="Minimum Pass Rate"
                  required
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
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
                    Operator
                  </label>
                  <select
                    className="select"
                    value={formOperator}
                    onChange={(e) => setFormOperator(e.target.value)}
                  >
                    {operatorOptions.map((o) => (
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
                  Action
                </label>
                <select
                  className="select"
                  value={formAction}
                  onChange={(e) => setFormAction(e.target.value)}
                >
                  {actionOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
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

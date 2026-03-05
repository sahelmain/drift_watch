import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  Pencil,
  Trash2,
  X,
  Loader2,
  FlaskConical,
  Clock,
  Play,
} from "lucide-react";
import { format } from "date-fns";
import {
  getSuites,
  createSuite,
  updateSuite,
  deleteSuite,
  triggerRun,
} from "@/api";
import type { Suite } from "@/types";

export default function SuitesPage() {
  const [suites, setSuites] = useState<Suite[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Suite | null>(null);
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formYaml, setFormYaml] = useState("");
  const [formSchedule, setFormSchedule] = useState("");
  const [saving, setSaving] = useState(false);
  const [runningSuiteId, setRunningSuiteId] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadSuites();
  }, []);

  async function loadSuites() {
    try {
      const data = await getSuites();
      setSuites(data);
    } catch {
      // empty state
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setFormName("");
    setFormDescription("");
    setFormYaml("");
    setFormSchedule("");
    setModalOpen(true);
  }

  function openEdit(suite: Suite) {
    setEditing(suite);
    setFormName(suite.name);
    setFormDescription(suite.description || "");
    setFormYaml(suite.yaml_content || "");
    setFormSchedule(suite.schedule_cron || "");
    setModalOpen(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: formName,
        description: formDescription,
        yaml_content: formYaml,
        schedule_cron: formSchedule || undefined,
      };
      if (editing) {
        await updateSuite(editing.id, payload);
      } else {
        await createSuite(payload);
      }
      setModalOpen(false);
      await loadSuites();
    } catch {
      // error handling
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to delete this suite?")) return;
    try {
      await deleteSuite(id);
      setSuites((prev) => prev.filter((s) => s.id !== id));
    } catch {
      // error
    }
  }

  async function handleRun(id: string) {
    if (runningSuiteId === id) return;
    setRunError(null);
    setRunningSuiteId(id);
    try {
      const run = await triggerRun(id);
      navigate(`/runs/${run.id}`);
    } catch (error) {
      setRunError(
        error instanceof Error ? error.message : "Unable to start the run.",
      );
    } finally {
      setRunningSuiteId(null);
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
          <h1 className="text-2xl font-bold text-white">Test Suites</h1>
          <p className="text-gray-400 mt-1">
            Manage your LLM evaluation test suites
          </p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus size={16} />
          New Suite
        </button>
      </div>

      {runError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {runError}
        </div>
      )}

      {suites.length > 0 ? (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700">
                <th className="table-header">Name</th>
                <th className="table-header">Schedule</th>
                <th className="table-header">Created</th>
                <th className="table-header text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {suites.map((suite) => (
                <tr
                  key={suite.id}
                  className="border-b border-surface-700/50 hover:bg-surface-800/50 cursor-pointer transition-colors"
                  onClick={() => navigate(`/timeline?suite=${suite.id}`)}
                >
                  <td className="table-cell">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-drift-500/10 flex items-center justify-center shrink-0">
                        <FlaskConical size={16} className="text-drift-400" />
                      </div>
                      <div>
                        <p className="font-medium text-white">{suite.name}</p>
                        {suite.description && (
                          <p className="text-xs text-gray-500 mt-0.5 truncate max-w-xs">
                            {suite.description}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="table-cell">
                    {suite.schedule_cron ? (
                      <span className="flex items-center gap-1.5 text-gray-300">
                        <Clock size={13} className="text-gray-500" />
                        {suite.schedule_cron}
                      </span>
                    ) : (
                      <span className="text-gray-500">Manual</span>
                    )}
                  </td>
                  <td className="table-cell text-gray-400">
                    {format(new Date(suite.created_at), "MMM dd, HH:mm")}
                  </td>
                  <td className="table-cell text-right">
                    <div
                      className="flex items-center gap-1 justify-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => handleRun(suite.id)}
                        disabled={runningSuiteId === suite.id}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-drift-500/10 px-3 py-2 text-sm font-medium text-drift-300 transition-colors hover:bg-drift-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {runningSuiteId === suite.id ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <Play size={14} />
                        )}
                        {runningSuiteId === suite.id ? "Running" : "Run"}
                      </button>
                      <button
                        onClick={() => openEdit(suite)}
                        className="p-2 rounded-lg hover:bg-surface-700 text-gray-400 hover:text-gray-200 transition-colors"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(suite.id)}
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
          <FlaskConical className="mx-auto text-gray-600 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-300 mb-2">
            No test suites yet
          </h3>
          <p className="text-gray-500 mb-6 max-w-md mx-auto">
            Create your first test suite to start monitoring LLM evaluation
            drift.
          </p>
          <button
            onClick={openCreate}
            className="btn-primary inline-flex items-center gap-2"
          >
            <Plus size={16} />
            Create Suite
          </button>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="card w-full max-w-xl p-6 mx-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">
                {editing ? "Edit Suite" : "New Suite"}
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
                  Name
                </label>
                <input
                  className="input"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="My Test Suite"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Description
                </label>
                <input
                  className="input"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Optional description"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Config (YAML)
                </label>
                <textarea
                  className="input font-mono text-sm min-h-[200px] resize-y"
                  value={formYaml}
                  onChange={(e) => setFormYaml(e.target.value)}
                  placeholder={`tests:\n  - name: "Greeting test"\n    prompt: "Say hello"\n    model: "gpt-4"\n    assertions:\n      - type: contains\n        value: "hello"`}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Schedule (cron)
                </label>
                <input
                  className="input"
                  value={formSchedule}
                  onChange={(e) => setFormSchedule(e.target.value)}
                  placeholder="0 */6 * * * (optional)"
                />
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

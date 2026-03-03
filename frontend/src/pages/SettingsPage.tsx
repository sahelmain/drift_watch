import { useState, useEffect } from "react";
import {
  Settings,
  Key,
  Users,
  CreditCard,
  FileText,
  Plus,
  Trash2,
  Copy,
  Loader2,
  Check,
} from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import {
  getSettings,
  updateSettings,
  createApiKey,
  revokeApiKey,
  inviteMember,
  getAuditLog,
} from "@/api";
import type { OrgSettings, AuditEvent, PaginatedResponse } from "@/types";

const tabs = [
  { id: "general", label: "General", icon: Settings },
  { id: "keys", label: "API Keys", icon: Key },
  { id: "members", label: "Members", icon: Users },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "audit", label: "Audit Log", icon: FileText },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("general");
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");

  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState("");
  const [creatingKey, setCreatingKey] = useState(false);
  const [copied, setCopied] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);

  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);

  useEffect(() => {
    getSettings()
      .then((s) => {
        setSettings(s);
        setOrgName(s.org.name);
        setOrgSlug(s.org.slug);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (activeTab === "audit") {
      getAuditLog({ page: auditPage, limit: 20 })
        .then((res: PaginatedResponse<AuditEvent>) => {
          setAuditEvents(res.items);
          setAuditTotal(res.total);
        })
        .catch(() => {});
    }
  }, [activeTab, auditPage]);

  async function handleSaveGeneral(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateSettings({
        org: { ...settings!.org, name: orgName, slug: orgSlug },
      });
      setSettings(updated);
    } catch {
      // error
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateKey(e: React.FormEvent) {
    e.preventDefault();
    setCreatingKey(true);
    try {
      const res = await createApiKey(newKeyName);
      setCreatedKey(res.key);
      setNewKeyName("");
      const updated = await getSettings();
      setSettings(updated);
    } catch {
      // error
    } finally {
      setCreatingKey(false);
    }
  }

  async function handleRevokeKey(id: string) {
    if (!confirm("Revoke this API key? This cannot be undone.")) return;
    try {
      await revokeApiKey(id);
      setSettings((prev) =>
        prev
          ? {
              ...prev,
              api_keys: prev.api_keys.filter((k) => k.id !== id),
            }
          : prev,
      );
    } catch {
      // error
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    try {
      await inviteMember(inviteEmail, inviteRole);
      setInviteEmail("");
      const updated = await getSettings();
      setSettings(updated);
    } catch {
      // error
    } finally {
      setInviting(false);
    }
  }

  function copyKey() {
    navigator.clipboard.writeText(createdKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-gray-400 mt-1">
          Manage your organization and preferences
        </p>
      </div>

      <div className="flex gap-6">
        <nav className="w-48 shrink-0 space-y-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                "flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "bg-drift-600/20 text-drift-400"
                  : "text-gray-400 hover:text-gray-200 hover:bg-surface-800",
              )}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="flex-1 min-w-0">
          {activeTab === "general" && (
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-white mb-6">
                Organization
              </h2>
              <form onSubmit={handleSaveGeneral} className="space-y-4 max-w-md">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">
                    Name
                  </label>
                  <input
                    className="input"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">
                    Slug
                  </label>
                  <input
                    className="input"
                    value={orgSlug}
                    onChange={(e) => setOrgSlug(e.target.value)}
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={saving}
                  className="btn-primary flex items-center gap-2"
                >
                  {saving && <Loader2 size={16} className="animate-spin" />}
                  Save Changes
                </button>
              </form>
            </div>
          )}

          {activeTab === "keys" && (
            <div className="space-y-6">
              <div className="card p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Create API Key
                </h2>
                <form
                  onSubmit={handleCreateKey}
                  className="flex items-end gap-3"
                >
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">
                      Key Name
                    </label>
                    <input
                      className="input"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      placeholder="Production CI"
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={creatingKey}
                    className="btn-primary flex items-center gap-2"
                  >
                    {creatingKey ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Plus size={16} />
                    )}
                    Create
                  </button>
                </form>

                {createdKey && (
                  <div className="mt-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
                    <p className="text-sm text-emerald-400 mb-2">
                      Copy this key now — it won't be shown again.
                    </p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 bg-surface-900 px-3 py-2 rounded text-sm font-mono text-white break-all">
                        {createdKey}
                      </code>
                      <button
                        onClick={copyKey}
                        className="btn-secondary flex items-center gap-1.5 shrink-0"
                      >
                        {copied ? (
                          <Check size={14} />
                        ) : (
                          <Copy size={14} />
                        )}
                        {copied ? "Copied" : "Copy"}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="card overflow-hidden">
                <div className="p-6 pb-0">
                  <h2 className="text-lg font-semibold text-white">
                    Active Keys
                  </h2>
                </div>
                {settings?.api_keys && settings.api_keys.length > 0 ? (
                  <table className="w-full mt-4">
                    <thead>
                      <tr className="border-b border-surface-700">
                        <th className="table-header">Name</th>
                        <th className="table-header">Prefix</th>
                        <th className="table-header">Created</th>
                        <th className="table-header">Last Used</th>
                        <th className="table-header text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {settings.api_keys.map((key) => (
                        <tr
                          key={key.id}
                          className="border-b border-surface-700/50"
                        >
                          <td className="table-cell font-medium text-white">
                            {key.name}
                          </td>
                          <td className="table-cell font-mono text-sm text-gray-400">
                            {key.prefix}...
                          </td>
                          <td className="table-cell text-gray-400">
                            {format(new Date(key.created_at), "MMM dd, yyyy")}
                          </td>
                          <td className="table-cell text-gray-400">
                            {key.last_used_at
                              ? format(
                                  new Date(key.last_used_at),
                                  "MMM dd, yyyy",
                                )
                              : "Never"}
                          </td>
                          <td className="table-cell text-right">
                            <button
                              onClick={() => handleRevokeKey(key.id)}
                              className="p-2 rounded-lg hover:bg-red-500/10 text-gray-400 hover:text-red-400 transition-colors"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="p-12 text-center text-gray-500">
                    No API keys created yet.
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "members" && (
            <div className="space-y-6">
              <div className="card p-6">
                <h2 className="text-lg font-semibold text-white mb-4">
                  Invite Member
                </h2>
                <form onSubmit={handleInvite} className="flex items-end gap-3">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">
                      Email
                    </label>
                    <input
                      type="email"
                      className="input"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="colleague@company.com"
                      required
                    />
                  </div>
                  <div className="w-40">
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">
                      Role
                    </label>
                    <select
                      className="select"
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                    >
                      <option value="viewer">Viewer</option>
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                  <button
                    type="submit"
                    disabled={inviting}
                    className="btn-primary flex items-center gap-2"
                  >
                    {inviting ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Plus size={16} />
                    )}
                    Invite
                  </button>
                </form>
              </div>

              <div className="card overflow-hidden">
                <div className="p-6 pb-0">
                  <h2 className="text-lg font-semibold text-white">Members</h2>
                </div>
                {settings?.members && settings.members.length > 0 ? (
                  <table className="w-full mt-4">
                    <thead>
                      <tr className="border-b border-surface-700">
                        <th className="table-header">Email</th>
                        <th className="table-header">Role</th>
                        <th className="table-header">Joined</th>
                      </tr>
                    </thead>
                    <tbody>
                      {settings.members.map((member) => (
                        <tr
                          key={member.id}
                          className="border-b border-surface-700/50"
                        >
                          <td className="table-cell">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full bg-drift-500/20 flex items-center justify-center text-drift-400 text-sm font-medium">
                                {member.email.charAt(0).toUpperCase()}
                              </div>
                              <span className="text-white">{member.email}</span>
                            </div>
                          </td>
                          <td className="table-cell capitalize text-gray-300">
                            {member.role}
                          </td>
                          <td className="table-cell text-gray-400">
                            {format(
                              new Date(member.created_at),
                              "MMM dd, yyyy",
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="p-12 text-center text-gray-500">
                    No members yet.
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "billing" && (
            <div className="space-y-6">
              <div className="card p-6">
                <h2 className="text-lg font-semibold text-white mb-6">
                  Current Plan
                </h2>
                <div className="flex items-center gap-4 mb-6">
                  <div className="bg-gradient-to-br from-drift-500 to-drift-700 text-white text-sm font-bold px-4 py-2 rounded-lg uppercase tracking-wider">
                    {settings?.org.plan || "Free"}
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="bg-surface-900 rounded-xl p-4 border border-surface-700">
                    <p className="text-sm text-gray-400">Runs This Month</p>
                    <p className="text-2xl font-bold text-white mt-1">
                      {settings?.usage.runs_this_month || 0}
                    </p>
                    <div className="mt-2 h-1.5 bg-surface-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-drift-500 rounded-full transition-all"
                        style={{
                          width: `${Math.min(
                            ((settings?.usage.runs_this_month || 0) /
                              (settings?.usage.plan_limit || 1000)) *
                              100,
                            100,
                          )}%`,
                        }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      of {settings?.usage.plan_limit || 1000} limit
                    </p>
                  </div>
                  <div className="bg-surface-900 rounded-xl p-4 border border-surface-700">
                    <p className="text-sm text-gray-400">Active Suites</p>
                    <p className="text-2xl font-bold text-white mt-1">
                      {settings?.usage.suites_count || 0}
                    </p>
                  </div>
                  <div className="bg-surface-900 rounded-xl p-4 border border-surface-700">
                    <p className="text-sm text-gray-400">Team Members</p>
                    <p className="text-2xl font-bold text-white mt-1">
                      {settings?.members?.length || 0}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "audit" && (
            <div className="card overflow-hidden">
              <div className="p-6 pb-0">
                <h2 className="text-lg font-semibold text-white">
                  Audit Log
                </h2>
                <p className="text-gray-400 text-sm mt-1">
                  {auditTotal} total events
                </p>
              </div>
              {auditEvents.length > 0 ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full mt-4">
                      <thead>
                        <tr className="border-b border-surface-700">
                          <th className="table-header">Action</th>
                          <th className="table-header">User</th>
                          <th className="table-header">Resource</th>
                          <th className="table-header">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody>
                        {auditEvents.map((ev) => (
                          <tr
                            key={ev.id}
                            className="border-b border-surface-700/50"
                          >
                            <td className="table-cell">
                              <span className="font-mono text-sm text-drift-400">
                                {ev.action}
                              </span>
                            </td>
                            <td className="table-cell text-gray-300">
                              {ev.user_email || "—"}
                            </td>
                            <td className="table-cell">
                              <span className="text-gray-300">
                                {ev.resource_type}
                              </span>
                              <span className="text-gray-500 font-mono text-xs ml-1">
                                {ev.resource_id?.slice(0, 8)}
                              </span>
                            </td>
                            <td className="table-cell text-gray-400">
                              {format(
                                new Date(ev.created_at),
                                "MMM dd, yyyy HH:mm:ss",
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="p-4 flex items-center justify-between border-t border-surface-700">
                    <button
                      onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                      disabled={auditPage <= 1}
                      className="btn-secondary text-sm"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-gray-400">
                      Page {auditPage} of {Math.ceil(auditTotal / 20) || 1}
                    </span>
                    <button
                      onClick={() => setAuditPage((p) => p + 1)}
                      disabled={auditPage >= Math.ceil(auditTotal / 20)}
                      className="btn-secondary text-sm"
                    >
                      Next
                    </button>
                  </div>
                </>
              ) : (
                <div className="p-12 text-center text-gray-500">
                  No audit events recorded yet.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

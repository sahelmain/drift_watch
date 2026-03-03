import clsx from "clsx";

const variants: Record<string, string> = {
  passed: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  failed: "bg-red-500/15 text-red-400 border-red-500/30",
  running: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  pending: "bg-gray-500/15 text-gray-400 border-gray-500/30",
  error: "bg-red-500/15 text-red-400 border-red-500/30",
  sent: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  block: "bg-red-500/15 text-red-400 border-red-500/30",
  warn: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  notify: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};

export default function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border capitalize",
        variants[status] || variants.pending,
        className,
      )}
    >
      <span
        className={clsx("w-1.5 h-1.5 rounded-full", {
          "bg-emerald-400": status === "passed" || status === "sent",
          "bg-red-400": status === "failed" || status === "error" || status === "block",
          "bg-amber-400 animate-pulse": status === "running" || status === "warn",
          "bg-gray-400": status === "pending",
          "bg-blue-400": status === "notify",
        })}
      />
      {status}
    </span>
  );
}

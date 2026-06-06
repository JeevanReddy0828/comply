import type { ControlStatus } from "../api/types";

const MAP: Record<ControlStatus, { cls: string; label: string }> = {
  SATISFIED: { cls: "ok", label: "Satisfied" },
  PARTIAL: { cls: "warn", label: "Partial" },
  MISSING: { cls: "bad", label: "Missing" },
};

export function StatusBadge({ status }: { status: ControlStatus }) {
  const { cls, label } = MAP[status] ?? { cls: "neutral", label: status };
  return (
    <span className={`badge ${cls}`}>
      <span className="dot" />
      {label}
    </span>
  );
}

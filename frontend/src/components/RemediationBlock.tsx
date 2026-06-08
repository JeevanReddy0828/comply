import { useState } from "react";
import type { RemediationTask, TaskUpdate, User } from "../api/types";

const STATUS_LABEL: Record<string, string> = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  RESOLVED: "Resolved",
};

function ownerLabel(users: User[], id: string | null): string {
  if (!id) return "Unassigned";
  const u = users.find((x) => x.id === id);
  return u ? u.name || u.email : "Unknown";
}

export function RemediationBlock({
  controlId,
  task,
  users,
  onCreate,
  onUpdate,
}: {
  controlId: string;
  task: RemediationTask | undefined;
  users: User[];
  onCreate: (controlId: string, ownerId: string | null, dueDate: string | null) => void;
  onUpdate: (taskId: string, patch: TaskUpdate) => void;
}) {
  if (task) {
    return (
      <div className="task-block">
        <div className="task-head">
          <span className="task-title">Remediation task</span>
          <span className={`badge task-${task.status.toLowerCase()}`}>
            {STATUS_LABEL[task.status] ?? task.status}
          </span>
        </div>
        <div className="task-fields">
          <label>
            Owner
            <select
              value={task.owner_id ?? ""}
              onChange={(e) => onUpdate(task.id, { owner_id: e.target.value || null })}
            >
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name || u.email}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select value={task.status} onChange={(e) => onUpdate(task.id, { status: e.target.value as TaskUpdate["status"] })}>
              <option value="OPEN">Open</option>
              <option value="IN_PROGRESS">In progress</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </label>
          <label>
            Due
            <input
              type="date"
              value={task.due_date ?? ""}
              onChange={(e) => onUpdate(task.id, { due_date: e.target.value || null })}
            />
          </label>
        </div>
        <div className="task-meta subtle">
          Owner: {ownerLabel(users, task.owner_id)}
          {task.source_gap_reason ? ` · opened for: ${task.source_gap_reason}` : ""}
        </div>
      </div>
    );
  }
  return <CreateTaskForm controlId={controlId} users={users} onCreate={onCreate} />;
}

function CreateTaskForm({
  controlId,
  users,
  onCreate,
}: {
  controlId: string;
  users: User[];
  onCreate: (controlId: string, ownerId: string | null, dueDate: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState("");

  if (!open) {
    return (
      <div className="task-block">
        <button className="secondary" onClick={() => setOpen(true)}>
          Assign owner &amp; track
        </button>
      </div>
    );
  }

  return (
    <div className="task-block">
      <div className="task-head">
        <span className="task-title">New remediation task</span>
      </div>
      <div className="task-fields">
        <label>
          Owner
          <select value={owner} onChange={(e) => setOwner(e.target.value)}>
            <option value="">Unassigned</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name || u.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          Due
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <button
          className="primary"
          onClick={() => {
            onCreate(controlId, owner || null, due || null);
            setOpen(false);
          }}
        >
          Create task
        </button>
      </div>
    </div>
  );
}

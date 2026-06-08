import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Organization, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";

function fmtDate(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toISOString().slice(0, 10);
}

function capLabel(c: string): string {
  return c.replace(/^can_/, "").replace(/_/g, " ");
}

export function ProfilePage() {
  const { user } = useAuth();
  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getOrganization()
      .then(setOrg)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load organization."));
    api.listUsers().then(setMembers).catch(() => setMembers([]));
  }, []);

  if (!user) return <div className="center-muted">Loading…</div>;

  return (
    <div className="container">
      <div style={{ marginBottom: "1rem" }}>
        <Link to="/" className="subtle">← Dashboard</Link>
      </div>
      <h1 style={{ marginBottom: "1.5rem" }}>Profile</h1>

      {error && <div className="notice warn" style={{ marginBottom: "1rem" }}>{error}</div>}

      <div className="profile-grid">
        <div className="card profile-card">
          <h2>Account</h2>
          <dl className="kv">
            <div><dt>Name</dt><dd>{user.name || "—"}</dd></div>
            <div><dt>Email</dt><dd>{user.email}</dd></div>
            <div><dt>Role</dt><dd><span className="badge neutral">{user.role}</span></dd></div>
          </dl>
          <div className="caps">
            <div className="caps-label">Capabilities</div>
            {user.capabilities.length === 0 ? (
              <span className="muted">None</span>
            ) : (
              <div className="cap-chips">
                {user.capabilities.map((c) => (
                  <span key={c} className="cap-chip">{capLabel(c)}</span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="card profile-card">
          <h2>Organization</h2>
          <dl className="kv">
            <div><dt>Name</dt><dd>{org?.name ?? "…"}</dd></div>
            <div><dt>Members</dt><dd>{org?.member_count ?? members.length}</dd></div>
            <div><dt>Created</dt><dd>{org ? fmtDate(org.created_at) : "…"}</dd></div>
          </dl>
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2 style={{ marginBottom: "0.75rem" }}>Members</h2>
        <table className="controls-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th style={{ width: "10rem" }}>Role</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id}>
                <td className="name">
                  {m.name || "—"}
                  {m.id === user.id && <span className="muted"> (you)</span>}
                </td>
                <td>{m.email}</td>
                <td>{m.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

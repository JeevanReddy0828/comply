import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [org, setOrg] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // already signed in → bounce to dashboard
  if (user) return <Navigate to="/" replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") {
        await register(org, email, password, name);
      } else {
        await login(email, password);
      }
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <h1>Comply</h1>
      <p className="tagline muted">EU AI Act compliance, with the evidence to prove it.</p>
      <div className="card auth-card">
        <form onSubmit={submit} className="stack">
          {mode === "register" && (
            <div className="field">
              <label htmlFor="org">Organization</label>
              <input id="org" value={org} onChange={(e) => setOrg(e.target.value)} required autoFocus />
            </div>
          )}
          {mode === "register" && (
            <div className="field">
              <label htmlFor="name">Your name</label>
              <input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
          )}
          <div className="field">
            <label htmlFor="email">Work email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus={mode === "login"}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button type="submit" className="primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
          </button>
        </form>
        <div className="auth-toggle muted">
          {mode === "register" ? (
            <>
              Already have an account?{" "}
              <button className="link" onClick={() => { setMode("login"); setError(null); }}>
                Sign in
              </button>
            </>
          ) : (
            <>
              New to Comply?{" "}
              <button className="link" onClick={() => { setMode("register"); setError(null); }}>
                Create an account
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="row" style={{ gap: "1.25rem" }}>
          <Link to="/" className="brand">
            Comply
          </Link>
          <Link to="/guard" className="muted">
            Guard
          </Link>
          <Link to="/ask" className="muted">
            Ask
          </Link>
        </div>
        <div className="header-right">
          {user && (
            <>
              <span className="subtle">{user.email}</span>
              <button
                className="link"
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
              >
                Sign out
              </button>
            </>
          )}
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

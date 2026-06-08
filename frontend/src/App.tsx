import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { CatalogProvider } from "./catalog/CatalogContext";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { RegisterSystemPage } from "./pages/RegisterSystemPage";
import { SystemDetailPage } from "./pages/SystemDetailPage";
import { ReportPage } from "./pages/ReportPage";
import { GuardPage } from "./pages/GuardPage";
import { AskPage } from "./pages/AskPage";
import { ProfilePage } from "./pages/ProfilePage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-muted">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <CatalogProvider>
                  <Layout />
                </CatalogProvider>
              </RequireAuth>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/systems/new" element={<RegisterSystemPage />} />
            <Route path="/systems/:id" element={<SystemDetailPage />} />
            <Route path="/systems/:id/report" element={<ReportPage />} />
            <Route path="/guard" element={<GuardPage />} />
            <Route path="/ask" element={<AskPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

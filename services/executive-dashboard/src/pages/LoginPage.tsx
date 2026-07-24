import { FormEvent, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { getToken, login } from "../lib/auth";

export function LoginPage() {
  const [username, setUsername] = useState("operator");
  const [password, setPassword] = useState("operator123");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();

  if (getToken()) {
    return <Navigate to={params.get("next") || "/"} replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate(params.get("next") || "/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="brand-mark">AI SRE Copilot</div>
        <h1>Sign in</h1>
        <p className="muted">JWT + RBAC for the executive console.</p>
        {error && <div className="error-banner">{error}</div>}
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="muted" style={{ fontSize: "0.8rem", marginTop: "1rem" }}>
          Demo: admin / operator / viewer (see docs)
        </p>
      </form>
    </div>
  );
}

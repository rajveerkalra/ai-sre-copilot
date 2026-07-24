import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { clearSession, getSessionUser } from "../lib/auth";
import { getOperator, setOperator } from "../lib/metrics";

export function Shell() {
  const [operator, setOp] = useState(getOperator());
  const user = getSessionUser();
  const navigate = useNavigate();

  useEffect(() => {
    setOperator(operator);
  }, [operator]);

  useEffect(() => {
    if (user?.username && !localStorage.getItem("sre_operator")) {
      setOp(user.username);
      setOperator(user.username);
    }
  }, [user?.username]);

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <div className="brand">
          <div className="brand-mark">AI SRE Copilot</div>
          <p className="brand-name">Executive</p>
        </div>
        <nav className="nav-links">
          <NavLink to="/" end>
            Overview
          </NavLink>
          <NavLink to="/incidents">Incidents</NavLink>
          <NavLink to="/remediations">Remediation queue</NavLink>
        </nav>
        <div className="nav-foot">
          <label htmlFor="operator">Operator</label>
          <input
            id="operator"
            value={operator}
            onChange={(e) => setOp(e.target.value)}
            aria-label="Operator name for approvals"
          />
          <p className="muted" style={{ fontSize: "0.75rem", margin: "0.5rem 0" }}>
            Signed in as <strong>{user?.username || "—"}</strong>
            {user?.roles?.length ? ` (${user.roles.join(", ")})` : ""}
          </p>
          <button
            type="button"
            className="btn"
            style={{ width: "100%" }}
            onClick={() => {
              clearSession();
              navigate("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}

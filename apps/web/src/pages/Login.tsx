import { useState } from "react";
import { Navigate } from "react-router-dom";
import { EmailCodeForm, PasswordForm, useSignInResult } from "../components/SignInSteps";
import { homePath, useAuth } from "../lib/auth";

export function Login() {
  const { user } = useAuth();
  const { handle, view } = useSignInResult();
  const [mode, setMode] = useState<"password" | "code">("password");

  if (user) return <Navigate to={homePath(user)} replace />;
  return (
    <AuthCard>
      {view ?? (
        <>
          <h2>Sign in</h2>
          <div className="tabs">
            <button className={mode === "password" ? "tab active" : "tab"} onClick={() => setMode("password")}>
              Password
            </button>
            <button className={mode === "code" ? "tab active" : "tab"} onClick={() => setMode("code")}>
              Email code
            </button>
          </div>
          {mode === "password" ? <PasswordForm onResult={handle} /> : <EmailCodeForm onResult={handle} />}
        </>
      )}
    </AuthCard>
  );
}

export function AuthCard({ children }: { children: React.ReactNode }) {
  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="brand">PERSONA_FORGE</div>
        {children}
      </div>
    </main>
  );
}

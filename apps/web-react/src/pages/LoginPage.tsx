import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { getProfile } from "../api/financeApi";
import { useAuth } from "../auth/useAuth";
import AuthLayout from "../components/AuthLayout";
import Button from "../components/Button";
import ErrorBox from "../components/ErrorBox";
import Field from "../components/Field";
import Notice from "../components/Notice";
import { ROUTES, type AuthRedirectState } from "../lib/routes";
import { validateEmail, validateLoginPassword } from "../lib/validation";

const loginRateLimitMessage = (seconds: number) => `Çok fazla deneme. ${seconds} saniye sonra tekrar deneyin.`;

// a "from" that is not an app path (or is an auth page) is ignored
function safeFrom(state: unknown): string | null {
  const from = (state as AuthRedirectState | null)?.from;
  if (typeof from !== "string" || !from.startsWith("/") || from.startsWith("//")) return null;
  if (from === ROUTES.login || from === ROUTES.register || from === ROUTES.home) return null;
  return from;
}

export default function LoginPage() {
  const { session, login, notice, clearNotice } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // only a session that existed when the page opened redirects; a fresh sign-in navigates below
  const [signedInOnArrival] = useState(() => session !== null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string | null; password?: string | null }>({});
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  if (signedInOnArrival) return <Navigate to={ROUTES.dashboard} replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors = { email: validateEmail(email), password: validateLoginPassword(password) };
    setFieldErrors(errors);
    if (errors.email || errors.password) return;

    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
      // new users (no profile yet, 404) start with the profile form; everyone else goes where they wanted to go
      let destination: string = ROUTES.profile;
      try {
        const profile = await getProfile();
        if (profile) destination = safeFrom(location.state) ?? ROUTES.dashboard;
      } catch {
        // Finance is down: the profile page shows the error with a retry button
      }
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err);
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="Giriş yap"
      footer={
        <>
          Hesabın yok mu? <Link to={ROUTES.register}>Kayıt ol</Link>
        </>
      }
    >
      <form className="form" onSubmit={handleSubmit} noValidate aria-label="Giriş formu">
        {notice ? (
          <Notice tone="warning">
            {notice}{" "}
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearNotice}>
              Kapat
            </button>
          </Notice>
        ) : null}
        <Field
          label="E-posta"
          type="email"
          name="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
          placeholder="ornek@eposta.com"
          required
          autoFocus
        />
        <Field
          label="Şifre"
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          required
        />
        <ErrorBox error={error} rateLimitMessage={loginRateLimitMessage} onRateLimitDone={() => setError(null)} />
        <Button type="submit" variant="primary" block loading={submitting} loadingLabel="Giriş yapılıyor…">
          Giriş yap
        </Button>
      </form>
    </AuthLayout>
  );
}

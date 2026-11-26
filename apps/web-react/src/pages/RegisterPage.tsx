import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import AuthLayout from "../components/AuthLayout";
import Button from "../components/Button";
import ErrorBox from "../components/ErrorBox";
import Field from "../components/Field";
import { ROUTES } from "../lib/routes";
import { PASSWORD_MAX, PASSWORD_MIN, validateEmail, validateNewPassword } from "../lib/validation";

interface FieldErrors {
  email?: string | null;
  password?: string | null;
  confirm?: string | null;
}

export default function RegisterPage() {
  const { session, register } = useAuth();
  const navigate = useNavigate();
  const [signedInOnArrival] = useState(() => session !== null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  if (signedInOnArrival) return <Navigate to={ROUTES.dashboard} replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const errors: FieldErrors = {
      email: validateEmail(email),
      password: validateNewPassword(password),
      confirm: confirm === password ? null : "Şifreler aynı değil.",
    };
    setFieldErrors(errors);
    if (errors.email || errors.password || errors.confirm) return;

    setSubmitting(true);
    setError(null);
    try {
      await register(email.trim(), password);
      // a new account has no financial profile yet
      navigate(ROUTES.profile, { replace: true });
    } catch (err) {
      setError(err);
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="Hesap oluştur"
      footer={
        <>
          Zaten hesabın var mı? <Link to={ROUTES.login}>Giriş yap</Link>
        </>
      }
    >
      <form className="form" onSubmit={handleSubmit} noValidate aria-label="Kayıt formu">
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
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          hint={`${PASSWORD_MIN}–${PASSWORD_MAX} karakter`}
          maxLength={PASSWORD_MAX}
          required
        />
        <Field
          label="Şifre (tekrar)"
          type="password"
          name="confirmPassword"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={fieldErrors.confirm}
          maxLength={PASSWORD_MAX}
          required
        />
        <ErrorBox error={error} onRateLimitDone={() => setError(null)} />
        <Button type="submit" variant="primary" block loading={submitting} loadingLabel="Hesap oluşturuluyor…">
          Kayıt ol
        </Button>
      </form>
    </AuthLayout>
  );
}

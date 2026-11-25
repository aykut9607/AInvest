import { useState, type FormEvent } from "react";
import { authenticate, type Session } from "./api";
import { problem } from "./text";
import { Banner, Button } from "./ui";

export default function AuthPage({ onSession, notice }: { onSession: (session: Session) => void; notice: string }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<unknown>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setFailed(null);
    try {
      onSession(await authenticate(mode === "login" ? "/auth/login" : "/auth/register", { email: email.trim(), password }));
    } catch (error) {
      setFailed(error);
      setBusy(false);
    }
  };
  const title = mode === "login" ? "Giriş yap" : "Kayıt ol";

  return (
    <main className="pf-auth">
      <div className="pf-brand pf-brand-big">
        <i>AI</i> AInvest
      </div>
      <p className="pf-note">Finansal IQ'na uygun portföy dağılımını gör.</p>
      <form className="pf-card" onSubmit={submit}>
        <h2>{title}</h2>
        {notice && !failed && <Banner title={notice} />}
        <label>
          E-posta
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="ornek@eposta.com" />
        </label>
        <label>
          Şifre
          <input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={8} maxLength={72} value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {failed !== null && (
          <p className="pf-text-bad" role="alert">
            {failed instanceof Error ? failed.message : problem(failed)}
          </p>
        )}
        <Button type="submit" busy={busy}>
          {title}
        </Button>
      </form>
      <p className="pf-note">
        {mode === "login" ? "Hesabın yok mu? " : "Hesabın var mı? "}
        <button
          type="button"
          className="pf-link"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setFailed(null);
          }}
        >
          {mode === "login" ? "Kayıt ol" : "Giriş yap"}
        </button>
      </p>
    </main>
  );
}

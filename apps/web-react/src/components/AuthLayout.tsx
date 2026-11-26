import { useEffect, type ReactNode } from "react";
import Card from "./Card";

export interface AuthLayoutProps {
  title: string;
  children: ReactNode;
  // link to the other auth page, under the card
  footer?: ReactNode;
}

// centred brand + card for /giris and /kayit (no app header: the user is not signed in)
export default function AuthLayout({ title, children, footer }: AuthLayoutProps) {
  useEffect(() => {
    document.title = `${title} · AInvest`;
  }, [title]);

  return (
    <main className="auth-layout">
      <div className="auth-brand">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true">
            AI
          </span>
          AInvest
        </span>
        <p className="text-secondary">Finansal IQ skorunu öğren, AI koçundan açıklamasını dinle.</p>
      </div>
      <Card className="auth-card" title={title} headingLevel={1}>
        {children}
      </Card>
      {footer ? <p className="auth-switch">{footer}</p> : null}
    </main>
  );
}

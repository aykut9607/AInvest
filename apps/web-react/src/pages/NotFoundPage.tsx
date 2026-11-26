import { useEffect } from "react";
import { Link } from "react-router-dom";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { ROUTES } from "../lib/routes";

export default function NotFoundPage() {
  useEffect(() => {
    document.title = "Sayfa bulunamadı · AInvest";
  }, []);

  return (
    <main className="not-found">
      <Card className="auth-card">
        <EmptyState
          title="Sayfa bulunamadı"
          description="Aradığın sayfa yok ya da taşınmış olabilir."
          action={
            <Link className="btn btn-primary" to={ROUTES.dashboard}>
              Panele dön
            </Link>
          }
        />
      </Card>
    </main>
  );
}

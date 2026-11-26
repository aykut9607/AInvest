import { useEffect, type ReactNode } from "react";

export interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  // buttons on the right (wrap under the title on phones)
  actions?: ReactNode;
  // browser tab title; defaults to the page title
  documentTitle?: string;
}

// the page's only <h1>; also sets the browser tab title ("Profil · AInvest")
export default function PageHeader({ title, description, actions, documentTitle }: PageHeaderProps) {
  const tabTitle = documentTitle ?? title;
  useEffect(() => {
    document.title = `${tabTitle} · AInvest`;
  }, [tabTitle]);

  return (
    <header className="page-header">
      <div className="page-header-text">
        <h1>{title}</h1>
        {description ? <p className="page-header-description">{description}</p> : null}
      </div>
      {actions ? <div className="cluster">{actions}</div> : null}
    </header>
  );
}

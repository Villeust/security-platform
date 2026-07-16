import type { PropsWithChildren, ReactNode } from 'react';

type SectionProps = PropsWithChildren<{
  title?: string;
  description?: string;
  actions?: ReactNode;
}>;

export function Section({ title, description, actions, children }: SectionProps) {
  return (
    <section className="sp-section">
      {title || actions ? (
        <div className="sp-section-header">
          {title ? (
            <div>
              <h2 className="sp-section-title">{title}</h2>
              {description ? <p className="sp-section-description">{description}</p> : null}
            </div>
          ) : <span />}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

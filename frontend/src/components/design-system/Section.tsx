import type { PropsWithChildren, ReactNode } from 'react';

type SectionProps = PropsWithChildren<{
  title?: string;
  actions?: ReactNode;
}>;

export function Section({ title, actions, children }: SectionProps) {
  return (
    <section className="sp-section">
      {title || actions ? (
        <div className="sp-section-header">
          {title ? <h2 className="sp-section-title">{title}</h2> : <span />}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

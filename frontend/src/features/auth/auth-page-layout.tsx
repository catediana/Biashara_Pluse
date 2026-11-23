import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

interface AuthPageLayoutProps {
  eyebrow: string
  title: string
  description: string
  children: ReactNode
  footer?: ReactNode
}

export function AuthPageLayout({
  eyebrow,
  title,
  description,
  children,
  footer,
}: AuthPageLayoutProps) {
  return (
    <main className="login-page">
      <section className="login-card">
        <Link className="brand-lockup" to="/" aria-label="Biashara Pulse home">
          <span className="brand-mark">B</span>
          <span>
            <strong>Biashara</strong>
            <small>BUSINESS, IN RHYTHM</small>
          </span>
        </Link>
        <div className="mt-12">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
            {title}
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {description}
          </p>
        </div>

        {children}
        {footer && (
          <div className="mt-8 text-center text-xs leading-5 text-slate-400">
            {footer}
          </div>
        )}
      </section>
      <aside className="login-aside">
        <div className="aside-glow" />
        <div className="aside-content">
          <span className="aside-pill">
            <span className="status-dot" />
            YOUR BUSINESS, IN SYNC
          </span>
          <h2>
            Make every
            <br />
            day <em>count.</em>
          </h2>
          <p>
            One calm, connected workspace for the people, numbers, and
            operations that move your business forward.
          </p>
          <div className="aside-bottom">
            <span>01</span>
            <span className="aside-rule" />
            <span>BUILT FOR HOW YOU DO BUSINESS</span>
          </div>
        </div>
        <div className="aside-orbit orbit-one" />
        <div className="aside-orbit orbit-two" />
      </aside>
    </main>
  )
}

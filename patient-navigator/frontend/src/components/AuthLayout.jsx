import { BrandMark } from './Icon'
import '../pages/auth.css'

export default function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <div className="auth-page">
      <header className="auth-masthead">
        <span className="brand">
          <BrandMark size={24} />
          <span className="brand-title">NaviCare</span>
        </span>
      </header>

      <main className="auth-main">
        <div className="auth-form-wrap">
          <h1>{title}</h1>
          <p className="auth-subtitle">{subtitle}</p>
          {children}
          {footer && <div className="auth-footer">{footer}</div>}
        </div>
      </main>

      <footer className="auth-fineprint">
        <p>
          NaviCare helps you find care, prepare for tests and manage appointments. It gives guidance, not a diagnosis.
        </p>
        <p className="auth-fineprint-emergency">
          In an emergency, call your local emergency number or go to the nearest emergency department.
        </p>
        <p>Your records are visible only to you and your care team.</p>
      </footer>
    </div>
  )
}

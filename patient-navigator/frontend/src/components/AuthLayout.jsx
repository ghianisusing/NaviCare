import Icon, { BrandMark } from './Icon'
import '../pages/auth.css'

const HIGHLIGHTS = [
  {
    icon: 'book',
    title: 'Answers from vetted sources',
    text: 'Health questions are answered from a curated library, with every source cited.',
  },
  {
    icon: 'calendar',
    title: 'Visits and follow-ups in one place',
    text: 'Find openings, book appointments and keep track of what your care team asked of you.',
  },
  {
    icon: 'shield',
    title: 'Safety comes first',
    text: 'Emergency symptoms trigger fixed safety guidance, and a real person steps in when needed.',
  },
]

export default function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <div className="auth-page">
      <section className="auth-showcase" aria-hidden="true">
        <div className="auth-showcase-brand">
          <BrandMark size={34} />
          <span>NaviCare</span>
        </div>

        <div className="auth-showcase-body">
          <h2>Care navigation that knows when to bring in a person.</h2>

          <div className="auth-preview">
            <div className="auth-preview-msg user">How should I prepare for a fasting blood test?</div>
            <div className="auth-preview-msg ai">
              <span className="auth-preview-ai-label">
                <Icon name="sparkle" size={13} /> Navigator
              </span>
              Usually no food or drink except water for 8–12 hours beforehand. Keep taking your regular medicines
              unless your clinician told you otherwise.
              <span className="auth-preview-source">
                <Icon name="book" size={12} /> Lab test preparation guide
              </span>
            </div>
          </div>

          <ul className="auth-highlights">
            {HIGHLIGHTS.map((item) => (
              <li key={item.title}>
                <span className="auth-highlight-icon">
                  <Icon name={item.icon} size={17} />
                </span>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="auth-showcase-foot">NaviCare offers guidance, not diagnosis. In an emergency, call your local emergency number.</p>
      </section>

      <section className="auth-panel">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand">
            <BrandMark size={30} />
            <span>NaviCare</span>
          </div>
          <h1>{title}</h1>
          <p className="auth-subtitle">{subtitle}</p>
          {children}
          {footer && <div className="auth-footer">{footer}</div>}
          <p className="auth-security-notice">
            <Icon name="lock" size={14} />
            Your records are only ever visible to you and your care team.
          </p>
        </div>
      </section>
    </div>
  )
}

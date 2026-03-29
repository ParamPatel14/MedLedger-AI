import { ChevronRight } from 'lucide-react'

export function PageHeader({ title, subtitle, icon: Icon, actions }) {
  return (
    <div className="pageHero">
      <div className="container">
        <div className="pageHeroBreadcrumb">
          <span>MedLedger AI</span>
          <ChevronRight size={11} />
          <span>{title}</span>
        </div>
        <div className="pageHeroInner">
          <div className="pageHeroLeft">
            {Icon && (
              <div className="pageHeroIconWrap">
                <Icon size={22} strokeWidth={1.5} />
              </div>
            )}
            <div>
              <h1 className="pageHeroTitle">{title}</h1>
              {subtitle && <p className="pageHeroSub">{subtitle}</p>}
            </div>
          </div>
          {actions && <div style={{ flexShrink: 0 }}>{actions}</div>}
        </div>
      </div>
    </div>
  )
}

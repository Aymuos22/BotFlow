import { Fragment } from "react";
import { NavLink } from "react-router-dom";
import type React from "react";

export type SidebarLink = {
  to: string;
  label: string;
  icon: React.ReactNode;
  end?: boolean;
  /** When true, shown in the nav but not navigable (roadmap / presentation). */
  disabled?: boolean;
  /** Tooltip when disabled (default: Coming soon). */
  disabledHint?: string;
  /** Small label next to title, e.g. "Soon". */
  badge?: string;
  /** Optional heading rendered above this row (product / presentation). */
  sectionBefore?: string;
  /** If set, renders an external link instead of in-app routing. */
  externalHref?: string;
};

const BotFlowIcon = () => (
  <svg className="sidebar__brand-icon" viewBox="0 0 40 40" fill="none" aria-hidden>
    {/* Filled rounded square background */}
    <rect width="40" height="40" rx="10" fill="currentColor" />
    {/* White chat bubble */}
    <rect x="7" y="9" width="26" height="17" rx="4" fill="white" fillOpacity="0.95" />
    {/* Three dots */}
    <circle cx="14" cy="17.5" r="2" fill="currentColor" />
    <circle cx="20" cy="17.5" r="2" fill="currentColor" />
    <circle cx="26" cy="17.5" r="2" fill="currentColor" />
    {/* Tail */}
    <path d="M14 26 L18 31 L22 26" fill="white" fillOpacity="0.95" />
  </svg>
);

type Props = {
  links: SidebarLink[];
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapse: () => void;
  onCloseMobile: () => void;
};

export default function Sidebar({
  links,
  collapsed,
  mobileOpen,
  onToggleCollapse,
  onCloseMobile,
}: Props) {
  return (
    <>
      <aside className={`sidebar ${collapsed ? "sidebar--collapsed" : ""} ${mobileOpen ? "sidebar--mobile-open" : ""}`}>
        <div className="sidebar__brand">
          <BotFlowIcon />
          <div>
            <strong>BotFlow</strong>
            <span>Chatbot Engine</span>
          </div>
        </div>
        <button
          type="button"
          className="sidebar__collapse"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? ">" : "<"}
        </button>
        <nav className="sidebar__nav" aria-label="Main navigation">
          {links.map((link) => {
            const hint = link.disabled
              ? link.disabledHint ?? "Coming soon"
              : link.externalHref?.startsWith("http")
                ? `${link.label} (opens new tab)`
                : link.externalHref?.startsWith("mailto")
                  ? `${link.label} (opens email)`
                  : link.label;
            const outer = (
              <>
                {link.sectionBefore ? (
                  <div className="sidebar__nav-section">{link.sectionBefore}</div>
                ) : null}
                {link.externalHref ? (
                  <a
                    key={link.to}
                    href={link.externalHref}
                    {...(link.externalHref.startsWith("http")
                      ? { target: "_blank", rel: "noopener noreferrer" }
                      : {})}
                    onClick={onCloseMobile}
                    className="sidebar__link sidebar__link--external"
                    title={hint}
                  >
                    <span className="sidebar__icon">{link.icon}</span>
                    <span className="sidebar__label">{link.label}</span>
                  </a>
                ) : link.disabled ? (
                  <button
                    key={link.to}
                    type="button"
                    disabled
                    className="sidebar__link sidebar__link--disabled"
                    title={hint}
                  >
                    <span className="sidebar__icon" aria-hidden>
                      {link.icon}
                    </span>
                    <span className="sidebar__label sidebar__label--with-badge">
                      <span>{link.label}</span>
                      {link.badge ? (
                        <span className="sidebar__badge">{link.badge}</span>
                      ) : null}
                    </span>
                  </button>
                ) : (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    end={link.end}
                    onClick={onCloseMobile}
                    title={hint}
                    className={({ isActive }) =>
                      `sidebar__link ${isActive ? "sidebar__link--active" : ""}`
                    }
                  >
                    <span className="sidebar__icon">{link.icon}</span>
                    <span className="sidebar__label">{link.label}</span>
                  </NavLink>
                )}
              </>
            );
            return <Fragment key={link.to}>{outer}</Fragment>;
          })}
        </nav>
      </aside>
      {mobileOpen && <button type="button" className="sidebar-backdrop" onClick={onCloseMobile} aria-label="Close sidebar" />}
    </>
  );
}

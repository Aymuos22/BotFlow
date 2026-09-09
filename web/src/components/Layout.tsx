import { useState } from "react";
import type React from "react";
import Footer from "./Footer";
import Navbar from "./Navbar";
import Sidebar, { type SidebarLink } from "./Sidebar";

type Props = {
  children: React.ReactNode;
  links: SidebarLink[];
  userLabel: string;
  role: "admin" | "user";
  onLogout: () => void;
};

export default function Layout({
  children,
  links,
  userLabel,
  role,
  onLogout,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className={`dashboard-layout ${collapsed ? "dashboard-layout--collapsed" : ""}`}>
      <Sidebar
        links={links}
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggleCollapse={() => setCollapsed((v) => !v)}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div className="dashboard-layout__main">
        <Navbar
          userLabel={userLabel}
          role={role}
          onLogout={onLogout}
          onOpenSidebar={() => setMobileOpen(true)}
        />
        <main className="dashboard-content">{children}</main>
        <Footer />
      </div>
    </div>
  );
}

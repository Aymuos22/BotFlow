import ThemeToggle from "./ThemeToggle";
import UserAvatarDropdown from "./UserAvatarDropdown";

type Props = {
  userLabel: string;
  role: "admin" | "user";
  onLogout: () => void;
  onOpenSidebar: () => void;
};

export default function Navbar({ userLabel, role, onLogout, onOpenSidebar }: Props) {
  return (
    <header className="topbar">
      <button
        type="button"
        className="topbar__hamburger"
        onClick={onOpenSidebar}
        aria-label="Open sidebar"
      >
        <span />
        <span />
        <span />
      </button>
      <div className="topbar__spacer" />
      <ThemeToggle />
      <UserAvatarDropdown label={userLabel} role={role} onLogout={onLogout} />
    </header>
  );
}

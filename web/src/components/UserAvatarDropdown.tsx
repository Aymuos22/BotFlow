import { useEffect, useRef, useState } from "react";

type Props = {
  label: string;
  role: "admin" | "user";
  onLogout: () => void;
};

export default function UserAvatarDropdown({ label, role, onLogout }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const initials = label
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "U";

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  return (
    <div className="user-menu" ref={ref}>
      <button
        type="button"
        className="user-menu__button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="user-menu__avatar">{initials}</span>
        <span className="user-menu__meta">
          <strong>{label}</strong>
          <small>{role}</small>
        </span>
      </button>
      {open && (
        <div className="user-menu__dropdown" role="menu">
          <button type="button" role="menuitem">Profile</button>
          <button type="button" role="menuitem">Settings</button>
          <button type="button" role="menuitem" onClick={onLogout}>Logout</button>
        </div>
      )}
    </div>
  );
}

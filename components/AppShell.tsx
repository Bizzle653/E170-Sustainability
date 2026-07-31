"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useState } from "react";
import { useAuth } from "@/components/AuthProvider";

const navigation = [
  {href: "/portfolio", label: "Overview", icon: "⌂"},
  {href: "/results", label: "Portfolio analysis", icon: "↗"},
  {href: "/", label: "Build another", icon: "+"},
  {href: "/chat", label: "AI Assistant", icon: "✦"},
  {href: "/profile", label: "Profile", icon: "◉"},
  {href: "/settings", label: "Settings", icon: "⚙"},
];

export function AppShell({children}: {children: ReactNode}) {
  const pathname = usePathname();
  const router = useRouter();
  const {user, signOut} = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const displayName = user?.user_metadata?.full_name || user?.email?.split("@")[0] || "Investor";
  const initials = String(displayName).split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();

  async function logout() {
    await signOut();
    router.replace("/login");
  }

  return <div className="appShell">
    <aside className={`appSidebar ${menuOpen ? "open" : ""}`}>
      <Link className="brand shellBrand" href="/portfolio"><span className="brandMark">⌁</span><span>Green Canopy</span></Link>
      <nav>{navigation.map((item) => <Link className={pathname === item.href ? "active" : ""} href={item.href} key={item.href} onClick={() => setMenuOpen(false)}><i>{item.icon}</i><span>{item.label}</span></Link>)}</nav>
      <div className="sidebarTrust"><strong>Educational portfolio</strong><small>Transparent scoring. No brokerage connection. No trades.</small></div>
      <div className="accountCard"><span className="accountAvatar">{initials}</span><span><strong>{displayName}</strong><small>{user?.email ?? "Account preview"}</small></span><button onClick={logout} aria-label="Log out">↪</button></div>
    </aside>
    <div className="appContent"><header className="appTopbar"><button className="mobileMenu" onClick={() => setMenuOpen((value) => !value)} aria-label="Toggle navigation">☰</button><span>Invest with clarity</span><div className="topAccount"><span className="accountAvatar">{initials}</span><div><strong>{displayName}</strong><small>{user?.email}</small></div><button onClick={logout}>Log out</button></div></header>{children}</div>
  </div>;
}

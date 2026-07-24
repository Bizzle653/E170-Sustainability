"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { useAuth } from "@/components/AuthProvider";

export function AccountGate({children}: {children: ReactNode}) {
  const {user, loading, configured} = useAuth();
  if (loading) return <main className="accountGate"><span className="loadingRing" /><p>Opening your Green Canopy account…</p></main>;
  if (!configured) return <main className="accountGate"><div className="brand"><span className="brandMark">⌁</span><span>Green Canopy</span></div><h1>Connect account storage</h1><p>The account experience is ready. Connect the project’s Supabase environment values to activate secure email and password sign-in.</p><Link className="button" href="/">Return to Green Canopy</Link></main>;
  if (!user) return <main className="accountGate"><div className="brand"><span className="brandMark">⌁</span><span>Green Canopy</span></div><h1>Welcome back.</h1><p>Sign in to view your saved portfolio, profile, and settings.</p><Link className="button" href="/login">Sign in</Link></main>;
  return children;
}

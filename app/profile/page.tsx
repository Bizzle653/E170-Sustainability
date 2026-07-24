"use client";

import { FormEvent, useEffect, useState } from "react";
import { AccountGate } from "@/components/AccountGate";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthProvider";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function ProfilePage() {
  return <AccountGate><AppShell><ProfileContent /></AppShell></AccountGate>;
}

function ProfileContent() {
  const {user} = useAuth();
  const [fullName, setFullName] = useState(user?.user_metadata?.full_name ?? "");
  const [currency, setCurrency] = useState("USD");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !user) return;
    void supabase.from("profiles").select("full_name,currency").eq("id", user.id).maybeSingle().then(({data}) => {
      if (data) {
        setFullName(data.full_name || user.user_metadata?.full_name || "");
        setCurrency(data.currency || "USD");
      }
    });
  }, [user]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !user) return;
    setBusy(true);
    setError("");
    setMessage("");
    const {error: profileError} = await supabase.from("profiles").upsert({
      id: user.id,
      full_name: fullName,
      currency,
      updated_at: new Date().toISOString(),
    });
    const {error: authError} = await supabase.auth.updateUser({data: {full_name: fullName}});
    if (profileError || authError) setError(profileError?.message || authError?.message || "Profile could not be saved.");
    else setMessage("Profile saved.");
    setBusy(false);
  }

  const priorities = (() => {
    try {
      if (typeof window === "undefined") return [];
      const raw = localStorage.getItem("greenCanopyPortfolio");
      if (!raw) return [];
      const portfolio = JSON.parse(raw);
      return Object.entries(portfolio.investor_profile?.sustainability_priority_weights ?? {})
        .filter(([, value]) => Number(value) > 0)
        .sort((a, b) => Number(b[1]) - Number(a[1]))
        .map(([key]) => key.replaceAll("_", " "));
    } catch { return []; }
  })();

  return <main className="accountPage">
    <header className="accountPageHeader"><span className="eyebrow">Your account</span><h1>Profile</h1><p>Manage the personal details attached to your Green Canopy portfolio.</p></header>
    <div className="accountColumns">
      <section className="settingsCard profileSummary"><span className="profileAvatar">{fullName ? fullName.slice(0, 1).toUpperCase() : "G"}</span><h2>{fullName || "Green Canopy investor"}</h2><p>{user?.email}</p><div><span>Investor style</span><strong>{priorities.length ? priorities.slice(0, 3).join(" · ") : "Complete your portfolio profile"}</strong></div><small>Your financial and sustainability answers determine the investor style shown here.</small></section>
      <section className="settingsCard"><div className="settingsHeading"><div><span className="eyebrow">Personal information</span><h2>About you</h2></div></div><form className="settingsForm" onSubmit={save}><label>Full name<input value={fullName} onChange={(event) => setFullName(event.target.value)} autoComplete="name" /></label><label>Account email<input value={user?.email ?? ""} disabled /><small>Change your sign-in email from Settings.</small></label><label>Display currency<select value={currency} onChange={(event) => setCurrency(event.target.value)}><option value="USD">USD · US Dollar</option><option value="CAD">CAD · Canadian Dollar</option><option value="GBP">GBP · British Pound</option><option value="EUR">EUR · Euro</option></select></label>{error && <p className="errorMessage">{error}</p>}{message && <p className="successMessage">{message}</p>}<button className="button" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button></form></section>
    </div>
  </main>;
}

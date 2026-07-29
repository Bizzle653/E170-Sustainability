"use client";

import { FormEvent, useEffect, useState } from "react";
import { AccountGate } from "@/components/AccountGate";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthProvider";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function SettingsPage() {
  return (
    <AccountGate>
      <AppShell>
        <SettingsContent />
      </AppShell>
    </AccountGate>
  );
}

function SettingsContent() {
  const { user } = useAuth();
  const [weeklyDigest, setWeeklyDigest] = useState(true);
  const [marketAlerts, setMarketAlerts] = useState(false);
  const [email, setEmail] = useState(user?.email ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !user) return;
    void supabase
      .from("profiles")
      .select("weekly_digest,market_alerts")
      .eq("id", user.id)
      .maybeSingle()
      .then(({ data }) => {
        if (data) {
          setWeeklyDigest(data.weekly_digest);
          setMarketAlerts(data.market_alerts);
        }
      });
  }, [user]);

  async function savePreferences() {
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !user) return;
    setBusy("preferences");
    setError("");
    setMessage("");
    const { error: saveError } = await supabase.from("profiles").upsert({
      id: user.id,
      weekly_digest: weeklyDigest,
      market_alerts: marketAlerts,
      updated_at: new Date().toISOString(),
    });
    if (saveError) setError(saveError.message);
    else setMessage("Preferences saved.");
    setBusy("");
  }

  async function changeEmail(event: FormEvent) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();
    if (!supabase) return;
    setBusy("email");
    setError("");
    setMessage("");
    const { error: updateError } = await supabase.auth.updateUser({ email });
    if (updateError) setError(updateError.message);
    else setMessage("Check both email addresses to confirm the change.");
    setBusy("");
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !user?.email) return;
    setBusy("password");
    setError("");
    setMessage("");
    const { error: verifyError } = await supabase.auth.signInWithPassword({
      email: user.email,
      password: currentPassword,
    });
    if (verifyError) {
      setError("Your current password is incorrect.");
      setBusy("");
      return;
    }
    const { error: updateError } = await supabase.auth.updateUser({
      password: newPassword,
    });
    if (updateError) setError(updateError.message);
    else {
      setMessage("Password updated.");
      setCurrentPassword("");
      setNewPassword("");
    }
    setBusy("");
  }

  return (
    <main className="accountPage">
      <header className="accountPageHeader">
        <span className="eyebrow">Control center</span>
        <h1>Settings</h1>
        <p>Choose how your account communicates and keep your sign-in secure.</p>
      </header>
      {error && <p className="errorMessage accountMessage">{error}</p>}
      {message && <p className="successMessage accountMessage">{message}</p>}
      <div className="settingsStack">
        <section className="settingsCard">
          <div className="settingsHeading">
            <div>
              <span className="eyebrow">Preferences</span>
              <h2>Notifications</h2>
            </div>
            <button
              className="button buttonSmall"
              onClick={savePreferences}
              disabled={busy === "preferences"}
            >
              Save
            </button>
          </div>
          <div className="toggleRows">
            <label>
              <span>
                <strong>Weekly portfolio digest</strong>
                <small>A concise summary of holdings, returns, and alignment.</small>
              </span>
              <input
                type="checkbox"
                checked={weeklyDigest}
                onChange={(event) => setWeeklyDigest(event.target.checked)}
              />
            </label>
            <label>
              <span>
                <strong>Market movement alerts</strong>
                <small>Notify me when a tracked holding moves materially.</small>
              </span>
              <input
                type="checkbox"
                checked={marketAlerts}
                onChange={(event) => setMarketAlerts(event.target.checked)}
              />
            </label>
          </div>
        </section>
        <section className="settingsCard">
          <div className="settingsHeading">
            <div>
              <span className="eyebrow">Sign-in email</span>
              <h2>Email address</h2>
            </div>
          </div>
          <form className="inlineSettingsForm" onSubmit={changeEmail}>
            <label>
              New email
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <button
              className="backButton"
              disabled={busy === "email" || email === user?.email}
            >
              Update email
            </button>
          </form>
        </section>
        <section className="settingsCard">
          <div className="settingsHeading">
            <div>
              <span className="eyebrow">Security</span>
              <h2>Change password</h2>
            </div>
          </div>
          <form className="inlineSettingsForm passwordForm" onSubmit={changePassword}>
            <label>
              Current password
              <input
                type="password"
                required
                autoComplete="current-password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </label>
            <label>
              New password
              <input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
            </label>
            <button className="backButton" disabled={busy === "password"}>
              Update password
            </button>
          </form>
          <small className="securityNote">
            Use at least 8 characters and a password you do not reuse elsewhere.
          </small>
        </section>
        <section className="settingsCard dataSettings">
          <div>
            <span className="eyebrow">Portfolio data</span>
            <h2>Your data stays yours</h2>
            <p>
              Green Canopy stores only the profile and simulated portfolio needed for this
              experience. It does not connect to a brokerage or move money.
            </p>
          </div>
          <button
            className="dangerButton"
            onClick={() => {
              localStorage.removeItem("greenCanopyPortfolio");
              localStorage.removeItem("greenCanopyQuotes");
              window.location.href = "/";
            }}
          >
            Clear this device
          </button>
        </section>
      </div>
    </main>
  );
}

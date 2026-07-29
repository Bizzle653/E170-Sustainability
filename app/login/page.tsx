"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import HCaptcha from "@hcaptcha/react-hcaptcha";
import {Turnstile, type TurnstileInstance} from "@marsidev/react-turnstile";
import { useAuth } from "@/components/AuthProvider";
import { getSupabaseBrowserClient } from "@/lib/supabase";

const CAPTCHA_PROVIDER = process.env.NEXT_PUBLIC_CAPTCHA_PROVIDER?.toLowerCase();
const CAPTCHA_SITE_KEY = process.env.NEXT_PUBLIC_CAPTCHA_SITE_KEY;
const CAPTCHA_ENABLED = Boolean(CAPTCHA_PROVIDER && CAPTCHA_SITE_KEY);
const CAPTCHA_CONFIG_VALID =
  (!CAPTCHA_PROVIDER && !CAPTCHA_SITE_KEY) ||
  (CAPTCHA_ENABLED && (CAPTCHA_PROVIDER === "hcaptcha" || CAPTCHA_PROVIDER === "turnstile"));

export default function LoginPage() {
  const router = useRouter();
  const {user, loading, configured} = useAuth();
  const hCaptchaRef = useRef<HCaptcha>(null);
  const turnstileRef = useRef<TurnstileInstance>(null);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && user) router.replace("/portfolio");
  }, [loading, user, router]);

  function resetCaptcha() {
    setCaptchaToken("");
    hCaptchaRef.current?.resetCaptcha();
    turnstileRef.current?.reset();
  }

  function changeMode(nextMode: "signin" | "signup") {
    setMode(nextMode);
    setError("");
    setMessage("");
    resetCaptcha();
  }

  function requireCaptchaToken() {
    if (!CAPTCHA_ENABLED || captchaToken) return true;
    setError("Complete the verification challenge before continuing.");
    return false;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !CAPTCHA_CONFIG_VALID || !requireCaptchaToken()) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "signup") {
        const {data, error: signUpError} = await supabase.auth.signUp({
          email,
          password,
          options: {
            captchaToken: captchaToken || undefined,
            data: {full_name: fullName},
            emailRedirectTo: `${window.location.origin}/portfolio`,
          },
        });
        if (signUpError) setError(signUpError.message);
        else if (data.session) router.replace("/portfolio");
        else setMessage("Check your email to confirm your Green Canopy account.");
      } else {
        const {error: signInError} = await supabase.auth.signInWithPassword({
          email,
          password,
          options: {captchaToken: captchaToken || undefined},
        });
        if (signInError) setError(signInError.message);
        else router.replace("/portfolio");
      }
    } finally {
      resetCaptcha();
      setBusy(false);
    }
  }

  async function resetPassword() {
    const supabase = getSupabaseBrowserClient();
    if (!supabase || !email) {
      setError("Enter your email first.");
      return;
    }
    if (!CAPTCHA_CONFIG_VALID || !requireCaptchaToken()) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const {error: resetError} = await supabase.auth.resetPasswordForEmail(email, {
        captchaToken: captchaToken || undefined,
        redirectTo: `${window.location.origin}/settings?reset=password`,
      });
      if (resetError) setError(resetError.message);
      else setMessage("Password reset instructions are on the way.");
    } finally {
      resetCaptcha();
      setBusy(false);
    }
  }

  return <main className="authPage">
    <section className="authStory"><Link className="brand inverse" href="/"><span className="brandMark lightMark">⌁</span><span>Green Canopy</span></Link><div><span className="eyebrow lightEyebrow">Your sustainable investing home</span><h1>See your portfolio clearly.</h1><p>Keep your values, holdings, performance, and company research together in one calm, private workspace.</p><div className="authBenefits"><span>✓ One portfolio overview</span><span>✓ Transparent sustainability scoring</span><span>✓ No brokerage connection or trades</span></div></div><small>Educational simulation · Not investment advice</small></section>
    <section className="authFormPanel"><div className="authForm">
      <span className="eyebrow">{mode === "signin" ? "Welcome back" : "Create your account"}</span><h2>{mode === "signin" ? "Sign in to Green Canopy" : "Start your Green Canopy profile"}</h2><p>{mode === "signin" ? "Your portfolio is waiting." : "Save your portfolio and preferences across sessions."}</p>
      {!configured && <p className="setupNotice">Account storage must be connected before sign-in can be used.</p>}
      {!CAPTCHA_CONFIG_VALID && <p className="setupNotice">Set NEXT_PUBLIC_CAPTCHA_PROVIDER to either hcaptcha or turnstile.</p>}
      <div className="authTabs"><button className={mode === "signin" ? "active" : ""} onClick={() => changeMode("signin")}>Sign in</button><button className={mode === "signup" ? "active" : ""} onClick={() => changeMode("signup")}>Create account</button></div>
      <form onSubmit={submit}>
        {mode === "signup" && <label>Full name<input required autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Your name" /></label>}
        <label>Email address<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label>
        <label>Password<input required type="password" minLength={8} autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" /></label>
        {CAPTCHA_ENABLED && <div className="captchaChallenge">
          {CAPTCHA_PROVIDER === "hcaptcha" && <HCaptcha ref={hCaptchaRef} sitekey={CAPTCHA_SITE_KEY!} onVerify={setCaptchaToken} onExpire={() => setCaptchaToken("")} onError={() => setCaptchaToken("")} />}
          {CAPTCHA_PROVIDER === "turnstile" && <Turnstile ref={turnstileRef} siteKey={CAPTCHA_SITE_KEY!} onSuccess={setCaptchaToken} onExpire={() => setCaptchaToken("")} onError={() => setCaptchaToken("")} />}
        </div>}
        {error && <p className="errorMessage" role="alert">{error}</p>}{message && <p className="successMessage">{message}</p>}
        <button className="button authSubmit" disabled={busy || !configured || !CAPTCHA_CONFIG_VALID}>{busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create my account"}</button>
      </form>
      {mode === "signin" && <button className="forgotButton" disabled={busy || !CAPTCHA_CONFIG_VALID} onClick={resetPassword}>Forgot your password?</button>}
      <p className="authFinePrint">By continuing, you acknowledge this is an educational portfolio simulation and not a brokerage account.</p>
    </div></section>
  </main>;
}

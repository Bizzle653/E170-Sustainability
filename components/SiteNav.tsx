"use client";

import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";

export function SiteNav() {
  const {user} = useAuth();
  return (
    <nav className="resultsNav">
      <Link className="brand" href="/">
        <span className="brandMark">⌁</span>
        <span>Green Canopy</span>
      </Link>
      <div className="navActions">
        <Link className="backButton navButton" href="/review">Review holdings</Link>
        <Link className="backButton navButton" href="/methodology">How it works</Link>
        <Link className="backButton navButton" href="/chat">AI Assistant</Link>
        {user ? (
          <Link className="backButton navButton" href="/portfolio">My dashboard</Link>
        ) : (
          <Link className="backButton navButton" href="/login">Sign in</Link>
        )}
        <Link className="button buttonSmall" href="/">Build portfolio</Link>
      </div>
    </nav>
  );
}

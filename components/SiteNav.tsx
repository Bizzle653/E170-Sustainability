"use client";

import Link from "next/link";

export function SiteNav() {
  return (
    <nav className="resultsNav">
      <Link className="brand" href="/">
        <span className="brandMark">⌁</span>
        <span>Green Canopy</span>
      </Link>
      <div className="navActions">
        <Link className="backButton navButton" href="/review">Review holdings</Link>
        <Link className="backButton navButton" href="/learn">Learn</Link>
        <Link className="backButton navButton" href="/methodology">Methodology</Link>
        <Link className="backButton navButton" href="/classification-updates">AI label updates</Link>
        <Link className="backButton navButton" href="/chat">AI Assistant</Link>
        <Link className="button buttonSmall" href="/">Build portfolio</Link>
      </div>
    </nav>
  );
}

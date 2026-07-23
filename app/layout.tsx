import type { Metadata } from "next";
import "./globals.css";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Green Canopy — Invest with purpose",
  description: "Build a personalized sustainable investment portfolio around your values and financial goals.",
  icons: { icon: "/favicon.svg" },
  openGraph: { title: "Green Canopy", description: "Invest with purpose. Grow a better future.", images: ["/og.png"] },
  twitter: { card: "summary_large_image", title: "Green Canopy", description: "Invest with purpose. Grow a better future.", images: ["/og.png"] },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

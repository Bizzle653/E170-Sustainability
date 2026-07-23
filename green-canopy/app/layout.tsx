import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "https";
  const metadataBase = new URL(host ? `${protocol}://${host}` : "http://localhost:3000");

  return {
    metadataBase,
    title: "Green Canopy — Invest with purpose",
    description:
      "Build a personalized sustainable investment portfolio around your values and financial goals.",
    icons: { icon: "/favicon.svg" },
    openGraph: {
      title: "Green Canopy",
      description: "Invest with purpose. Grow a better future.",
      images: ["/og.png"],
    },
    twitter: {
      card: "summary_large_image",
      title: "Green Canopy",
      description: "Invest with purpose. Grow a better future.",
      images: ["/og.png"],
    },
  };
}

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

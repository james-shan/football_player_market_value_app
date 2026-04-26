import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Player Market Value Dashboard",
  description: "Explore Big-5 league player history and 2025-26 projected end-of-season market values.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ink-950 text-ink-100 antialiased">
        <header className="border-b border-ink-800 bg-ink-900/50 backdrop-blur sticky top-0 z-10">
          <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-md bg-gradient-to-br from-brand-500 to-accent-500" />
              <div>
                <div className="text-sm font-semibold tracking-tight text-white">
                  Player Market Value Dashboard
                </div>
                <div className="text-xs text-ink-400">
                  Big-5 leagues · 2025-26 projections
                </div>
              </div>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <NavLink href="/">Player Explorer</NavLink>
              <NavLink href="/squad">Club / League Overview</NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        <footer className="border-t border-ink-800 mt-16">
          <div className="mx-auto max-w-7xl px-6 py-6 text-xs text-ink-500">
            Data sources: API-Football, Understat, Transfermarkt. Projections are
            end-of-season values for the 2025-26 campaign.
          </div>
        </footer>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-2 rounded-md text-ink-300 hover:text-white hover:bg-ink-800 transition"
    >
      {children}
    </Link>
  );
}

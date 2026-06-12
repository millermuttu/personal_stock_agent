"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  isActive: (pathname: string) => boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Stock Search",
    isActive: (pathname) => pathname === "/",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden>
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
        <path d="m20 20-3-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/runs",
    label: "Runs",
    isActive: (pathname) => pathname === "/runs" || pathname.startsWith("/runs/"),
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden>
        <path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/investments",
    label: "Investments",
    isActive: (pathname) => pathname === "/investments" || pathname.startsWith("/investments/"),
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden>
        <path
          d="M4 17l5-5 3 3 6-7"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M15 6h4v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname() ?? "/";

  return (
    <aside className="border-b border-border bg-canvas-soft/70 backdrop-blur md:sticky md:top-0 md:h-screen md:w-64 md:shrink-0 md:border-b-0 md:border-r">
      <div className="flex items-center gap-3 px-5 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-sm font-bold text-white">
          SA
        </span>
        <div className="leading-tight">
          <p className="font-display text-sm font-semibold">Stock Agent</p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-ink-soft">Console</p>
        </div>
      </div>

      <nav className="flex gap-1 px-3 pb-3 md:flex-col md:gap-1 md:px-3 md:pt-2">
        {NAV_ITEMS.map((item) => {
          const active = item.isActive(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex flex-1 items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition md:flex-none ${
                active
                  ? "bg-accent/10 text-accent"
                  : "text-ink-soft hover:bg-canvas hover:text-ink"
              }`}
            >
              <span className={active ? "text-accent" : "text-ink-soft"}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

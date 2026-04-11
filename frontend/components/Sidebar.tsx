"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";
import SearchBar from "@/components/SearchBar";

const NAV_ITEMS = [
  { label: "HOME", href: "/" },
  { label: "INVESTMENTS", href: "/investments" },
  { label: "SHORTLIST", href: "/shortlist" },
  { label: "COMMODITIES SENTIMENT", href: "/commodities-sentiment" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col w-64 min-h-screen bg-neutral-950 border-r border-neutral-800 px-6 py-8 shrink-0">
      <div className="text-2xl font-extrabold tracking-wide text-white mb-8">
        invest-hub
      </div>

      <SearchBar />

      <nav className="flex flex-col gap-1 flex-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`px-3 py-2 rounded-md text-sm font-semibold tracking-wide transition-colors ${
                isActive
                  ? "bg-neutral-800 text-white"
                  : "text-neutral-400 hover:text-white hover:bg-neutral-900"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="pt-4 border-t border-neutral-800">
        <UserButton
          appearance={{
            elements: {
              userButtonAvatarBox: "w-8 h-8",
            },
          }}
        />
      </div>
    </aside>
  );
}

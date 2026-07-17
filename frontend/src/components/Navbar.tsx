"use client";

import { FileCheck2, History, Home, LayoutDashboard, Upload } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Home", Icon: Home },
  { href: "/upload", label: "Upload", Icon: Upload },
  { href: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { href: "/history", label: "History", Icon: History },
];

export default function Navbar() {
  const pathname = usePathname();
  return (
    <nav className="border-b border-gray-200 bg-white" aria-label="Primary navigation">
      <div className="mx-auto flex min-h-16 max-w-7xl flex-col px-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between sm:h-16">
          <Link href="/" className="flex items-center gap-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-gray-950 text-white"><FileCheck2 size={18} aria-hidden="true" /></span>
            <span className="text-lg font-bold text-gray-950">MDAV</span>
          </Link>
          <span className="text-xs font-medium text-gray-500 sm:hidden">Document verification</span>
        </div>
        <div className="grid grid-cols-4 gap-0 pb-2 sm:flex sm:gap-1 sm:pb-0">
          {navItems.map(({ href, label, Icon }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
            return (
              <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`inline-flex min-w-0 items-center justify-center gap-1 rounded-md px-1.5 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 sm:shrink-0 sm:gap-1.5 sm:px-3 sm:text-sm ${active ? "bg-gray-950 text-white" : "text-gray-600 hover:bg-gray-100 hover:text-gray-950"}`}>
                <Icon size={15} aria-hidden="true" /> {label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

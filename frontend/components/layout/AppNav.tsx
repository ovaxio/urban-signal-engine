"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./AppNav.module.css";

const LINKS = [
  { href: "/dashboard", label: "Tableau de bord", matchAlso: ["/zones"] },
  { href: "/reports",   label: "Rapports d'impact" },
  { href: "/",          label: "Vitrine", exact: true },
  { href: "/contact",   label: "Contact" },
];

export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav className={styles.nav}>
      <div className={styles.inner}>
        {LINKS.map(({ href, label, matchAlso, exact }) => {
          const active = exact
            ? pathname === href
            : pathname === href
              || pathname.startsWith(href + "/")
              || (matchAlso ?? []).some((p) => pathname.startsWith(p));
          return (
            <Link
              key={href}
              href={href}
              className={`${styles.link} ${active ? styles.active : ""}`}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

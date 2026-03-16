import Link from "next/link";
import styles from "./AppHeader.module.css";

type Props = {
  /** Optional label shown after the brand name (e.g. "RAPPORTS D'IMPACT") */
  label?: string;
  /** Optional back link */
  back?: { href: string; text: string };
  /** Optional right-side content (sim badge, etc.) */
  right?: React.ReactNode;
  /** Override status dot color (default: green) */
  statusColor?: string;
};

export default function AppHeader({ label, back, right, statusColor = "#22c55e" }: Props) {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.left}>
          {back && (
            <Link href={back.href} className={styles.back}>
              ← {back.text}
            </Link>
          )}
          <Link href="/dashboard" className={styles.brand}>
            <span
              className={styles.statusDot}
              style={{ background: statusColor, boxShadow: `0 0 8px ${statusColor}` }}
            />
            <span className={styles.title}>URBAN SIGNAL ENGINE</span>
            <span className={styles.titleShort}>USE</span>
          </Link>
          {label && <span className={styles.label}>{label}</span>}
        </div>
        {right && <div className={styles.right}>{right}</div>}
      </div>
    </header>
  );
}

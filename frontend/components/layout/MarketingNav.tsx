import Link from "next/link";
import s from "../../app/landing.module.css";

type Props = {
  /** Show anchor links (Problème, Fonctionnalités, Méthode) — only on landing */
  showAnchors?: boolean;
  /** Show CTA button — only on landing */
  showCta?: boolean;
};

export default function MarketingNav({ showAnchors = false, showCta = false }: Props) {
  return (
    <nav className={s.nav}>
      <Link href="/" className={s.navLogo}>
        Urban Signal <span>Engine</span>
      </Link>

      {showAnchors ? (
        <ul className={s.navLinks}>
          <li><a href="#probleme">Problème</a></li>
          <li><a href="#fonctionnalites">Fonctionnalités</a></li>
          <li><a href="#methode">Méthode</a></li>
        </ul>
      ) : (
        <div />
      )}

      {showCta ? (
        <Link href="/contact"><button className={s.navCta}>Nous contacter</button></Link>
      ) : (
        <Link href="/contact" className={s.navCta}>Contact</Link>
      )}
    </nav>
  );
}

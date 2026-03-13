import type { Metadata } from "next";
import s from "../landing.module.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Mentions légales · Urban Signal Engine",
  description: "Mentions légales du site Urban Signal Engine, édité par Codeblend EURL.",
};

export default function MentionsLegales() {
  return (
    <div className={s.page}>
      <nav className={s.nav}>
        <Link href="/marketing" className={s.navLogo}>
          Urban Signal <span>Engine</span>
        </Link>
        <div />
      </nav>

      <article className={s.legalPage}>
        <h1 className={s.legalTitle}>Mentions légales</h1>
        <p className={s.legalUpdated}>Dernière mise à jour : mars 2026</p>

        <section className={s.legalSection}>
          <h2>1. Éditeur du site</h2>
          <p>
            Le site <strong>Urban Signal Engine</strong> (ci-après « le Site ») est édité par :
          </p>
          <ul>
            <li><strong>Raison sociale :</strong> Codeblend EURL</li>
            <li><strong>Forme juridique :</strong> Entreprise Unipersonnelle à Responsabilité Limitée (EURL)</li>
            <li><strong>Capital social :</strong> 1 000 €</li>
            <li><strong>Siège social :</strong> 58 bis rue des Aqueducs, 69005 Lyon, France</li>
            <li><strong>SIRET :</strong> 999 389 471 00015</li>
            <li><strong>RCS :</strong> Lyon 999 389 471</li>
            <li><strong>Code APE :</strong> 6201Z — Programmation informatique</li>
            <li><strong>N° TVA intracommunautaire :</strong> FR81 999389471</li>
            <li><strong>Email :</strong> guillaume.chambard@codeblend.fr</li>
            <li><strong>Directeur de la publication :</strong> Guillaume Chambard</li>
          </ul>
        </section>

        <section className={s.legalSection}>
          <h2>2. Hébergement</h2>
          <ul>
            <li><strong>Frontend :</strong> Vercel Inc. — 340 S Lemon Ave #4133, Walnut, CA 91789, États-Unis</li>
            <li><strong>Backend :</strong> Render Services, Inc. — 525 Brannan St, Suite 300, San Francisco, CA 94107, États-Unis</li>
          </ul>
        </section>

        <section className={s.legalSection}>
          <h2>3. Propriété intellectuelle</h2>
          <p>
            L&#39;ensemble des contenus présents sur le Site (textes, graphismes, logos, icônes,
            images, données, code source) est la propriété exclusive de Codeblend EURL ou
            de ses partenaires et est protégé par les lois françaises et internationales
            relatives à la propriété intellectuelle.
          </p>
          <p>
            Toute reproduction, représentation, modification, publication ou adaptation de
            tout ou partie des éléments du Site, quel que soit le moyen ou le procédé utilisé,
            est interdite sans autorisation écrite préalable de Codeblend EURL.
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>4. Sources de données</h2>
          <p>
            Urban Signal Engine agrège des données publiques issues de sources ouvertes,
            notamment :
          </p>
          <ul>
            <li>Données de trafic — Grand Lyon / Métropole de Lyon (licence ouverte)</li>
            <li>Données météorologiques — Open-Meteo (API ouverte)</li>
            <li>Données de transports en commun — TCL / SYTRAL (GTFS-RT)</li>
            <li>Données événementielles — données statiques</li>
          </ul>
          <p>
            Ces données sont utilisées conformément à leurs licences respectives.
            Aucune donnée personnelle n&#39;est collectée via ces sources.
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>5. Responsabilité</h2>
          <p>
            Les informations fournies par le Site le sont à titre indicatif et ne sauraient
            constituer un conseil opérationnel. Codeblend EURL ne garantit pas l&#39;exactitude,
            la complétude ou l&#39;actualité des scores et prévisions affichés.
          </p>
          <p>
            L&#39;UrbanScore est un indicateur composite calculé à partir de données publiques.
            Il ne constitue pas une mesure officielle et ne se substitue pas aux dispositifs
            de sécurité civile ou de gestion de crise existants.
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>6. Cookies</h2>
          <p>
            Le Site utilise uniquement un cookie fonctionnel (<code>theme</code>) pour
            mémoriser votre préférence d&#39;affichage (mode sombre / clair). Ce cookie est
            stocké localement dans votre navigateur (localStorage) et n&#39;est transmis à
            aucun serveur tiers.
          </p>
          <p>
            Aucun cookie publicitaire, de tracking ou analytique n&#39;est déposé sans votre
            consentement.
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>7. Droit applicable</h2>
          <p>
            Les présentes mentions légales sont régies par le droit français. Tout litige
            relatif à l&#39;utilisation du Site sera soumis à la compétence exclusive des
            tribunaux de Lyon.
          </p>
        </section>

        <div className={s.legalBack}>
          <Link href="/marketing">← Retour au site</Link>
        </div>
      </article>

      <footer className={s.footer}>
        <span>© 2026 Urban Signal Engine · Codeblend EURL · Lyon</span>
        <ul className={s.footerLinks}>
          <li><Link href="/marketing/mentions-legales">Mentions légales</Link></li>
          <li><Link href="/marketing/politique-confidentialite">Politique de confidentialité</Link></li>
          <li><a href="mailto:contact@urbansignal.fr">Contact</a></li>
        </ul>
      </footer>
    </div>
  );
}

import type { Metadata } from "next";
import s from "../landing.module.css";
import Link from "next/link";
import MarketingNav from "@/components/layout/MarketingNav";

export const metadata: Metadata = {
  title: "Politique de confidentialité · Urban Signal Engine",
  description: "Politique de confidentialité et de protection des données personnelles (RGPD) d'Urban Signal Engine.",
};

export default function PolitiqueConfidentialite() {
  return (
    <div className={s.page}>
      <MarketingNav />

      <article className={s.legalPage}>
        <h1 className={s.legalTitle}>Politique de confidentialité</h1>
        <p className={s.legalUpdated}>Dernière mise à jour : mars 2026</p>

        <section className={s.legalSection}>
          <h2>1. Responsable du traitement</h2>
          <p>
            Le responsable du traitement des données est :
          </p>
          <ul>
            <li><strong>Codeblend EURL</strong> (SIRET : 999 389 471 00015)</li>
            <li>58 bis rue des Aqueducs, 69005 Lyon, France</li>
            <li>Email : guillaume.chambard@codeblend.fr</li>
            <li>Représentant : Guillaume Chambard, Gérant</li>
          </ul>
        </section>

        <section className={s.legalSection}>
          <h2>2. Données collectées</h2>
          <p>
            Urban Signal Engine traite exclusivement des <strong>données publiques agrégées</strong>
            {" "}(trafic, météo, transports, événements). La plateforme ne collecte
            <strong> aucune donnée personnelle</strong> de ses utilisateurs en navigation libre.
          </p>
          <p>
            Dans le cadre d&#39;une prise de contact ou d&#39;une demande commerciale, les données
            suivantes peuvent être collectées :
          </p>
          <ul>
            <li>Nom et prénom</li>
            <li>Adresse email professionnelle</li>
            <li>Nom de l&#39;organisation</li>
            <li>Contenu du message</li>
          </ul>
        </section>

        <section className={s.legalSection}>
          <h2>3. Finalités du traitement</h2>
          <p>Les données collectées sont utilisées pour :</p>
          <ul>
            <li>Répondre aux demandes de renseignements et de démonstration</li>
            <li>Établir et gérer la relation commerciale</li>
            <li>Fournir l&#39;accès à la plateforme aux clients sous contrat</li>
            <li>Améliorer le service et corriger les anomalies techniques</li>
          </ul>
        </section>

        <section className={s.legalSection}>
          <h2>4. Base légale</h2>
          <p>
            Les traitements reposent sur :
          </p>
          <ul>
            <li><strong>L&#39;intérêt légitime</strong> de Codeblend EURL pour les demandes commerciales</li>
            <li><strong>L&#39;exécution contractuelle</strong> pour les clients disposant d&#39;un abonnement</li>
            <li><strong>Le consentement</strong> pour tout traitement optionnel (newsletter, analytics) — vous pouvez retirer votre consentement à tout moment</li>
          </ul>
        </section>

        <section className={s.legalSection}>
          <h2>5. Durée de conservation</h2>
          <ul>
            <li><strong>Données de contact :</strong> 3 ans à compter du dernier échange</li>
            <li><strong>Données clients :</strong> durée du contrat + 5 ans (obligations légales)</li>
            <li><strong>Données techniques :</strong> scores et historiques agrégés conservés sans limitation (données non personnelles)</li>
            <li><strong>Logs serveur :</strong> 12 mois maximum</li>
          </ul>
        </section>

        <section className={s.legalSection}>
          <h2>6. Destinataires des données</h2>
          <p>
            Les données personnelles sont accessibles uniquement à l&#39;équipe de Codeblend EURL.
            Elles ne sont ni vendues, ni louées, ni partagées avec des tiers à des fins
            commerciales.
          </p>
          <p>Les sous-traitants techniques suivants peuvent traiter des données :</p>
          <ul>
            <li><strong>Vercel Inc.</strong> (hébergement frontend) — États-Unis, certifié DPF</li>
            <li><strong>Render Services, Inc.</strong> (hébergement backend) — États-Unis, encadré par CCT</li>
            <li><strong>Sentry</strong> (monitoring d&#39;erreurs) — États-Unis, certifié SOC 2</li>
          </ul>
          <p>
            Les transferts vers les États-Unis sont encadrés par les clauses contractuelles
            types (CCT) de la Commission européenne et/ou le Data Privacy Framework (DPF).
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>7. Cookies et stockage local</h2>
          <p>
            Le Site utilise uniquement le stockage local du navigateur (localStorage) pour
            mémoriser votre préférence de thème (sombre / clair). Aucun cookie de suivi,
            publicitaire ou analytique n&#39;est déposé sans consentement préalable.
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>8. Vos droits (RGPD)</h2>
          <p>
            Conformément au Règlement Général sur la Protection des Données (UE) 2016/679
            et à la loi Informatique et Libertés, vous disposez des droits suivants :
          </p>
          <ul>
            <li><strong>Droit d&#39;accès :</strong> obtenir une copie de vos données</li>
            <li><strong>Droit de rectification :</strong> corriger des données inexactes</li>
            <li><strong>Droit d&#39;effacement :</strong> demander la suppression de vos données</li>
            <li><strong>Droit à la portabilité :</strong> recevoir vos données dans un format structuré</li>
            <li><strong>Droit d&#39;opposition :</strong> vous opposer au traitement de vos données</li>
            <li><strong>Droit à la limitation :</strong> restreindre le traitement</li>
          </ul>
          <p>
            Pour exercer ces droits, contactez-nous à : <strong>contact@urbansignal.fr</strong>
          </p>
          <p>
            Nous répondrons dans un délai maximum de 30 jours. En cas de désaccord, vous
            pouvez introduire une réclamation auprès de la <strong>CNIL</strong> (Commission
            Nationale de l&#39;Informatique et des Libertés) — <a href="https://www.cnil.fr" target="_blank" rel="noopener noreferrer">www.cnil.fr</a>.
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>9. Sécurité</h2>
          <p>
            Codeblend EURL met en œuvre des mesures techniques et organisationnelles
            appropriées pour protéger les données : chiffrement en transit (HTTPS/TLS),
            contrôle d&#39;accès, sauvegardes régulières, monitoring des erreurs et alertes
            de sécurité.
          </p>
        </section>

        <section className={s.legalSection}>
          <h2>10. Modification de cette politique</h2>
          <p>
            La présente politique peut être mise à jour à tout moment. La date de dernière
            mise à jour est indiquée en haut de cette page. Nous vous invitons à la consulter
            régulièrement.
          </p>
        </section>

        <div className={s.legalBack}>
          <Link href="/">← Retour au site</Link>
        </div>
      </article>

      <footer className={s.footer}>
        <span>© 2026 Urban Signal Engine · Codeblend EURL · Lyon</span>
        <ul className={s.footerLinks}>
          <li><Link href="/mentions-legales">Mentions légales</Link></li>
          <li><Link href="/politique-confidentialite">Politique de confidentialité</Link></li>
          <li><a href="mailto:contact@urbansignal.fr">Contact</a></li>
        </ul>
      </footer>
    </div>
  );
}

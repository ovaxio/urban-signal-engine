"use client";

import { useState } from "react";
import Link from "next/link";
import s from "../landing.module.css";
import MarketingNav from "@/components/layout/MarketingNav";
import { submitContact } from "@/lib/api";

type FormState = "idle" | "sending" | "success" | "error";

export default function ContactPage() {
  const [state, setState] = useState<FormState>("idle");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setState("sending");
    setError("");

    const fd = new FormData(e.currentTarget);

    try {
      await submitContact({
        nom: fd.get("nom") as string,
        email: fd.get("email") as string,
        organisation: fd.get("organisation") as string,
        message: fd.get("message") as string,
      });
      setState("success");
    } catch {
      setError("Une erreur est survenue. Réessayez ou écrivez-nous à contact@urbansignal.fr.");
      setState("error");
    }
  }

  return (
    <div className={s.page}>
      <MarketingNav />

      <article className={s.legalPage}>
        <h1 className={s.legalTitle}>Nous contacter</h1>
        <p className={s.legalUpdated}>
          Collectivités, assureurs, organisateurs — parlez-nous de votre besoin.
        </p>

        {state === "success" ? (
          <div className={s.contactSuccess}>
            <h2>Message envoyé</h2>
            <p>
              Merci pour votre intérêt. Nous reviendrons vers vous sous 48h.
            </p>
            <Link href="/" className={s.contactBackLink}>
              ← Retour au site
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={s.contactForm}>
            <div className={s.contactField}>
              <label htmlFor="nom">Nom complet</label>
              <input
                id="nom"
                name="nom"
                type="text"
                required
                placeholder="Jean Dupont"
                disabled={state === "sending"}
              />
            </div>

            <div className={s.contactField}>
              <label htmlFor="email">Email professionnel</label>
              <input
                id="email"
                name="email"
                type="email"
                required
                placeholder="jean.dupont@metropole-lyon.fr"
                disabled={state === "sending"}
              />
            </div>

            <div className={s.contactField}>
              <label htmlFor="organisation">Organisation</label>
              <input
                id="organisation"
                name="organisation"
                type="text"
                required
                placeholder="Métropole de Lyon"
                disabled={state === "sending"}
              />
            </div>

            <div className={s.contactField}>
              <label htmlFor="message">Votre besoin</label>
              <textarea
                id="message"
                name="message"
                required
                rows={5}
                placeholder="Décrivez votre cas d'usage : monitoring événementiel, gestion de crise, évaluation de risques..."
                disabled={state === "sending"}
              />
            </div>

            {error && <p className={s.contactError}>{error}</p>}

            <button
              type="submit"
              className={s.btnPrimary}
              disabled={state === "sending"}
            >
              {state === "sending" ? "Envoi en cours..." : "Envoyer →"}
            </button>
          </form>
        )}
      </article>

      <footer className={s.footer}>
        <span>© 2026 Urban Signal Engine · Codeblend EURL · Lyon</span>
        <ul className={s.footerLinks}>
          <li><Link href="/mentions-legales">Mentions légales</Link></li>
          <li><Link href="/politique-confidentialite">Politique de confidentialité</Link></li>
          <li><Link href="/contact">Contact</Link></li>
        </ul>
      </footer>
    </div>
  );
}

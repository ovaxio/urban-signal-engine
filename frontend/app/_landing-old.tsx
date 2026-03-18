"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import s from "./landing.module.css";
import MarketingNav from "@/components/layout/MarketingNav";

/* ── Mock terminal data ─────────────────────────────────────────────────────── */

const ZONES = [
  { name: "Part-Dieu",      score: 78, level: "CRITIQUE" as const },
  { name: "Perrache",       score: 62, level: "TENDU" as const },
  { name: "Bellecour",      score: 55, level: "TENDU" as const },
  { name: "Vieux Lyon",     score: 41, level: "CALME" as const },
  { name: "Confluence",     score: 38, level: "CALME" as const },
  { name: "Guillotière",    score: 67, level: "TENDU" as const },
  { name: "Croix-Rousse",   score: 33, level: "CALME" as const },
];

const LEVEL_CLASS: Record<string, string> = {
  CALME: s.levelCalme,
  TENDU: s.levelTendu,
  CRITIQUE: s.levelCritique,
};

function scoreColor(score: number) {
  if (score >= 72) return "#ef4444";
  if (score >= 55) return "#f97316";
  return "#22c55e";
}

/* ── Scroll reveal hook ─────────────────────────────────────────────────────── */

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold: 0.15 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return { ref, className: `${s.reveal} ${visible ? s.revealVisible : ""}` };
}

/* ── Counter animation hook ─────────────────────────────────────────────────── */

function useCountUp(target: string, duration = 800) {
  const [display, setDisplay] = useState(target);
  const [started, setStarted] = useState(false);

  const start = useCallback(() => {
    if (started) return;
    setStarted(true);
    const numeric = parseInt(target, 10);
    if (isNaN(numeric)) { setDisplay(target); return; }

    const suffix = target.replace(String(numeric), "");
    const startTime = performance.now();

    function step(now: number) {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setDisplay(Math.round(numeric * eased) + suffix);
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }, [target, duration, started]);

  return { display, start };
}

/* ── Ticker item with counter ───────────────────────────────────────────────── */

function TickerItem({ value, label }: { value: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const { display, start } = useCountUp(value);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { start(); obs.disconnect(); } },
      { threshold: 0.5 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [start]);

  return (
    <div ref={ref} className={s.tickerItem}>
      <div className={s.tickerValue}>{display}</div>
      <div className={s.tickerLabel}>{label}</div>
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────────────────────────── */

export default function MarketingPage() {
  const problem = useReveal<HTMLElement>();
  const features = useReveal<HTMLElement>();
  const method = useReveal<HTMLElement>();
  const cta = useReveal<HTMLElement>();

  return (
    <div className={s.page}>
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <MarketingNav showAnchors showCta />

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section className={s.hero}>
        <div className={s.heroLeft}>
          <p className={s.heroEyebrow}>Plateforme temps réel · Lyon</p>
          <h1 className={s.heroTitle}>
            Détectez les tensions urbaines <em>avant</em> qu&#39;elles n&#39;éclatent
          </h1>
          <p className={s.heroSub}>
            Urban Signal Engine agrège trafic, météo, transports et événements
            pour calculer un score prédictif par quartier — en temps réel.
            Les collectivités, assureurs et organisateurs d&#39;événements
            anticipent au lieu de réagir.
          </p>
          <div className={s.heroCtas}>
            <Link href="/dashboard">
              <button className={s.btnPrimary}>
                Voir le dashboard live →
              </button>
            </Link>
            <Link href="/contact">
              <button className={s.btnSecondary}>
                Demander une présentation
              </button>
            </Link>
          </div>
        </div>

        <div className={s.heroRight}>
          <div className={s.heroTerminal}>
            <div className={s.termHeader}>
              <span className={s.termDot} />
              <span className={s.termDot} />
              <span className={s.termDot} />
            </div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 12, letterSpacing: "0.06em" }}>
              <span className={s.liveDot} />
              LIVE · {new Date().toLocaleDateString("fr-FR")} — 12 ZONES ACTIVES
            </div>
            {ZONES.map((z, i) => (
              <div
                key={z.name}
                className={s.termLineAnimated}
                style={{ animationDelay: `${0.3 + i * 0.12}s` }}
              >
                <span className={s.termZone}>{z.name}</span>
                <span className={s.termScore} style={{ color: scoreColor(z.score) }}>
                  {z.score}
                </span>
                <span className={`${s.termLevel} ${LEVEL_CLASS[z.level]}`}>
                  {z.level}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Ticker ──────────────────────────────────────────────────────── */}
      <div className={s.ticker}>
        {[
          { value: "12", label: "Zones monitorées" },
          { value: "5", label: "Sources de données" },
          { value: "60s", label: "Fréquence de rafraîchissement" },
          { value: "24/7", label: "Surveillance continue" },
          { value: "<2min", label: "Délai d'alerte" },
        ].map((t) => (
          <TickerItem key={t.label} value={t.value} label={t.label} />
        ))}
      </div>

      {/* ── Problème ────────────────────────────────────────────────────── */}
      <section ref={problem.ref} className={`${s.section} ${problem.className}`} id="probleme">
        <p className={s.sectionEyebrow}>Le problème</p>
        <h2 className={s.sectionTitle}>
          Les crises urbaines ne préviennent pas. Vos outils actuels non plus.
        </h2>
        <p className={s.sectionDesc}>
          Embouteillages en cascade, événements qui dégénèrent, grèves de
          transports combinées à un épisode météo — quand trois signaux faibles
          convergent, il est déjà trop tard.
        </p>

        <div className={s.problemGrid}>
          <div className={s.problemCard}>
            <div className={s.problemNumber}>01</div>
            <div className={s.problemCardTitle}>Données en silos</div>
            <p className={s.problemCardDesc}>
              Trafic routier, transports en commun, météo, événements — chaque
              source a son outil. Personne n&#39;a la vue d&#39;ensemble.
            </p>
          </div>
          <div className={s.problemCard}>
            <div className={s.problemNumber}>02</div>
            <div className={s.problemCardTitle}>Réaction, pas anticipation</div>
            <p className={s.problemCardDesc}>
              Les équipes terrain découvrent les tensions en même temps que les
              citoyens. Le temps de coordination est perdu.
            </p>
          </div>
          <div className={s.problemCard}>
            <div className={s.problemNumber}>03</div>
            <div className={s.problemCardTitle}>Aucune prédiction</div>
            <p className={s.problemCardDesc}>
              Sans modèle de convergence multi-signaux, impossible de prévoir
              quand une situation modérée va basculer en crise.
            </p>
          </div>
        </div>
      </section>

      {/* ── Fonctionnalités ─────────────────────────────────────────────── */}
      <section ref={features.ref} className={`${s.section} ${features.className}`} id="fonctionnalites">
        <p className={s.sectionEyebrow}>Fonctionnalités</p>
        <h2 className={s.sectionTitle}>
          Un score. Douze quartiers. Zéro surprise.
        </h2>
        <p className={s.sectionDesc}>
          L&#39;UrbanScore fusionne cinq sources de données en un indicateur
          unique par zone — de 0 (calme) à 100 (critique).
        </p>

        <div className={s.featuresGrid}>
          <div className={s.featureItem}>
            <span className={s.featureTag}>Temps réel</span>
            <h3 className={s.featureTitle}>Monitoring continu</h3>
            <p className={s.featureDesc}>
              Trafic (Criter/Grand Lyon), météo (Open-Meteo), transports TCL,
              événements et incidents — agrégés toutes les 60 secondes pour
              chaque zone.
            </p>
          </div>
          <div className={s.featureItem}>
            <span className={s.featureTag}>Prévision</span>
            <h3 className={s.featureTitle}>Forecast à 30, 60, 120 min</h3>
            <p className={s.featureDesc}>
              Projection du score basée sur les tendances actuelles et les
              cycles temporels (heure de pointe, nuit, week-end). Anticipez
              les pics avant qu&#39;ils ne surviennent.
            </p>
          </div>
          <div className={s.featureItem}>
            <span className={s.featureTag}>Simulation</span>
            <h3 className={s.featureTitle}>Mode &quot;What If&quot;</h3>
            <p className={s.featureDesc}>
              Simulez l&#39;impact d&#39;un concert, d&#39;une grève ou d&#39;un épisode
              météo extrême sur le score de chaque quartier. Testez vos plans
              de gestion de crise.
            </p>
          </div>
          <div className={s.featureItem}>
            <span className={s.featureTag}>Alertes</span>
            <h3 className={s.featureTitle}>Notifications intelligentes</h3>
            <p className={s.featureDesc}>
              Webhook, email ou Slack — soyez alerté dès qu&#39;une zone passe en
              TENDU ou CRITIQUE. Seuils configurables, pas de faux positifs
              grâce à la calibration automatique.
            </p>
          </div>
        </div>
      </section>

      {/* ── Méthode / Formule ───────────────────────────────────────────── */}
      <section ref={method.ref} className={`${s.section} ${method.className}`} id="methode">
        <p className={s.sectionEyebrow}>La méthode</p>
        <h2 className={s.sectionTitle}>
          Transparent. Auditable. Scientifique.
        </h2>
        <p className={s.sectionDesc}>
          Pas de boîte noire. L&#39;UrbanScore repose sur un modèle mathématique
          ouvert, calibré en continu sur les données historiques réelles de
          la métropole de Lyon.
        </p>

        <div className={s.formulaWrap}>
          <div className={s.formula}>
            <strong>UrbanScore</strong> = Φ(h) · (w<sub>T</sub>·T + w<sub>M</sub>·M + w<sub>E</sub>·E + w<sub>P</sub>·P + w<sub>I</sub>·I) + λ<sub>2</sub>·A + λ<sub>3</sub>·C + λ<sub>4</sub>·S
          </div>
          <p className={s.formulaCaption}>
            Φ = modulation temporelle · T = trafic · M = météo · E = événements · P = transports · I = incidents · A = anomalie · C = convergence · S = propagation spatiale
          </p>
        </div>
      </section>

      {/* ── CTA: Contact ───────────────────────────────────────────────── */}
      <section ref={cta.ref} className={`${s.ctaSection} ${cta.className}`} id="contact">
        <h2 className={s.ctaTitle}>
          Lyon mérite un système nerveux <em>intelligent</em>
        </h2>
        <p className={s.ctaDesc}>
          Collectivités, assureurs, organisateurs d&#39;événements — découvrez
          comment Urban Signal Engine peut transformer votre gestion du risque
          urbain.
        </p>
        <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/contact">
            <button className={s.btnPrimary}>Nous contacter →</button>
          </Link>
          <Link href="/dashboard">
            <button className={s.btnSecondary}>Explorer le dashboard</button>
          </Link>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
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

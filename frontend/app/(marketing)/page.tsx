import { Syne, DM_Sans } from "next/font/google";
import s from "./page.module.css";
import ContactForm from "./_components/ContactForm";

/* ── Fonts ─────────────────────────────────────────────────────────── */

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
  weight: ["700", "800"],
});

const dm = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

/* ── Score utilities ───────────────────────────────────────────────── */

function scoreColor(score: number): string {
  if (score >= 72) return "#ef4444";
  if (score >= 55) return "#f97316";
  if (score >= 35) return "#eab308";
  return "#22c55e";
}

function scoreLevel(score: number): string {
  if (score >= 72) return "CRITIQUE";
  if (score >= 55) return "TENDU";
  if (score >= 35) return "MODÉRÉ";
  return "CALME";
}

/* ── Hero monitor data ─────────────────────────────────────────────── */

const MONITOR_ZONES = [
  { name: "Part-Dieu", score: 67 },
  { name: "Villette", score: 52 },
  { name: "Presqu’île", score: 38 },
  { name: "Vieux-Lyon", score: 24 },
];

/* ── Backtest data (Match OL — 8 mars 2026) ───────────────────────── */

const BACKTEST_ZONES = [
  {
    name: "Villette",
    sub: "axe Groupama",
    color: "#f97316",
    scores: [28, 32, 55, 62, 72, 85, 80, 74, 65, 48, 36, 30, 28],
  },
  {
    name: "Part-Dieu",
    sub: "gare & hub",
    color: "#818cf8",
    scores: [30, 33, 38, 44, 52, 60, 68, 70, 62, 48, 38, 32, 29],
  },
  {
    name: "Brotteaux",
    sub: "résidentiel",
    color: "#22d3ee",
    scores: [27, 29, 32, 36, 42, 48, 52, 55, 50, 40, 33, 29, 27],
  },
];

const TIME_LABELS = [
  "T−4h", "T−3h", "T−2h", "T−1h30", "T−1h", "T−30m",
  "Coup d’envoi", "T+30m", "T+1h", "T+2h", "T+3h", "T+4h", "T+6h",
];

/* ── SVG chart config ──────────────────────────────────────────────── */

const CW = 780;
const CH = 210;
const CT = 30;
const CB = CT + CH;

function toX(i: number) {
  return (i / (TIME_LABELS.length - 1)) * CW;
}
function toY(score: number) {
  return CB - (score / 100) * CH;
}
function polyline(scores: number[]): string {
  return scores.map((sc, i) => `${toX(i).toFixed(1)},${toY(sc).toFixed(1)}`).join(" ");
}

/* ── Steps data ────────────────────────────────────────────────────── */

const STEPS = [
  {
    num: "1",
    title: "Signalez votre événement",
    desc: "Vous nous indiquez la date, le lieu et les zones qui vous concernent.",
  },
  {
    num: "2",
    title: "On analyse en temps réel",
    desc: "Trafic, transport, météo, incidents — croisés et scorés en continu sur vos zones.",
  },
  {
    num: "3",
    title: "Recevez le rapport",
    desc: "48h avant : les zones à surveiller, les créneaux à risque, les recommandations.",
  },
];

/* ── Page ───────────────────────────────────────────────────────────── */

export default function LandingPage() {
  return (
    <div className={`${s.page} ${syne.variable} ${dm.variable}`}>
      {/* ─── NAV ─── */}
      <nav className={s.nav}>
        <div className={s.navInner}>
          <a href="/" className={s.navLogo}>Urban Signal Engine</a>
          <div className={s.navLinks}>
            <a href="#proof" className={s.navLink}>Preuve</a>
            <a href="#pricing" className={s.navLink}>Tarifs</a>
            <a href="#form" className={s.navCta}>Demander un rapport</a>
          </div>
        </div>
      </nav>

      <main>
        {/* ─── HERO ─── */}
        <section className={s.hero}>
          <div className={s.heroInner}>
            <div className={s.heroContent}>
              <h1 className={s.headline}>
                Anticipez les tensions urbaines.
                <br />
                <span className={s.headlineAccent}>Avant qu&apos;elles arrivent.</span>
              </h1>
              <p className={s.subheadline}>
                Recevez un rapport d&apos;anticipation 48h avant votre prochain
                événement à Lyon. Ajustez vos effectifs avant, pas pendant.
              </p>
              <a href="#form" className={s.heroCta}>
                Demander un rapport
              </a>
            </div>
            <div className={s.heroVisual}>
              <div className={s.monitor}>
                <div className={s.monitorHeader}>
                  <span className={s.monitorDot} />
                  <span className={s.monitorTitle}>Lyon &mdash; Temps réel</span>
                </div>
                {MONITOR_ZONES.map((z, i) => (
                  <div key={z.name} className={s.monitorRow}>
                    <span className={s.monitorZone}>{z.name}</span>
                    <div className={s.monitorTrack}>
                      <div
                        className={s.monitorBar}
                        style={{
                          width: `${z.score}%`,
                          backgroundColor: scoreColor(z.score),
                          animationDelay: `${i * 0.12}s`,
                        }}
                      />
                    </div>
                    <span className={s.monitorScore} style={{ color: scoreColor(z.score) }}>
                      {z.score}
                    </span>
                    <span className={s.monitorLevel} style={{ color: scoreColor(z.score) }}>
                      {scoreLevel(z.score)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ─── BACKTEST ─── */}
        <section className={s.backtest} id="proof">
          <div className={s.sectionInner}>
            <span className={s.sectionLabel}>Preuve</span>
            <h2 className={s.sectionTitle}>
              Ce que l&apos;outil a détecté &mdash; Match OL, 8 mars 2026
            </h2>

            <div className={s.chartContainer}>
              <svg
                viewBox={`0 0 ${CW} 300`}
                className={s.chartSvg}
                preserveAspectRatio="xMidYMid meet"
                role="img"
                aria-label="Timeline des scores de tension urbaine avant et après un match OL"
              >
                {/* Level background bands */}
                <rect x={0} y={CT} width={CW} height={toY(72) - CT} fill="rgba(239,68,68,0.06)" />
                <rect x={0} y={toY(72)} width={CW} height={toY(55) - toY(72)} fill="rgba(249,115,22,0.05)" />
                <rect x={0} y={toY(55)} width={CW} height={toY(35) - toY(55)} fill="rgba(234,179,8,0.04)" />
                <rect x={0} y={toY(35)} width={CW} height={CB - toY(35)} fill="rgba(34,197,94,0.03)" />

                {/* Threshold lines */}
                <line x1={0} y1={toY(72)} x2={CW} y2={toY(72)} stroke="#ef4444" strokeWidth={0.5} strokeDasharray="4 4" opacity={0.5} />
                <line x1={0} y1={toY(55)} x2={CW} y2={toY(55)} stroke="#f97316" strokeWidth={0.5} strokeDasharray="4 4" opacity={0.4} />
                <line x1={0} y1={toY(35)} x2={CW} y2={toY(35)} stroke="#eab308" strokeWidth={0.5} strokeDasharray="4 4" opacity={0.3} />

                {/* Threshold labels */}
                <text x={CW - 4} y={toY(72) - 4} textAnchor="end" fill="#ef4444" fontSize={8} opacity={0.6} fontFamily="system-ui, sans-serif">CRITIQUE</text>
                <text x={CW - 4} y={toY(55) - 4} textAnchor="end" fill="#f97316" fontSize={8} opacity={0.5} fontFamily="system-ui, sans-serif">TENDU</text>
                <text x={CW - 4} y={toY(35) - 4} textAnchor="end" fill="#eab308" fontSize={8} opacity={0.4} fontFamily="system-ui, sans-serif">MODÉRÉ</text>

                {/* Annotation: T-2h alert */}
                <line x1={toX(2)} y1={CT} x2={toX(2)} y2={CB} stroke="#e8830a" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
                <text x={toX(2) + 5} y={CT - 8} fill="#e8830a" fontSize={9} fontWeight={600} fontFamily="system-ui, sans-serif">
                  Alerte détectée &mdash; 2h avant
                </text>

                {/* Annotation: T-30min peak */}
                <line x1={toX(5)} y1={CT} x2={toX(5)} y2={CB} stroke="#ef4444" strokeWidth={1} strokeDasharray="3 3" opacity={0.6} />
                <text x={toX(5) + 5} y={CT - 8} fill="#ef4444" fontSize={9} fontWeight={600} fontFamily="system-ui, sans-serif">
                  Pic CRITIQUE &mdash; 85/100
                </text>

                {/* Zone polylines */}
                {BACKTEST_ZONES.map((zone, zi) => (
                  <g key={zone.name} className={zi === 2 ? s.chartZoneThird : undefined}>
                    <polyline
                      points={polyline(zone.scores)}
                      fill="none"
                      stroke={zone.color}
                      strokeWidth={2.5}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                    />
                    {zone.scores.map((sc, i) => (
                      <circle key={i} cx={toX(i)} cy={toY(sc)} r={3} fill={zone.color} />
                    ))}
                  </g>
                ))}

                {/* Time labels */}
                {TIME_LABELS.map((label, i) => (
                  <text
                    key={i}
                    x={toX(i)}
                    y={CB + 20}
                    textAnchor="middle"
                    fill="#6b7280"
                    fontSize={10}
                    fontFamily="system-ui, sans-serif"
                    className={i % 2 === 1 ? s.chartLabelOdd : undefined}
                  >
                    {label}
                  </text>
                ))}
              </svg>
            </div>

            {/* Legend */}
            <div className={s.chartLegend}>
              {BACKTEST_ZONES.map((zone, zi) => (
                <div key={zone.name} className={`${s.legendItem} ${zi === 2 ? s.legendThird : ""}`}>
                  <span className={s.legendLine} style={{ backgroundColor: zone.color }} />
                  <span>{zone.name}</span>
                  <span className={s.legendSub}>{zone.sub}</span>
                </div>
              ))}
            </div>

            <p className={s.backtestCaption}>
              Un responsable exploitation aurait pu ajuster son dispositif 2 heures avant. Pas pendant.
            </p>
          </div>
        </section>

        {/* ─── STEPS ─── */}
        <section className={s.steps}>
          <div className={s.sectionInner}>
            <span className={s.sectionLabel}>Comment ça marche</span>
            <h2 className={s.sectionTitle}>3 étapes, zéro complexité</h2>
            <div className={s.stepsGrid}>
              {STEPS.map((step) => (
                <div key={step.num} className={s.step}>
                  <div className={s.stepNum}>{step.num}</div>
                  <h3 className={s.stepTitle}>{step.title}</h3>
                  <p className={s.stepDesc}>{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ─── PRICING ─── */}
        <section className={s.pricing} id="pricing">
          <div className={s.sectionInner}>
            <span className={s.sectionLabel}>Tarifs</span>
            <h2 className={s.sectionTitle}>Deux formules, un objectif</h2>
            <div className={s.pricingGrid}>
              {/* Tier 1 */}
              <div className={`${s.tier} ${s.tierAccent}`}>
                <div className={s.tierBadge}>Recommandé</div>
                <h3 className={s.tierName}>Rapport Événement</h3>
                <div className={s.tierPrice}>
                  <span className={s.tierAmount}>390€</span>
                  <span className={s.tierPeriod}>HT / événement</span>
                </div>
                <ul className={s.tierFeatures}>
                  <li>Rapport PDF anticipation &mdash; 2 pages</li>
                  <li>Accès dashboard live 48h avant &rarr; 24h après</li>
                  <li>Analyse multi-signal sur vos zones</li>
                  <li>Facture unique, aucun engagement</li>
                </ul>
                <a href="#form" className={s.tierCtaPrimary}>
                  Demander un rapport
                </a>
              </div>

              {/* Tier 2 */}
              <div className={s.tier}>
                <h3 className={s.tierName}>Abonnement Mensuel</h3>
                <div className={s.tierPrice}>
                  <span className={s.tierAmount}>490€</span>
                  <span className={s.tierPeriod}>HT / mois</span>
                </div>
                <ul className={s.tierFeatures}>
                  <li>Accès continu &mdash; 12 zones Lyon</li>
                  <li>Alertes email sur seuil configurable</li>
                  <li>Export PDF hebdomadaire</li>
                  <li>Résiliable à tout moment</li>
                </ul>
                <p className={s.tierNote}>Dès 2 événements par mois, l&apos;abonnement est plus rentable.</p>
                <a href="#form" className={s.tierCtaSecondary}>
                  Nous contacter
                </a>
              </div>
            </div>
            <p className={s.pricingAnchor}>
              Un agent de sécurité supplémentaire coûte ~3&nbsp;000€/mois.
              Un rapport Urban Signal coûte 390€.
            </p>
          </div>
        </section>

        {/* ─── FORM ─── */}
        <section className={s.formSection} id="form">
          <div className={s.sectionInner}>
            <div className={s.formGrid}>
              <div className={s.formInfo}>
                <span className={s.sectionLabel}>Contact</span>
                <h2 className={s.sectionTitle}>Demandez un rapport</h2>
                <p className={s.formInfoText}>
                  Décrivez votre prochain événement. On vous recontacte sous 24h
                  avec une proposition adaptée.
                </p>
              </div>
              <div className={s.formCard}>
                <ContactForm />
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ─── FOOTER ─── */}
      <footer className={s.footer}>
        <div className={s.footerInner}>
          <div className={s.footerBrand}>
            <span className={s.footerLogo}>Urban Signal Engine</span>
            <span className={s.footerLocation}>Lyon, France</span>
          </div>
          <div className={s.footerLinks}>
            <a href="mailto:contact@urbanscoreengine.com">contact@urbanscoreengine.com</a>
            <a href="/mentions-legales">Mentions légales</a>
          </div>
          <span className={s.footerCopy}>&copy; 2026 Urban Signal Engine</span>
        </div>
      </footer>
    </div>
  );
}

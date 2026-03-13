import Link from "next/link";

type Props = {
  simDate: string;
  events?: string[];
  zoneId?: string;
};

export default function SimBanner({ simDate, events, zoneId }: Props) {
  return (
    <>
      {events && events.length > 0 && (
        <div style={{ background: "#1a1d2799", borderBottom: "1px solid #f9731633", padding: "6px 24px", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#64748b" }}>ÉVÉNEMENTS ACTIFS :</span>
          {events.map((e, i) => (
            <span key={i} style={{ fontSize: 10, color: "#f97316", background: "#f9731611", border: "1px solid #f9731633", borderRadius: 4, padding: "1px 8px" }}>{e}</span>
          ))}
        </div>
      )}

      {zoneId && (
        <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #f9731622", textAlign: "center" }}>
          <div style={{ fontSize: 11, color: "#64748b" }}>
            Simulation · l'historique et les prévisions ne sont pas disponibles en mode simulation.
          </div>
          <Link href={`/zones/${zoneId}`} style={{ fontSize: 11, color: "#a5b4fc", marginTop: 8, display: "inline-block" }}>
            Voir les données live →
          </Link>
        </div>
      )}
    </>
  );
}

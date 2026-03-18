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
        <div className="flex flex-wrap items-center gap-2 border-b border-[#f9731633] bg-bg-card px-6 py-1.5">
          <span className="text-[10px] text-text-muted">ÉVÉNEMENTS ACTIFS :</span>
          {events.map((e, i) => (
            <span key={i} className="rounded border border-[#f9731633] bg-[#f9731611] px-2 py-px text-[10px] text-[#f97316]">{e}</span>
          ))}
        </div>
      )}

      {zoneId && (
        <div className="rounded-xl border border-[#f9731622] bg-bg-card p-5 text-center">
          <div className="text-[11px] text-text-muted">
            Simulation · l&apos;historique et les prévisions ne sont pas disponibles en mode simulation.
          </div>
          <Link href={`/zones/${zoneId}`} className="mt-2 inline-block text-[11px] text-accent-text">
            Voir les données live →
          </Link>
        </div>
      )}
    </>
  );
}

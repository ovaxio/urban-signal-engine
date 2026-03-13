import type { ZoneSummary } from "@/domain/types";
import ZoneCard from "./ZoneCard";

type Props = {
  zones: ZoneSummary[];
  simDate?: string;
};

export default function ZoneGrid({ zones, simDate }: Props) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10, minWidth: 0 }}>
      {zones.length === 0 ? (
        <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: 32, color: "#94a3b8", fontSize: 12 }}>
          Aucune zone ne correspond au filtre sélectionné.
        </div>
      ) : (
        zones.map(z => <ZoneCard key={z.zone_id} zone={z} simDate={simDate} />)
      )}
    </div>
  );
}

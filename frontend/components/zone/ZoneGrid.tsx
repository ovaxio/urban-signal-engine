import type { ZoneSummary } from "@/domain/types";
import ZoneCard from "./ZoneCard";

type Props = {
  zones: ZoneSummary[];
  simDate?: string;
};

export default function ZoneGrid({ zones, simDate }: Props) {
  return (
    <div className="grid min-w-0 grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2.5">
      {zones.length === 0 ? (
        <div className="col-span-full p-8 text-center text-xs text-text-secondary">
          Aucune zone ne correspond au filtre sélectionné.
        </div>
      ) : (
        zones.map(z => <ZoneCard key={z.zone_id} zone={z} simDate={simDate} />)
      )}
    </div>
  );
}

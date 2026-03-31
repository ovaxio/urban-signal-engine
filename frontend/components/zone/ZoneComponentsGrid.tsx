import type { ZoneComponents } from "@/domain/types";

const COMPONENTS_CONFIG: { key: keyof ZoneComponents; label: string; tooltip: string }[] = [
  { key: "risk",    label: "Risque global",       tooltip: "Niveau de risque pondéré par tous les facteurs" },
  { key: "anomaly", label: "Pics d'activité",     tooltip: "Activité anormalement élevée sur un ou plusieurs facteurs" },
  { key: "conv",    label: "Cumul de facteurs",   tooltip: "Plusieurs facteurs élevés en même temps" },
  { key: "spread",  label: "Tension alentour",    tooltip: "Influence des zones voisines en tension" },
];

function componentLevel(value: number): { label: string; color: string } {
  if (value < 0.2) return { label: "Aucun",  color: "#71717a" };
  if (value < 0.5) return { label: "Faible", color: "#22c55e" };
  if (value < 1.0) return { label: "Modéré", color: "#eab308" };
  if (value < 1.8) return { label: "Élevé",  color: "#f97316" };
  return               { label: "Fort",   color: "#ef4444" };
}

type Props = {
  components: ZoneComponents;
};

export default function ZoneComponentsGrid({ components }: Props) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-3.5 text-[10px] font-semibold tracking-widest text-text-muted">CE QUI CONTRIBUE AU SCORE</div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-2">
        {COMPONENTS_CONFIG.map(({ key, label, tooltip }) => {
          const val = components[key] ?? 0;
          const { label: lvl, color } = componentLevel(val);
          return (
            <div key={key} className="rounded-lg bg-bg-inner p-3 text-center" title={tooltip}>
              <div className="mb-1 text-[9px] tracking-wide text-text-muted">{label}</div>
              <div className="text-base font-bold" style={{ color }}>{lvl}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

import type { FilterLevel, ZoneSummary } from "@/domain/types";

type Props = {
  filter: FilterLevel;
  zones: ZoneSummary[];
  onFilterChange: (f: FilterLevel) => void;
};

const FILTER_OPTIONS: { key: FilterLevel; label: string; minScore?: number }[] = [
  { key: "all",      label: "Toutes les zones" },
  { key: "TENDU",    label: "Sous tension",    minScore: 55 },
  { key: "CRITIQUE", label: "Critiques",       minScore: 72 },
];

export default function FilterBar({ filter, zones, onFilterChange }: Props) {
  return (
    <div role="group" aria-label="Filtrer par niveau" className="mb-3 flex gap-2">
      {FILTER_OPTIONS.map(f => {
        const active = filter === f.key;
        const count = f.minScore ? zones.filter(z => z.urban_score >= f.minScore!).length : undefined;
        return (
          <button
            key={f.key}
            onClick={() => onFilterChange(f.key)}
            aria-pressed={active}
            className={`min-h-9 cursor-pointer rounded-md border px-4 py-2 text-[11px] font-semibold ${
              active
                ? "border-accent bg-accent text-accent-text opacity-85"
                : "border-border bg-bg-control text-text-secondary"
            }`}
          >
            {f.label}{count !== undefined ? ` (${count})` : ""}
          </button>
        );
      })}
    </div>
  );
}

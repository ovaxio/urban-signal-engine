import type { FilterLevel, ZoneSummary } from "@/domain/types";

type Props = {
  filter: FilterLevel;
  zones: ZoneSummary[];
  onFilterChange: (f: FilterLevel) => void;
};

const FILTER_OPTIONS: { key: FilterLevel; label: string; minScore?: number }[] = [
  { key: "all",      label: "TOUTES" },
  { key: "TENDU",    label: "TENDU+",    minScore: 55 },
  { key: "CRITIQUE", label: "CRITIQUE",  minScore: 72 },
];

export default function FilterBar({ filter, zones, onFilterChange }: Props) {
  return (
    <div role="group" aria-label="Filtrer par niveau" style={{ display: "flex", gap: 8, marginBottom: 12 }}>
      {FILTER_OPTIONS.map(f => {
        const count = f.minScore ? zones.filter(z => z.urban_score >= f.minScore!).length : undefined;
        return (
          <button
            key={f.key}
            onClick={() => onFilterChange(f.key)}
            aria-pressed={filter === f.key}
            style={{
              fontSize: 11, fontWeight: 600, padding: "8px 16px", borderRadius: 6, cursor: "pointer", minHeight: 36,
              border: filter === f.key ? "1px solid #6366f1" : "1px solid #2d3148",
              background: filter === f.key ? "#6366f122" : "#1e2235",
              color: filter === f.key ? "#a5b4fc" : "#94a3b8",
            }}
          >
            {f.label}{count !== undefined ? ` (${count})` : ""}
          </button>
        );
      })}
    </div>
  );
}

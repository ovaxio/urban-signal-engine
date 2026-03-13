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
              border: filter === f.key ? "1px solid var(--accent)" : "1px solid var(--border)",
              background: filter === f.key ? "var(--accent)" : "var(--bg-control)",
              color: filter === f.key ? "var(--accent-text)" : "var(--text-secondary)",
              opacity: filter === f.key ? 0.85 : 1,
            }}
          >
            {f.label}{count !== undefined ? ` (${count})` : ""}
          </button>
        );
      })}
    </div>
  );
}

import type { ZoneComponents } from "@/domain/types";
import { COMPONENT_KEYS } from "@/domain/constants";

type Props = {
  components: ZoneComponents;
};

export default function ZoneComponentsGrid({ components }: Props) {
  return (
    <div style={{ background: "var(--bg-card)", borderRadius: 12, padding: 20, border: "1px solid var(--border)" }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>COMPOSANTES</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 8 }}>
        {COMPONENT_KEYS.map(k => (
          <div key={k} style={{ textAlign: "center", padding: 12, background: "var(--bg-inner)", borderRadius: 8 }}>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.06em" }}>{k.toUpperCase()}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--accent-text)" }}>{components[k].toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

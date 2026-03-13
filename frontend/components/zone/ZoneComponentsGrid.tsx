import type { ZoneComponents } from "@/domain/types";
import { COMPONENT_KEYS } from "@/domain/constants";

type Props = {
  components: ZoneComponents;
};

export default function ZoneComponentsGrid({ components }: Props) {
  return (
    <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #2d3148" }}>
      <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>COMPOSANTES</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 8 }}>
        {COMPONENT_KEYS.map(k => (
          <div key={k} style={{ textAlign: "center", padding: 12, background: "#13161f", borderRadius: 8 }}>
            <div style={{ fontSize: 9, color: "#64748b", marginBottom: 4, letterSpacing: "0.06em" }}>{k.toUpperCase()}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#a5b4fc" }}>{components[k].toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

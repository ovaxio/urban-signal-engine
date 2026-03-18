import type { ZoneComponents } from "@/domain/types";
import { COMPONENT_KEYS } from "@/domain/constants";

type Props = {
  components: ZoneComponents;
};

export default function ZoneComponentsGrid({ components }: Props) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-3.5 text-[10px] font-semibold tracking-widest text-text-muted">COMPOSANTES</div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(100px,1fr))] gap-2">
        {COMPONENT_KEYS.map(k => (
          <div key={k} className="rounded-lg bg-bg-inner p-3 text-center">
            <div className="mb-1 text-[9px] tracking-wide text-text-muted">{k.toUpperCase()}</div>
            <div className="text-lg font-bold text-accent-text">{components[k].toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

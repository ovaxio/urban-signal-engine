type Props = {
  pct: number;
  color: string;
  height?: number;
};

export default function ScoreBar({ pct, color, height = 3 }: Props) {
  return (
    <div style={{ height, background: "var(--bg-control)", borderRadius: height, marginBottom: 10 }}>
      <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: height, transition: "width 0.5s" }} />
    </div>
  );
}

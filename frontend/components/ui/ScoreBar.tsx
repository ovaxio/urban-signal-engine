type Props = {
  pct: number;
  color: string;
  height?: number;
};

export default function ScoreBar({ pct, color, height = 3 }: Props) {
  return (
    <div className="mb-2.5 rounded-full bg-bg-control" style={{ height }}>
      <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${pct}%`, background: color, borderRadius: height }} />
    </div>
  );
}

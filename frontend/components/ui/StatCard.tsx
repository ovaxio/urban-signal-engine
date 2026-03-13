type Props = {
  label: string;
  value: string | number;
  color?: string;
};

export default function StatCard({ label, value, color = "#64748b" }: Props) {
  return (
    <div style={{ background: "#1a1d27", border: "1px solid #2d3148", borderRadius: 8, padding: "10px 16px", flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 9, color: "#94a3b8", letterSpacing: "0.08em", marginBottom: 4 }}>{label.toUpperCase()}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</div>
    </div>
  );
}

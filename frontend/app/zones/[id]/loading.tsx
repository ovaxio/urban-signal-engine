export default function ZoneDetailLoading() {
  return (
    <div style={{ minHeight: "100vh" }}>
      <div style={{ maxWidth: 700, margin: "0 auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="skeleton" style={{ height: 80, borderRadius: 12 }} />
        <div className="skeleton" style={{ height: 160, borderRadius: 12 }} />
        <div className="skeleton" style={{ height: 120, borderRadius: 12 }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 10 }}>
          {[1, 2, 3, 4, 5].map(i => <div key={i} className="skeleton" style={{ height: 70, borderRadius: 8 }} />)}
        </div>
      </div>
    </div>
  );
}

export default function DashboardLoading() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", fontFamily: "monospace" }}>
      <div style={{ padding: "16px 24px", maxWidth: 960, margin: "0 auto", width: "100%", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ textAlign: "center", padding: "12px 0", fontSize: 12, color: "var(--text-muted)", letterSpacing: "0.04em" }}>
          Chargement du tableau de bord…
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {[1, 2, 3, 4].map(i => <div key={i} className="skeleton" style={{ height: 52, flex: 1, minWidth: 120 }} />)}
        </div>
        <div className="skeleton" style={{ height: 420, borderRadius: 12 }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
          {[1, 2, 3, 4, 5, 6].map(i => <div key={i} className="skeleton" style={{ height: 140, borderRadius: 10 }} />)}
        </div>
      </div>
    </div>
  );
}

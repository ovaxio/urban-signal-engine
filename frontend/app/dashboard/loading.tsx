export default function DashboardLoading() {
  return (
    <div className="flex min-h-screen flex-col font-mono">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-4 p-4 px-6">
        <div className="py-3 text-center text-xs tracking-wide text-text-muted">
          Chargement du tableau de bord…
        </div>
        <div className="flex flex-wrap gap-3">
          {[1, 2, 3, 4].map(i => <div key={i} className="skeleton min-w-[120px] flex-1" style={{ height: 52 }} />)}
        </div>
        <div className="skeleton rounded-xl" style={{ height: 420 }} />
        <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2.5">
          {[1, 2, 3, 4, 5, 6].map(i => <div key={i} className="skeleton rounded-[10px]" style={{ height: 140 }} />)}
        </div>
      </div>
    </div>
  );
}

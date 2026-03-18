export default function ZoneDetailLoading() {
  return (
    <div className="min-h-screen">
      <div className="mx-auto flex max-w-[700px] flex-col gap-4 p-6">
        <div className="skeleton rounded-xl" style={{ height: 80 }} />
        <div className="skeleton rounded-xl" style={{ height: 160 }} />
        <div className="skeleton rounded-xl" style={{ height: 120 }} />
        <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-2.5">
          {[1, 2, 3, 4, 5].map(i => <div key={i} className="skeleton rounded-lg" style={{ height: 70 }} />)}
        </div>
      </div>
    </div>
  );
}

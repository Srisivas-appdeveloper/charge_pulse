export default function HealthBadge({ score }) {
  const s = Math.round(score ?? 0);
  let color = "bg-emerald-500";
  if (s < 90) color = "bg-amber-500";
  if (s < 70) color = "bg-orange-500";
  if (s < 50) color = "bg-red-500";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium text-white ${color}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-white/80" />
      {s}
    </span>
  );
}

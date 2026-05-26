const COLORS = {
  online: "bg-emerald-500",
  offline: "bg-gray-400",
  faulted: "bg-red-500",
  unknown: "bg-gray-300",
};

export default function ChargerStatusDot({ status }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-gray-700">
      <span className={`w-2 h-2 rounded-full ${COLORS[status] || COLORS.unknown}`} />
      {status}
    </span>
  );
}

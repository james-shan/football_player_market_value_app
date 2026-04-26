import clsx from "clsx";

type Props = {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "neutral" | "positive" | "negative" | "accent";
  className?: string;
};

export default function MetricCard({
  label,
  value,
  hint,
  tone = "neutral",
  className,
}: Props) {
  const toneClass =
    tone === "positive"
      ? "text-emerald-400"
      : tone === "negative"
        ? "text-rose-400"
        : tone === "accent"
          ? "text-indigo-300"
          : "text-white";
  return (
    <div
      className={clsx(
        "rounded-lg border border-ink-800 bg-ink-900/50 p-4",
        className,
      )}
    >
      <div className="text-xs uppercase tracking-wide text-ink-400">
        {label}
      </div>
      <div className={clsx("mt-1 text-xl font-semibold", toneClass)}>
        {value}
      </div>
      {hint ? <div className="mt-1 text-xs text-ink-400">{hint}</div> : null}
    </div>
  );
}

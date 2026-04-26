/** Formatting helpers used across the UI. */

const FALLBACK = "—";

export function formatEuro(
  value: number | null | undefined,
  opts: { fallback?: string } = {},
): string {
  const fallback = opts.fallback ?? FALLBACK;
  if (value == null || !Number.isFinite(value)) return fallback;
  if (Math.abs(value) >= 1_000_000) {
    return `€${(value / 1_000_000).toFixed(value >= 10_000_000 ? 1 : 2)}m`;
  }
  if (Math.abs(value) >= 1_000) {
    return `€${(value / 1_000).toFixed(0)}k`;
  }
  return `€${Math.round(value)}`;
}

export function formatEuroFull(
  value: number | null | undefined,
  opts: { fallback?: string } = {},
): string {
  const fallback = opts.fallback ?? FALLBACK;
  if (value == null || !Number.isFinite(value)) return fallback;
  return `€${Math.round(value).toLocaleString()}`;
}

export function formatPercent(
  value: number | null | undefined,
  opts: { fallback?: string; signed?: boolean; digits?: number } = {},
): string {
  const fallback = opts.fallback ?? FALLBACK;
  if (value == null || !Number.isFinite(value)) return fallback;
  const digits = opts.digits ?? 1;
  const out = `${(value * 100).toFixed(digits)}%`;
  if (opts.signed && value > 0) return `+${out}`;
  return out;
}

export function formatRate(
  value: number | null | undefined,
  opts: { fallback?: string; digits?: number } = {},
): string {
  const fallback = opts.fallback ?? FALLBACK;
  if (value == null || !Number.isFinite(value)) return fallback;
  return value.toFixed(opts.digits ?? 2);
}

export function formatCount(
  value: number | null | undefined,
  opts: { fallback?: string } = {},
): string {
  const fallback = opts.fallback ?? FALLBACK;
  if (value == null || !Number.isFinite(value)) return fallback;
  return Math.round(value).toLocaleString();
}

export function formatAge(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return FALLBACK;
  return Math.round(value).toString();
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

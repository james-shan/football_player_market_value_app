"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CohortRow } from "@/lib/types";
import type { PercentileMetric, StatFormat } from "@/lib/positionConfig";
import { formatCount, formatPercent, formatRate } from "@/lib/format";
import { leagueLabel, positionLabel } from "@/lib/labels";

type Props = {
  player: CohortRow | null;
  cohort: CohortRow[];
  metrics: PercentileMetric[];
  positionCode: string | null;
  leagueId: number | null;
};

type Datum = {
  label: string;
  percentile: number | null;
  rawValue: number | null;
  cohortN: number;
  format: StatFormat;
};

/**
 * Computes 0–100 percentile rank ("X% of peers are at or below"), restricted
 * to peers with a non-null value for the metric so missing data does not
 * unfairly inflate or deflate the player's position.
 */
function percentileFor(
  metric: PercentileMetric,
  player: CohortRow,
  cohort: CohortRow[],
): { value: number | null; rawValue: number | null; cohortN: number } {
  const raw = player[metric.key as keyof CohortRow] as number | null;
  if (raw == null || !Number.isFinite(raw)) {
    return { value: null, rawValue: null, cohortN: 0 };
  }
  const peerValues = cohort
    .map((p) => p[metric.key as keyof CohortRow] as number | null)
    .filter((v): v is number => v != null && Number.isFinite(v));
  if (peerValues.length < 2) {
    return { value: null, rawValue: raw, cohortN: peerValues.length };
  }
  const n = peerValues.length;
  let belowOrEqual = 0;
  for (const v of peerValues) {
    if (v <= raw) belowOrEqual += 1;
  }
  let pct = (belowOrEqual / n) * 100;
  if (metric.lowerIsBetter) pct = 100 - pct;
  return { value: pct, rawValue: raw, cohortN: n };
}

function formatStat(value: number | null, format: StatFormat): string {
  if (value == null) return "—";
  if (format === "percent") return formatPercent(value, { digits: 1 });
  if (format === "count") return formatCount(value);
  return formatRate(value);
}

function colorFor(percentile: number | null): string {
  if (percentile == null) return "#475569";
  if (percentile >= 75) return "#10b981";
  if (percentile >= 50) return "#22d3ee";
  if (percentile >= 25) return "#f59e0b";
  return "#f43f5e";
}

export default function PercentileChart({
  player,
  cohort,
  metrics,
  positionCode,
  leagueId,
}: Props) {
  if (!player || cohort.length < 3) {
    return (
      <div className="rounded-lg border border-ink-800 bg-ink-900/40 p-4">
        <Header positionCode={positionCode} leagueId={leagueId} cohortN={cohort.length} />
        <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-ink-700 text-sm text-ink-400">
          Not enough peers to compute percentiles.
        </div>
      </div>
    );
  }

  const data: Datum[] = metrics.map((m) => {
    const { value, rawValue, cohortN } = percentileFor(m, player, cohort);
    return {
      label: m.label,
      percentile: value,
      rawValue,
      cohortN,
      format: m.format,
    };
  });

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40 p-4">
      <Header positionCode={positionCode} leagueId={leagueId} cohortN={cohort.length} />
      <div style={{ width: "100%", height: Math.max(220, metrics.length * 40) }}>
        <ResponsiveContainer>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 8, right: 28, bottom: 8, left: 8 }}
          >
            <CartesianGrid stroke="#1f2937" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tickFormatter={(v) => `${v}`}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              stroke="#334155"
            />
            <YAxis
              dataKey="label"
              type="category"
              width={150}
              tick={{ fill: "#cbd5e1", fontSize: 12 }}
              stroke="#334155"
            />
            <Tooltip content={<PercentileTooltip />} />
            <Bar dataKey="percentile" radius={[0, 3, 3, 0]} isAnimationActive={false}>
              {data.map((d, i) => (
                <Cell key={i} fill={colorFor(d.percentile)} fillOpacity={0.9} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] text-ink-400">
        <LegendSwatch color="#f43f5e" label="Bottom 25%" />
        <LegendSwatch color="#f59e0b" label="25–50%" />
        <LegendSwatch color="#22d3ee" label="50–75%" />
        <LegendSwatch color="#10b981" label="Top 25%" />
      </div>
    </div>
  );
}

function Header({
  positionCode,
  leagueId,
  cohortN,
}: {
  positionCode: string | null;
  leagueId: number | null;
  cohortN: number;
}) {
  return (
    <div className="mb-3">
      <div className="text-sm font-medium text-white">
        Percentile vs League + Position
      </div>
      <div className="text-xs text-ink-400">
        Ranked against {cohortN.toLocaleString()} {positionLabel(positionCode)}s in{" "}
        {leagueLabel(leagueId)} for 2025-26.
      </div>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-3 rounded-sm"
        style={{ background: color }}
      />
      {label}
    </span>
  );
}

function PercentileTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: unknown[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const first = payload[0] as { payload: Datum };
  const d = first.payload;
  return (
    <div className="rounded-md border border-ink-700 bg-ink-900/95 px-3 py-2 text-xs shadow-lg">
      <div className="font-medium text-white">{d.label}</div>
      <div className="mt-1 text-ink-300">
        <span className="text-ink-400">Value: </span>
        <span className="text-white">{formatStat(d.rawValue, d.format)}</span>
      </div>
      <div className="text-ink-300">
        <span className="text-ink-400">Percentile: </span>
        <span className="text-white">
          {d.percentile == null ? "—" : `${d.percentile.toFixed(0)}`}
        </span>
      </div>
      <div className="text-[11px] text-ink-500">vs {d.cohortN} peers</div>
    </div>
  );
}

"use client";

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatEuro, formatEuroFull } from "@/lib/format";
import type { PlayerSeasonRow } from "@/lib/types";

type Point = {
  season: number;
  actual: number | null;
  projected: number | null;
  bridge: number | null;
  team: string | null;
  label: string;
  rawValue: number | null;
};

function toPoints(seasons: PlayerSeasonRow[]): Point[] {
  return seasons.map((s) => {
    const isProjection = s.is_projection;
    // Pre-2025 rows: actuals from target_market_value_eur.
    // 2025 row: actual = NULL (no end-of-season actual yet), projected = predicted_market_value_eur.
    const actual = !isProjection ? s.target_market_value_eur : null;
    const projected = isProjection ? s.predicted_market_value_eur : null;
    const v = isProjection ? projected : actual;
    return {
      season: s.season,
      actual,
      projected,
      bridge: null,
      team: s.team_name,
      label: isProjection ? "Projected end-of-season value" : "Actual market value",
      rawValue: v,
    };
  });
}

export default function MarketValueChart({
  seasons,
}: {
  seasons: PlayerSeasonRow[];
}) {
  const data = toPoints(seasons).filter((p) => p.rawValue != null);
  if (data.length === 0) {
    return (
      <EmptyChart message="No market value history available for this player." />
    );
  }

  // Splice a `bridge` series into the existing rows so the dashed connector
  // is anchored on the same X-axis as the rest of the timeline. Recharts
  // would otherwise re-index a separate `data` prop and pin the line to the
  // first/last category, which is what was making it appear stuck on the
  // y-axis.
  const lastActualIdx = (() => {
    for (let i = data.length - 1; i >= 0; i -= 1) {
      if (data[i].actual != null) return i;
    }
    return -1;
  })();
  const projectionIdx = data.findIndex((d) => d.projected != null);
  const hasBridge =
    lastActualIdx !== -1 &&
    projectionIdx !== -1 &&
    projectionIdx !== lastActualIdx;
  if (hasBridge) {
    data[lastActualIdx].bridge = data[lastActualIdx].actual;
    data[projectionIdx].bridge = data[projectionIdx].projected;
  }

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-white">Market Value Timeline</div>
          <div className="text-xs text-ink-400">
            Historical actuals · 2025-26 projected end-of-season value
          </div>
        </div>
        <Legend />
      </div>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="#1f2937" vertical={false} />
            <XAxis
              dataKey="season"
              type="number"
              domain={["dataMin", "dataMax"]}
              allowDecimals={false}
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              stroke="#334155"
              tickFormatter={(v) => `${v}-${(v + 1) % 100}`}
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              stroke="#334155"
              tickFormatter={(v) => formatEuro(Number(v))}
              width={70}
            />
            <Tooltip content={<MVTooltip />} />
            <Line
              type="monotone"
              dataKey="actual"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 3, fill: "#10b981" }}
              activeDot={{ r: 5 }}
              connectNulls
              isAnimationActive={false}
              name="Actual"
            />
            {hasBridge ? (
              <Line
                type="linear"
                dataKey="bridge"
                stroke="#6366f1"
                strokeDasharray="6 4"
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
                name="Projection bridge"
                legendType="none"
              />
            ) : null}
            <Scatter
              dataKey="projected"
              fill="#6366f1"
              shape="diamond"
              name="Projected"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex items-center gap-4 text-xs text-ink-300">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-4 rounded-sm bg-emerald-500" />
        Actual
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-4 rounded-sm bg-indigo-500" />
        Projected end-of-season
      </span>
    </div>
  );
}

function MVTooltip({ active, payload }: { active?: boolean; payload?: unknown[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const first = payload[0] as { payload: Point };
  const p = first.payload;
  return (
    <div className="rounded-md border border-ink-700 bg-ink-900/95 px-3 py-2 text-xs shadow-lg">
      <div className="font-medium text-white">
        {p.season}-{(p.season + 1) % 100}
      </div>
      {p.team ? <div className="text-ink-300">{p.team}</div> : null}
      <div className="mt-1 text-ink-300">
        <span className="text-ink-400">{p.label}: </span>
        <span className="text-white">{formatEuroFull(p.rawValue)}</span>
      </div>
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-ink-700 bg-ink-900/30 text-sm text-ink-400">
      {message}
    </div>
  );
}

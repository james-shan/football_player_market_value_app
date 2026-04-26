"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type StatSeries = {
  key: string;
  label: string;
  color: string;
};

type Datum = {
  season: number;
  [key: string]: number | string | null;
};

type Props = {
  title: string;
  description?: string;
  data: Datum[];
  series: StatSeries[];
  formatValue?: (v: number | null | undefined) => string;
  yTickFormatter?: (v: number) => string;
};

export default function StatChart({
  title,
  description,
  data,
  series,
  formatValue,
  yTickFormatter,
}: Props) {
  const filtered = data.filter((d) =>
    series.some((s) => {
      const v = d[s.key];
      return typeof v === "number" && Number.isFinite(v);
    }),
  );
  if (filtered.length === 0) return null;

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40 p-4">
      <div className="mb-3">
        <div className="text-sm font-medium text-white">{title}</div>
        {description ? (
          <div className="text-xs text-ink-400">{description}</div>
        ) : null}
      </div>
      <div style={{ width: "100%", height: 240 }}>
        <ResponsiveContainer>
          <BarChart data={filtered} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="#1f2937" vertical={false} />
            <XAxis
              dataKey="season"
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              stroke="#334155"
              tickFormatter={(v) => `${v}-${(v + 1) % 100}`}
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              stroke="#334155"
              tickFormatter={(v) =>
                yTickFormatter
                  ? yTickFormatter(Number(v))
                  : Math.round(Number(v)).toLocaleString()
              }
              width={56}
            />
            <Tooltip
              cursor={{ fill: "#1f293750" }}
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 6,
                fontSize: 12,
              }}
              formatter={(v) => {
                const n = typeof v === "number" ? v : Number(v);
                return formatValue
                  ? formatValue(n)
                  : Math.round(n).toLocaleString();
              }}
              labelFormatter={(v) => `${v}-${(Number(v) + 1) % 100}`}
            />
            {series.length > 1 ? (
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#cbd5e1" }}
                iconType="square"
              />
            ) : null}
            {series.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.label}
                fill={s.color}
                radius={[3, 3, 0, 0]}
                maxBarSize={40}
                isAnimationActive={false}
              >
                {series.length === 1
                  ? filtered.map((_, i) => (
                      <Cell key={i} fill={s.color} fillOpacity={0.85} />
                    ))
                  : null}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

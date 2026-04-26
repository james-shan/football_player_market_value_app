"use client";

import { useMemo } from "react";
import StatChart from "./StatChart";
import { getPositionConfig, type StatChartGroup } from "@/lib/positionConfig";
import type { PlayerSeasonRow } from "@/lib/types";
import { formatCount, formatPercent, formatRate } from "@/lib/format";

type Props = {
  positionCode: string | null;
  seasons: PlayerSeasonRow[];
};

function pick(seasons: PlayerSeasonRow[], group: StatChartGroup) {
  return seasons.map((s) => {
    const row: Record<string, number | string | null> = { season: s.season };
    for (const series of group.series) {
      row[series.key] = (s[series.key as keyof PlayerSeasonRow] as
        | number
        | null) ?? null;
    }
    return row;
  });
}

function makeFormatter(group: StatChartGroup) {
  if (group.format === "percent") {
    return (v: number | null | undefined) =>
      v == null ? "—" : formatPercent(v, { digits: 1 });
  }
  if (group.format === "rate") {
    return (v: number | null | undefined) =>
      v == null ? "—" : formatRate(v);
  }
  return (v: number | null | undefined) =>
    v == null ? "—" : formatCount(v);
}

export default function PositionStats({ positionCode, seasons }: Props) {
  const config = useMemo(() => getPositionConfig(positionCode), [positionCode]);

  // Build datasets and skip groups with no data so we don't render empty cards.
  const groups = useMemo(() => {
    return config.charts
      .map((group) => {
        const data = pick(seasons, group);
        const hasAny = data.some((row) =>
          group.series.some((s) => {
            const v = row[s.key];
            return typeof v === "number" && Number.isFinite(v);
          }),
        );
        return hasAny ? { group, data } : null;
      })
      .filter((x): x is { group: StatChartGroup; data: Record<string, number | string | null>[] } => x != null);
  }, [config, seasons]);

  if (groups.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {groups.map(({ group, data }) => (
        <StatChart
          key={group.title}
          title={group.title}
          description={group.description}
          data={data}
          series={group.series}
          formatValue={makeFormatter(group)}
          yTickFormatter={
            group.format === "percent"
              ? (v) => `${Math.round(v * 100)}%`
              : group.format === "rate"
                ? (v) => v.toFixed(2)
                : undefined
          }
        />
      ))}
    </div>
  );
}

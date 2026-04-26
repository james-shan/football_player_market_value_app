"use client";

import { useEffect, useMemo, useState } from "react";
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
import type { CurrentMappingRow, SquadRow } from "@/lib/types";
import {
  formatCount,
  formatEuro,
  formatPercent,
  formatRate,
} from "@/lib/format";
import { LEAGUE_NAMES, POSITION_LABELS, positionLabel } from "@/lib/labels";
import FilterBar from "./FilterBar";
import MetricCard from "./MetricCard";
import PlayerPhoto from "./PlayerPhoto";

export default function SquadOverview({
  mapping,
}: {
  mapping: CurrentMappingRow[];
}) {
  const [leagueId, setLeagueId] = useState<number | "">("");
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState<string>("");
  const [rows, setRows] = useState<SquadRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams();
    if (leagueId !== "") params.set("leagueId", String(leagueId));
    if (team) params.set("team", team);
    if (position) params.set("position", position);
    setLoading(true);
    fetch(`/api/squad?${params.toString()}`)
      .then((r) => r.json())
      .then((j: { rows: SquadRow[] }) => {
        if (!cancelled) setRows(j.rows ?? []);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, team, position]);

  const totals = useMemo(() => {
    const current = rows.reduce(
      (s, r) => s + (r.last_market_value_eur ?? 0),
      0,
    );
    const projected = rows.reduce(
      (s, r) => s + (r.predicted_market_value_eur ?? 0),
      0,
    );
    const eligible = rows.filter(
      (r) => r.projected_change_pct != null,
    );
    const avgChange =
      eligible.length === 0
        ? null
        : eligible.reduce((s, r) => s + (r.projected_change_pct ?? 0), 0) /
          eligible.length;

    const sortedByChange = [...eligible].sort(
      (a, b) => (b.projected_change_pct ?? 0) - (a.projected_change_pct ?? 0),
    );
    return {
      current,
      projected,
      avgChange,
      topRiser: sortedByChange[0] ?? null,
      topFaller: sortedByChange[sortedByChange.length - 1] ?? null,
    };
  }, [rows]);

  const byPosition = useMemo(() => {
    const groups: Record<
      string,
      { position: string; current: number; projected: number }
    > = {};
    for (const code of Object.keys(POSITION_LABELS)) {
      groups[code] = {
        position: POSITION_LABELS[code],
        current: 0,
        projected: 0,
      };
    }
    for (const r of rows) {
      const code = r.model_position && groups[r.model_position] ? r.model_position : null;
      if (!code) continue;
      groups[code].current += r.last_market_value_eur ?? 0;
      groups[code].projected += r.predicted_market_value_eur ?? 0;
    }
    return Object.values(groups);
  }, [rows]);

  const changeDistribution = useMemo(() => {
    const buckets = [
      { label: "<-25%", min: -Infinity, max: -0.25, count: 0 },
      { label: "-25 to -10%", min: -0.25, max: -0.1, count: 0 },
      { label: "-10 to 0%", min: -0.1, max: 0, count: 0 },
      { label: "0 to +10%", min: 0, max: 0.1, count: 0 },
      { label: "+10 to +25%", min: 0.1, max: 0.25, count: 0 },
      { label: "+25 to +50%", min: 0.25, max: 0.5, count: 0 },
      { label: ">+50%", min: 0.5, max: Infinity, count: 0 },
    ];
    for (const r of rows) {
      const c = r.projected_change_pct;
      if (c == null) continue;
      const b = buckets.find((b) => c >= b.min && c < b.max);
      if (b) b.count += 1;
    }
    return buckets;
  }, [rows]);

  const top10 = useMemo(
    () =>
      [...rows]
        .filter((r) => r.predicted_market_value_eur != null)
        .sort(
          (a, b) =>
            (b.predicted_market_value_eur ?? 0) -
            (a.predicted_market_value_eur ?? 0),
        )
        .slice(0, 10),
    [rows],
  );

  const sortedRisers = useMemo(
    () =>
      [...rows]
        .filter((r) => r.projected_change_pct != null)
        .sort(
          (a, b) =>
            (b.projected_change_pct ?? 0) - (a.projected_change_pct ?? 0),
        ),
    [rows],
  );

  const reset = () => {
    setLeagueId("");
    setTeam("");
    setPosition("");
  };

  const scope =
    team
      ? team
      : leagueId !== ""
        ? LEAGUE_NAMES[leagueId] ?? "Selected league"
        : "All Big-5 leagues";

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Club / League Overview
        </h1>
        <p className="mt-1 text-sm text-ink-400">
          Squad-level summary based on current 2025-26 league/club mapping.
        </p>
      </section>

      <FilterBar
        mapping={mapping}
        leagueId={leagueId}
        team={team}
        playerUid=""
        onLeagueChange={setLeagueId}
        onTeamChange={setTeam}
        onPlayerChange={() => {}}
        onReset={reset}
        showPosition
        position={position}
        onPositionChange={setPosition}
      />

      <section className="grid grid-cols-1 gap-3 md:grid-cols-5">
        <MetricCard
          label="Squad — Current Value"
          value={formatEuro(totals.current)}
          hint={scope}
        />
        <MetricCard
          label="Squad — Projected EOS Value"
          value={formatEuro(totals.projected)}
          tone="accent"
          hint={`${formatCount(rows.length)} players`}
        />
        <MetricCard
          label="Average Projected Change"
          value={
            totals.avgChange == null
              ? "—"
              : formatPercent(totals.avgChange, { signed: true })
          }
          tone={
            totals.avgChange == null
              ? "neutral"
              : totals.avgChange > 0
                ? "positive"
                : "negative"
          }
        />
        <MetricCard
          label="Biggest Riser"
          value={
            totals.topRiser
              ? formatPercent(totals.topRiser.projected_change_pct, {
                  signed: true,
                })
              : "—"
          }
          tone="positive"
          hint={totals.topRiser?.player_name ?? undefined}
        />
        <MetricCard
          label="Biggest Faller"
          value={
            totals.topFaller
              ? formatPercent(totals.topFaller.projected_change_pct, {
                  signed: true,
                })
              : "—"
          }
          tone="negative"
          hint={totals.topFaller?.player_name ?? undefined}
        />
      </section>

      {loading ? (
        <div className="rounded-lg border border-ink-800 bg-ink-900/30 px-4 py-6 text-sm text-ink-300">
          Loading squad…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-ink-700 bg-ink-900/20 p-8 text-center text-sm text-ink-400">
          No players match the current filters.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ChartCard
              title="Current vs Projected Squad Value by Position"
              description="Sum of current and projected end-of-season market value"
            >
              <div style={{ width: "100%", height: 240 }}>
                <ResponsiveContainer>
                  <BarChart data={byPosition}>
                    <CartesianGrid stroke="#1f2937" vertical={false} />
                    <XAxis
                      dataKey="position"
                      tick={{ fill: "#94a3b8", fontSize: 12 }}
                      stroke="#334155"
                    />
                    <YAxis
                      tick={{ fill: "#94a3b8", fontSize: 12 }}
                      stroke="#334155"
                      tickFormatter={(v) => formatEuro(Number(v))}
                      width={60}
                    />
                    <Tooltip
                      cursor={{ fill: "#1f293750" }}
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid #334155",
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                      formatter={(v) => formatEuro(typeof v === "number" ? v : Number(v))}
                    />
                    <Bar
                      dataKey="current"
                      name="Current"
                      fill="#10b981"
                      radius={[3, 3, 0, 0]}
                      isAnimationActive={false}
                    />
                    <Bar
                      dataKey="projected"
                      name="Projected"
                      fill="#6366f1"
                      radius={[3, 3, 0, 0]}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            <ChartCard
              title="Projected Change Distribution"
              description="Number of players in each projected change bucket"
            >
              <div style={{ width: "100%", height: 240 }}>
                <ResponsiveContainer>
                  <BarChart data={changeDistribution}>
                    <CartesianGrid stroke="#1f2937" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      stroke="#334155"
                    />
                    <YAxis
                      tick={{ fill: "#94a3b8", fontSize: 12 }}
                      stroke="#334155"
                      width={40}
                      allowDecimals={false}
                    />
                    <Tooltip
                      cursor={{ fill: "#1f293750" }}
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid #334155",
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                      {changeDistribution.map((b, i) => (
                        <Cell
                          key={i}
                          fill={b.min >= 0 ? "#10b981" : "#ef4444"}
                          fillOpacity={0.9}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          </div>

          <ChartCard
            title="Top 10 Projected Values"
            description={`Highest projected end-of-season values in ${scope}`}
          >
            <div style={{ width: "100%", height: Math.max(220, top10.length * 32) }}>
              <ResponsiveContainer>
                <BarChart data={top10} layout="vertical" margin={{ left: 90 }}>
                  <CartesianGrid stroke="#1f2937" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fill: "#94a3b8", fontSize: 12 }}
                    stroke="#334155"
                    tickFormatter={(v) => formatEuro(Number(v))}
                  />
                  <YAxis
                    dataKey="player_name"
                    type="category"
                    tick={{ fill: "#cbd5e1", fontSize: 12 }}
                    stroke="#334155"
                    width={130}
                  />
                  <Tooltip
                    cursor={{ fill: "#1f293750" }}
                    contentStyle={{
                      background: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                    formatter={(v) => formatEuro(typeof v === "number" ? v : Number(v))}
                  />
                  <Bar
                    dataKey="predicted_market_value_eur"
                    fill="#6366f1"
                    radius={[0, 3, 3, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RisersFallers
              title="Top Projected Risers"
              tone="positive"
              rows={sortedRisers.slice(0, 8)}
            />
            <RisersFallers
              title="Top Projected Fallers"
              tone="negative"
              rows={sortedRisers.slice(-8).reverse()}
            />
          </div>

          <SquadTable rows={rows} />
        </>
      )}
    </div>
  );
}

function ChartCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40 p-4">
      <div className="mb-3">
        <div className="text-sm font-medium text-white">{title}</div>
        {description ? (
          <div className="text-xs text-ink-400">{description}</div>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function RisersFallers({
  title,
  tone,
  rows,
}: {
  title: string;
  tone: "positive" | "negative";
  rows: SquadRow[];
}) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40">
      <div className="border-b border-ink-800 px-4 py-3 text-sm font-medium text-white">
        {title}
      </div>
      <ul>
        {rows.map((r) => (
          <li
            key={r.player_uid}
            className="flex items-center gap-3 border-b border-ink-900 px-4 py-2 last:border-b-0"
          >
            <PlayerPhoto src={r.player_photo_url} name={r.player_name} size={32} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm text-ink-100">{r.player_name}</div>
              <div className="truncate text-xs text-ink-400">
                {r.team_name ?? "—"} · {positionLabel(r.model_position)}
              </div>
            </div>
            <div className="text-right tabular-nums">
              <div
                className={
                  tone === "positive" ? "text-emerald-400" : "text-rose-400"
                }
              >
                {formatPercent(r.projected_change_pct, { signed: true })}
              </div>
              <div className="text-xs text-ink-400">
                {formatEuro(r.last_market_value_eur)} →{" "}
                {formatEuro(r.predicted_market_value_eur)}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SquadTable({ rows }: { rows: SquadRow[] }) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40">
      <div className="border-b border-ink-800 px-4 py-3 text-sm font-medium text-white">
        Squad table
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] text-sm">
          <thead className="bg-ink-900/70 text-xs uppercase tracking-wide text-ink-400">
            <tr>
              <Th>Player</Th>
              <Th>Position</Th>
              <Th right>Age</Th>
              <Th right>Current Value</Th>
              <Th right>Projected EOS</Th>
              <Th right>Change %</Th>
              <Th right>Minutes</Th>
              <Th right>G+A / 90</Th>
              <Th right>xG+xA / 90</Th>
              <Th right>Key Passes / 90</Th>
              <Th right>Tackles / 90</Th>
              <Th right>Duel Win %</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.player_uid}
                className="border-b border-ink-900 hover:bg-ink-800/30"
              >
                <td className="px-3 py-2">
                  <div className="flex items-center gap-3">
                    <PlayerPhoto
                      src={r.player_photo_url}
                      name={r.player_name}
                      size={32}
                    />
                    <div className="min-w-0">
                      <div className="truncate text-ink-100">{r.player_name}</div>
                      <div className="truncate text-xs text-ink-400">
                        {r.team_name ?? "—"}
                      </div>
                    </div>
                  </div>
                </td>
                <Td>{positionLabel(r.model_position)}</Td>
                <Td right>{formatCount(r.player_age)}</Td>
                <Td right>{formatEuro(r.last_market_value_eur)}</Td>
                <Td right>{formatEuro(r.predicted_market_value_eur)}</Td>
                <Td
                  right
                  className={
                    r.projected_change_pct == null
                      ? ""
                      : r.projected_change_pct > 0
                        ? "text-emerald-400"
                        : r.projected_change_pct < 0
                          ? "text-rose-400"
                          : ""
                  }
                >
                  {formatPercent(r.projected_change_pct, { signed: true })}
                </Td>
                <Td right>{formatCount(r.api_minutes)}</Td>
                <Td right>{formatRate(r.goals_assists_per90)}</Td>
                <Td right>{formatRate(r.xg_xa_per90)}</Td>
                <Td right>{formatRate(r.api_passes_key_per90)}</Td>
                <Td right>{formatRate(r.api_tackles_total_per90)}</Td>
                <Td right>{formatPercent(r.duel_win_rate)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({
  children,
  right,
}: {
  children: React.ReactNode;
  right?: boolean;
}) {
  return (
    <th
      className={`whitespace-nowrap border-b border-ink-800 px-3 py-2 font-medium ${
        right ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  right,
  className,
}: {
  children: React.ReactNode;
  right?: boolean;
  className?: string;
}) {
  return (
    <td
      className={`whitespace-nowrap px-3 py-2 text-ink-200 ${
        right ? "text-right tabular-nums" : ""
      } ${className ?? ""}`}
    >
      {children}
    </td>
  );
}

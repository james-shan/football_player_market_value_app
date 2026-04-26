"use client";

import { useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import Papa from "papaparse";
import clsx from "clsx";
import type { PlayerSeasonRow } from "@/lib/types";
import {
  formatCount,
  formatEuro,
  formatPercent,
  formatRate,
} from "@/lib/format";
import { leagueLabel, positionLabel } from "@/lib/labels";

type Row = PlayerSeasonRow;

const NUMERIC_RIGHT = "text-right tabular-nums";

const BASE_COLUMNS: ColumnDef<Row>[] = [
  {
    header: "Season",
    accessorKey: "season",
    cell: (info) => {
      const s = info.getValue<number>();
      return `${s}-${(s + 1) % 100}`;
    },
  },
  { header: "Team", accessorKey: "team_name", cell: (i) => i.getValue<string>() ?? "—" },
  {
    header: "League",
    accessorKey: "league_id",
    cell: (i) => leagueLabel(i.getValue<number>()),
  },
  {
    header: "Position",
    accessorKey: "model_position",
    cell: (i) => positionLabel(i.getValue<string | null>()),
  },
  {
    header: "Age",
    accessorKey: "player_age",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Market Value",
    accessorKey: "target_market_value_eur",
    cell: (i) => formatEuro(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Projected EOS Value",
    accessorKey: "predicted_market_value_eur",
    cell: (i) => formatEuro(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Minutes",
    accessorKey: "api_minutes",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Apps",
    accessorKey: "api_appearances",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Starts",
    accessorKey: "api_starts",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
];

const OUTFIELD_COLUMNS: ColumnDef<Row>[] = [
  {
    header: "Goals",
    accessorKey: "api_goals_total",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Assists",
    id: "assists",
    accessorFn: (row) =>
      row.api_goals_assists ?? row.understat_assists ?? null,
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Goals / 90",
    accessorKey: "understat_goals_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Assists / 90",
    accessorKey: "understat_assists_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "G+A / 90",
    accessorKey: "goals_assists_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "xG / 90",
    accessorKey: "xg_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "xA / 90",
    accessorKey: "xa_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "xG+xA / 90",
    accessorKey: "xg_xa_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Shots / 90",
    accessorKey: "api_shots_total_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Shots on Tgt / 90",
    accessorKey: "api_shots_on_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Key Passes / 90",
    accessorKey: "api_passes_key_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Tackles / 90",
    accessorKey: "api_tackles_total_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Duels Won / 90",
    accessorKey: "api_duels_won_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Duel Win %",
    accessorKey: "duel_win_rate",
    cell: (i) => formatPercent(i.getValue<number | null>(), { digits: 1 }),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Dribble Success %",
    accessorKey: "dribble_success_rate",
    cell: (i) => formatPercent(i.getValue<number | null>(), { digits: 1 }),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Cards / 90",
    accessorKey: "cards_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
];

const GK_COLUMNS: ColumnDef<Row>[] = [
  {
    header: "Saves",
    accessorKey: "saves",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Goals Conceded",
    accessorKey: "goals_conceded",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Saves / 90",
    accessorKey: "saves_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Goals Conceded / 90",
    accessorKey: "goals_conceded_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Save %",
    accessorKey: "save_rate",
    cell: (i) => formatPercent(i.getValue<number | null>(), { digits: 1 }),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Passes",
    accessorKey: "api_passes_total",
    cell: (i) => formatCount(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Passes / 90",
    accessorKey: "api_passes_total_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Duel Win %",
    accessorKey: "duel_win_rate",
    cell: (i) => formatPercent(i.getValue<number | null>(), { digits: 1 }),
    meta: { className: NUMERIC_RIGHT },
  },
  {
    header: "Cards / 90",
    accessorKey: "cards_per90",
    cell: (i) => formatRate(i.getValue<number | null>()),
    meta: { className: NUMERIC_RIGHT },
  },
];

function columnsFor(positionCode: string | null): ColumnDef<Row>[] {
  if (positionCode === "G") return [...BASE_COLUMNS, ...GK_COLUMNS];
  return [...BASE_COLUMNS, ...OUTFIELD_COLUMNS];
}

export default function PlayerStatsTable({
  rows,
  playerName,
  positionCode,
}: {
  rows: Row[];
  playerName: string;
  positionCode: string | null;
}) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "season", desc: true },
  ]);

  const data = useMemo(() => rows, [rows]);
  const columns = useMemo(() => columnsFor(positionCode), [positionCode]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  function exportCsv() {
    const isGK = positionCode === "G";
    const exportRows = rows.map((r) => {
      const assists = r.api_goals_assists ?? r.understat_assists ?? null;
      const base = {
        season: r.season,
        team: r.team_name,
        league: leagueLabel(r.league_id),
        position: positionLabel(r.model_position),
        age: r.player_age,
        market_value_eur: r.target_market_value_eur,
        projected_end_of_season_value_eur: r.predicted_market_value_eur,
        minutes: r.api_minutes,
        appearances: r.api_appearances,
        starts: r.api_starts,
        is_projection: r.is_projection,
      };
      if (isGK) {
        return {
          ...base,
          saves: r.saves,
          goals_conceded: r.goals_conceded,
          saves_per_90: r.saves_per90,
          goals_conceded_per_90: r.goals_conceded_per90,
          save_rate: r.save_rate,
          passes_total: r.api_passes_total,
          passes_total_per_90: r.api_passes_total_per90,
          duel_win_rate: r.duel_win_rate,
          cards_per_90: r.cards_per90,
        };
      }
      return {
        ...base,
        goals: r.api_goals_total,
        assists,
        goals_per_90: r.understat_goals_per90,
        assists_per_90: r.understat_assists_per90,
        goals_assists_per_90: r.goals_assists_per90,
        xg_per_90: r.xg_per90,
        xa_per_90: r.xa_per90,
        xg_xa_per_90: r.xg_xa_per90,
        shots_per_90: r.api_shots_total_per90,
        shots_on_target_per_90: r.api_shots_on_per90,
        key_passes_per_90: r.api_passes_key_per90,
        passes_total: r.api_passes_total,
        tackles_per_90: r.api_tackles_total_per90,
        duels_won_per_90: r.api_duels_won_per90,
        duel_win_rate: r.duel_win_rate,
        dribble_success_rate: r.dribble_success_rate,
        cards_per_90: r.cards_per90,
      };
    });
    const csv = Papa.unparse(exportRows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${playerName.replace(/[^a-z0-9]+/gi, "_")}_seasons.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40">
      <div className="flex items-center justify-between border-b border-ink-800 px-4 py-3">
        <div>
          <div className="text-sm font-medium text-white">Season-by-season stats</div>
          <div className="text-xs text-ink-400">
            Click any column to sort. Scroll horizontally to see all metrics.
          </div>
        </div>
        <button
          type="button"
          onClick={exportCsv}
          className="rounded-md border border-ink-700 bg-ink-800/40 px-3 py-1.5 text-xs text-ink-100 hover:bg-ink-800"
        >
          Export CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] text-sm">
          <thead className="bg-ink-900/70 text-xs uppercase tracking-wide text-ink-400">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const meta = header.column.columnDef.meta as
                    | { className?: string }
                    | undefined;
                  const sort = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className={clsx(
                        "whitespace-nowrap border-b border-ink-800 px-3 py-2 text-left font-medium",
                        meta?.className,
                      )}
                    >
                      <button
                        type="button"
                        className="flex items-center gap-1 hover:text-white"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {sort === "asc" ? "▲" : sort === "desc" ? "▼" : ""}
                      </button>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className={clsx(
                  "border-b border-ink-900 hover:bg-ink-800/30",
                  row.original.is_projection && "bg-indigo-500/5",
                )}
              >
                {row.getVisibleCells().map((cell) => {
                  const meta = cell.column.columnDef.meta as
                    | { className?: string }
                    | undefined;
                  return (
                    <td
                      key={cell.id}
                      className={clsx(
                        "whitespace-nowrap px-3 py-2 text-ink-200",
                        meta?.className,
                      )}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

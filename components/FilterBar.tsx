"use client";

import { useMemo } from "react";
import clsx from "clsx";
import type { CurrentMappingRow } from "@/lib/types";
import { LEAGUE_NAMES, POSITION_LABELS } from "@/lib/labels";

type Props = {
  mapping: CurrentMappingRow[];
  leagueId: number | "";
  team: string;
  playerUid: string;
  onLeagueChange: (v: number | "") => void;
  onTeamChange: (v: string) => void;
  onPlayerChange: (v: string) => void;
  onReset: () => void;
  showPosition?: boolean;
  position?: string;
  onPositionChange?: (v: string) => void;
};

export default function FilterBar({
  mapping,
  leagueId,
  team,
  playerUid,
  onLeagueChange,
  onTeamChange,
  onPlayerChange,
  onReset,
  showPosition = false,
  position = "",
  onPositionChange,
}: Props) {
  const leagueOptions = useMemo(() => {
    const ids = new Set<number>();
    for (const row of mapping) {
      if (row.league_id != null) ids.add(row.league_id);
    }
    return [...ids].sort();
  }, [mapping]);

  const teamOptions = useMemo(() => {
    const filtered = leagueId === "" ? mapping : mapping.filter((r) => r.league_id === leagueId);
    const teams = new Set<string>();
    for (const row of filtered) {
      if (row.team_name) teams.add(row.team_name);
    }
    return [...teams].sort();
  }, [mapping, leagueId]);

  const playerOptions = useMemo(() => {
    let filtered = mapping;
    if (leagueId !== "") filtered = filtered.filter((r) => r.league_id === leagueId);
    if (team) filtered = filtered.filter((r) => r.team_name === team);
    if (showPosition && position) filtered = filtered.filter((r) => r.model_position === position);
    return filtered
      .slice()
      .sort((a, b) => a.player_name.localeCompare(b.player_name));
  }, [mapping, leagueId, team, position, showPosition]);

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40 p-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <FilterSelect
          label="League"
          value={leagueId === "" ? "" : String(leagueId)}
          onChange={(v) => {
            const next = v === "" ? "" : Number(v);
            onLeagueChange(next as number | "");
            onTeamChange("");
            onPlayerChange("");
          }}
        >
          <option value="">All leagues</option>
          {leagueOptions.map((id) => (
            <option key={id} value={id}>
              {LEAGUE_NAMES[id] ?? `League ${id}`}
            </option>
          ))}
        </FilterSelect>

        <FilterSelect
          label="Club"
          value={team}
          onChange={(v) => {
            onTeamChange(v);
            onPlayerChange("");
          }}
          disabled={teamOptions.length === 0}
        >
          <option value="">All clubs</option>
          {teamOptions.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </FilterSelect>

        {showPosition ? (
          <FilterSelect
            label="Position"
            value={position}
            onChange={(v) => onPositionChange?.(v)}
          >
            <option value="">All positions</option>
            {Object.entries(POSITION_LABELS).map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </FilterSelect>
        ) : (
          <FilterSelect
            label="Player"
            value={playerUid}
            onChange={(v) => onPlayerChange(v)}
          >
            <option value="">Select a player…</option>
            {playerOptions.map((p) => (
              <option key={p.player_uid} value={p.player_uid}>
                {p.player_name}
                {p.team_name ? ` · ${p.team_name}` : ""}
              </option>
            ))}
          </FilterSelect>
        )}

        <div className="flex items-end">
          <button
            type="button"
            onClick={onReset}
            className="w-full rounded-md border border-ink-700 bg-ink-800/40 px-3 py-2 text-sm text-ink-200 hover:bg-ink-800"
          >
            Reset filters
          </button>
        </div>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  disabled,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs uppercase tracking-wide text-ink-400">{label}</span>
      <select
        className={clsx(
          "rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100",
          "focus:outline-none focus:ring-2 focus:ring-brand-500/40",
          disabled && "opacity-60",
        )}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {children}
      </select>
    </label>
  );
}

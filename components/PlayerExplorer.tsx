"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  CohortRow,
  CurrentMappingRow,
  PlayerProfile,
  PlayerSeasonRow,
} from "@/lib/types";
import FilterBar from "./FilterBar";
import PlayerSearch from "./PlayerSearch";
import PlayerHeader from "./PlayerHeader";
import MarketValueChart from "./MarketValueChart";
import PositionStats from "./PositionStats";
import PercentileChart from "./PercentileChart";
import PlayerStatsTable from "./PlayerStatsTable";
import { getPositionConfig } from "@/lib/positionConfig";

type PlayerData = {
  profile: PlayerProfile;
  seasons: PlayerSeasonRow[];
};

type CohortData = {
  player: CohortRow | null;
  cohort: CohortRow[];
};

export default function PlayerExplorer({
  mapping,
}: {
  mapping: CurrentMappingRow[];
}) {
  const [leagueId, setLeagueId] = useState<number | "">("");
  const [team, setTeam] = useState("");
  const [playerUid, setPlayerUid] = useState("");
  const [data, setData] = useState<PlayerData | null>(null);
  const [cohort, setCohort] = useState<CohortData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerUid) {
      setData(null);
      setCohort(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(`/api/player/${encodeURIComponent(playerUid)}`).then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body?.error || `Failed to load player (${res.status})`);
        }
        return (await res.json()) as PlayerData;
      }),
      fetch(`/api/cohort/${encodeURIComponent(playerUid)}`).then(async (res) => {
        if (!res.ok) return { player: null, cohort: [] } as CohortData;
        return (await res.json()) as CohortData;
      }),
    ])
      .then(([playerData, cohortData]) => {
        if (cancelled) return;
        setData(playerData);
        setCohort(cohortData);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [playerUid]);

  function reset() {
    setLeagueId("");
    setTeam("");
    setPlayerUid("");
  }

  function selectFromSearch(row: CurrentMappingRow) {
    setLeagueId(row.league_id ?? "");
    setTeam(row.team_name ?? "");
    setPlayerUid(row.player_uid);
  }

  const seasons = data?.seasons ?? [];

  const latestActual = useMemo(() => {
    const histories = seasons.filter((s) => !s.is_projection);
    for (let i = histories.length - 1; i >= 0; i -= 1) {
      const v = histories[i].target_market_value_eur;
      if (v != null) return v;
    }
    return null;
  }, [seasons]);

  const positionCode = data?.profile.model_position ?? null;
  const percentileMetrics = useMemo(
    () => getPositionConfig(positionCode).percentiles,
    [positionCode],
  );

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Player Explorer
        </h1>
        <p className="mt-1 text-sm text-ink-400">
          Pick a league, club, and player — or search any current Big-5 player
          directly. Historical seasons reflect actual market values; the 2025-26
          row is a projected end-of-season value.
        </p>
      </section>

      <PlayerSearch mapping={mapping} onSelect={selectFromSearch} />

      <FilterBar
        mapping={mapping}
        leagueId={leagueId}
        team={team}
        playerUid={playerUid}
        onLeagueChange={setLeagueId}
        onTeamChange={setTeam}
        onPlayerChange={setPlayerUid}
        onReset={reset}
      />

      {loading ? <LoadingState /> : null}
      {error ? <ErrorState message={error} /> : null}

      {!playerUid && !loading ? (
        <EmptyExplorer mappingCount={mapping.length} />
      ) : null}

      {data ? (
        <div className="space-y-6">
          <PlayerHeader
            profile={data.profile}
            latestActualValue={latestActual}
          />

          <MarketValueChart seasons={seasons} />

          <PercentileChart
            player={cohort?.player ?? null}
            cohort={cohort?.cohort ?? []}
            metrics={percentileMetrics}
            positionCode={positionCode}
            leagueId={data.profile.league_id}
          />

          <PositionStats positionCode={positionCode} seasons={seasons} />

          <PlayerStatsTable
            rows={seasons}
            playerName={data.profile.player_name}
            positionCode={positionCode}
          />
        </div>
      ) : null}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/30 px-4 py-6 text-sm text-ink-300">
      Loading player history…
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">
      {message}
    </div>
  );
}

function EmptyExplorer({ mappingCount }: { mappingCount: number }) {
  return (
    <div className="rounded-lg border border-dashed border-ink-700 bg-ink-900/20 p-8 text-center">
      <div className="text-base font-medium text-white">
        Pick a player to begin
      </div>
      <p className="mt-1 text-sm text-ink-400">
        Use the search box or the league → club → player filters.{" "}
        {mappingCount.toLocaleString()} current Big-5 players are available.
      </p>
    </div>
  );
}

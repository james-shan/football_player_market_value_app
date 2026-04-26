import type { PlayerProfile } from "@/lib/types";
import { formatAge, formatEuro, formatPercent } from "@/lib/format";
import { leagueLabel, positionLabel } from "@/lib/labels";
import PlayerPhoto from "./PlayerPhoto";
import MetricCard from "./MetricCard";

type Props = {
  profile: PlayerProfile;
  latestActualValue: number | null;
};

export default function PlayerHeader({ profile, latestActualValue }: Props) {
  const last = profile.last_market_value_eur;
  const projected = profile.predicted_market_value_eur;
  const changePct =
    last && last > 0 && projected != null ? (projected - last) / last : null;
  const tone =
    changePct == null
      ? "neutral"
      : changePct > 0.0001
        ? "positive"
        : changePct < -0.0001
          ? "negative"
          : "neutral";

  return (
    <section className="rounded-lg border border-ink-800 bg-ink-900/40 p-6">
      <div className="flex flex-col gap-6 md:flex-row md:items-center">
        <PlayerPhoto
          src={profile.player_photo_url}
          name={profile.player_name}
          size={96}
          className="ring-2 ring-ink-700"
        />
        <div className="min-w-0 flex-1">
          <div className="text-2xl font-semibold tracking-tight text-white">
            {profile.player_name}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-300">
            <span>{profile.team_name ?? "—"}</span>
            <Sep />
            <span>{leagueLabel(profile.league_id)}</span>
            <Sep />
            <span>{positionLabel(profile.model_position)}</span>
            <Sep />
            <span>Age {formatAge(profile.player_age)}</span>
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Latest Actual Market Value"
          value={formatEuro(latestActualValue ?? last)}
          hint={last != null ? "Most recent Transfermarkt value" : undefined}
        />
        <MetricCard
          label="Projected End-of-Season Value"
          value={formatEuro(projected)}
          tone="accent"
          hint="2025-26 projection"
        />
        <MetricCard
          label="Projected Change"
          value={
            changePct == null
              ? "—"
              : formatPercent(changePct, { signed: true, digits: 1 })
          }
          tone={tone}
          hint="vs last market value"
        />
      </div>
    </section>
  );
}

function Sep() {
  return <span className="text-ink-600">·</span>;
}

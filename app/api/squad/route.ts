import { NextRequest, NextResponse } from "next/server";
import { getSquad } from "@/lib/queries";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const url = req.nextUrl;
  const leagueIdRaw = url.searchParams.get("leagueId");
  const team = url.searchParams.get("team") ?? undefined;
  const position = url.searchParams.get("position") ?? undefined;
  const leagueId = leagueIdRaw ? Number(leagueIdRaw) : undefined;
  try {
    const rows = await getSquad({
      leagueId: Number.isFinite(leagueId) ? leagueId : undefined,
      team: team && team !== "" ? team : undefined,
      position: position && position !== "" ? position : undefined,
    });
    return NextResponse.json({ rows });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Unknown error" },
      { status: 500 },
    );
  }
}

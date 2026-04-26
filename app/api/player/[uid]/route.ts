import { NextRequest, NextResponse } from "next/server";
import { getPlayerProfile, getPlayerSeasons } from "@/lib/queries";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ uid: string }> },
) {
  const { uid } = await ctx.params;
  if (!uid) {
    return NextResponse.json({ error: "missing uid" }, { status: 400 });
  }
  try {
    const [profile, seasons] = await Promise.all([
      getPlayerProfile(uid),
      getPlayerSeasons(uid),
    ]);
    if (!profile && seasons.length === 0) {
      return NextResponse.json({ error: "Player not found" }, { status: 404 });
    }
    return NextResponse.json({ profile, seasons });
  } catch (err) {
    console.error("[/api/player] error", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Unknown error" },
      { status: 500 },
    );
  }
}

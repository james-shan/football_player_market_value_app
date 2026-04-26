import { NextRequest, NextResponse } from "next/server";
import { getPlayerCohort } from "@/lib/queries";

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
    const data = await getPlayerCohort(uid);
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Unknown error" },
      { status: 500 },
    );
  }
}

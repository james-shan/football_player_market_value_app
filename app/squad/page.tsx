import { getCurrentMapping } from "@/lib/queries";
import SquadOverview from "@/components/SquadOverview";

export const dynamic = "force-dynamic";

export default async function SquadPage() {
  const mapping = await getCurrentMapping();
  return <SquadOverview mapping={mapping} />;
}

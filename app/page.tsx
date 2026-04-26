import { getCurrentMapping } from "@/lib/queries";
import PlayerExplorer from "@/components/PlayerExplorer";

export const dynamic = "force-dynamic";

export default async function Home() {
  const mapping = await getCurrentMapping();
  return <PlayerExplorer mapping={mapping} />;
}

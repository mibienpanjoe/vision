import { LiveConversation } from "@/features/conversation/live-workspace";

export default async function NewConversation({ searchParams }: { searchParams: Promise<{ work?: string }> }) {
  const { work } = await searchParams;
  const valid = work && /^[0-9a-f-]{36}$/.test(work) ? work : null;
  return <LiveConversation key={valid ?? "new"} initialId={null} initialWork={valid} />;
}

import { LiveConversation } from "@/features/conversation/live-workspace";

export default async function ConversationPage({ params }: { params: Promise<{ conversationId: string }> }) {
  const { conversationId } = await params;
  return <LiveConversation key={conversationId} initialId={conversationId} />;
}

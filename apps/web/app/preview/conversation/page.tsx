import { notFound } from "next/navigation";
import { connection } from "next/server";
import { ConversationPreview } from "@/features/conversation/workspace";
import "@/features/conversation/workspace.css";

export default async function ConversationPreviewPage() {
  await connection();
  if (process.env.VISION_CONVERSATION_PREVIEW !== "1") notFound();
  return <ConversationPreview />;
}

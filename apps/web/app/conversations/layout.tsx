import { SessionProvider } from "@/components/session-provider";
import "@/features/conversation/workspace.css";

export default function ConversationLayout({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}

import { SessionProvider } from "@/components/session-provider";
import { OpenWorkspace } from "@/features/conversation/open-workspace";

export default function Home() {
  return <SessionProvider><OpenWorkspace /></SessionProvider>;
}

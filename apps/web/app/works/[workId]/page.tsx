import { WorkspaceFrame } from "@/components/workspace-frame";
import { BookWorkspace } from "@/features/world-explorer/book-workspace";

export default async function BookPage({ params }: { params: Promise<{ workId: string }> }) {
  const { workId } = await params;
  return <WorkspaceFrame section="book"><BookWorkspace key={workId} workId={workId} /></WorkspaceFrame>;
}

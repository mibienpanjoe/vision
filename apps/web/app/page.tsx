import { WorkspaceFrame } from "@/components/workspace-frame";
import { Library } from "@/features/library/library";

export default function LibraryPage() {
  return (
    <WorkspaceFrame>
        <div className="library-heading library-hero">
          <div>
            <h1>Your library</h1>
          </div>
        </div>
        <Library />
    </WorkspaceFrame>
  );
}

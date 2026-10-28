import { Illustration } from "@/components/illustration";
import { WorkspaceFrame } from "@/components/workspace-frame";
import { Library } from "@/features/library/library";

export default function LibraryPage() {
  return (
    <WorkspaceFrame>
        <div className="library-heading library-hero">
          <div>
            <h1>Your library</h1>
          </div>
          <Illustration name="library" className="library-art" />
        </div>
        <Library />
    </WorkspaceFrame>
  );
}

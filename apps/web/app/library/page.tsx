import { Illustration } from "@/components/illustration";
import { WorkspaceFrame } from "@/components/workspace-frame";
import { Library } from "@/features/library/library";

export default function LibraryPage() {
  return (
    <WorkspaceFrame>
        <div className="library-heading library-hero">
          <div>
            <p className="eyebrow">A private reading workspace</p>
            <h1>Your library</h1>
            <p className="intro">Keep your books close. Bring their worlds into focus.</p>
          </div>
          <Illustration name="library" className="library-art" />
        </div>
        <Library />
        <p className="library-note">Every detail begins with a passage.</p>
    </WorkspaceFrame>
  );
}

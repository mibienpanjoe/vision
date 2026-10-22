import Image from "next/image";
import emptyDark from "../../../assets/illustrations/empty-dark.webp";
import emptyLight from "../../../assets/illustrations/empty-light.webp";
import libraryDark from "../../../assets/illustrations/library-dark.webp";
import libraryLight from "../../../assets/illustrations/library-light.webp";
import signInDark from "../../../assets/illustrations/sign-in-dark.webp";
import signInLight from "../../../assets/illustrations/sign-in-light.webp";
import workspaceDark from "../../../assets/illustrations/workspace-dark.webp";
import workspaceLight from "../../../assets/illustrations/workspace-light.webp";

const art = {
  "sign-in": [signInLight, signInDark], library: [libraryLight, libraryDark],
  workspace: [workspaceLight, workspaceDark], empty: [emptyLight, emptyDark],
};

// Decorative only: each variant blends into its theme's surface (see the illustration manifest).
export function Illustration({ name, className = "" }: { name: keyof typeof art; className?: string }) {
  const [light, dark] = art[name];
  return <div className={`illustration ${className}`} aria-hidden="true">
    <Image className="illustration-light" src={light} alt="" unoptimized />
    <Image className="illustration-dark" src={dark} alt="" unoptimized />
  </div>;
}

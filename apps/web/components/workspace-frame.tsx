import Image from "next/image";
import type { ReactNode } from "react";
import lightMark from "../../../assets/brand/vision-mark.png";
import darkMark from "../../../assets/brand/vision-mark-dark-tile.png";
import { ThemeControl } from "./theme-provider";

export function WorkspaceFrame({ children, section = "library" }: { children: ReactNode; section?: "library" | "book" }) {
  return <div className="workspace">
    <a className="skip-link" href={`#${section}`}>Skip to {section}</a>
    <header className="site-header">
      <a className="brand" href="/" aria-label="Vision home">
        <Image className="mark-light" src={lightMark} alt="" width={48} height={48} unoptimized />
        <Image className="mark-dark" src={darkMark} alt="" width={48} height={48} unoptimized /><span>Vision</span>
      </a><ThemeControl />
    </header>
    <main id={section} tabIndex={-1}>{children}</main>
    <footer><span>Vision</span><span>Read the words. See the world.</span></footer>
  </div>;
}

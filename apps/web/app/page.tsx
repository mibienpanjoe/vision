import Image from "next/image";
import lightMark from "../../../assets/brand/vision-mark.png";
import darkMark from "../../../assets/brand/vision-mark-dark-tile.png";
import { ThemeControl } from "@/components/theme-provider";
import { Library } from "@/features/library/library";

export default function LibraryPage() {
  return (
    <div className="workspace">
      <a className="skip-link" href="#library">Skip to library</a>
      <header className="site-header">
        <a className="brand" href="/" aria-label="Vision home"><Image className="mark-light" src={lightMark} alt="" width={48} height={48} unoptimized />
          <Image className="mark-dark" src={darkMark} alt="" width={48} height={48} unoptimized />
          <span>Vision</span></a>
        <ThemeControl />
      </header>
      <main id="library" tabIndex={-1}>
        <div className="library-heading">
          <p className="eyebrow">A private reading workspace</p>
          <h1>Your library</h1>
          <p className="intro">Keep your books close. Bring their worlds into focus.</p>
        </div>
        <Library />
        <p className="library-note">Every detail begins with a passage.</p>
      </main>
      <footer><span>Vision</span><span>Read the words. See the world.</span></footer>
    </div>
  );
}

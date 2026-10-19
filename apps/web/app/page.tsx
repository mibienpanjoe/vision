import { ThemeControl } from "@/components/theme-provider";

export default function LibraryPage() {
  return (
    <div className="workspace">
      <a className="skip-link" href="#library">Skip to library</a>
      <header className="site-header">
        <a className="brand" href="/" aria-label="Vision home"><span>Vision</span></a>
        <ThemeControl />
      </header>
      <main id="library" tabIndex={-1}>
        <div className="library-heading">
          <p className="eyebrow">A private reading workspace</p>
          <h1>Your library</h1>
          <p className="intro">Keep your books close. Bring their worlds into focus.</p>
        </div>
        <section className="empty-library" aria-labelledby="empty-title">
          <div className="book-spine" aria-hidden="true">V</div>
          <div>
            <p className="eyebrow">The first page</p>
            <h2 id="empty-title">A place for your next world.</h2>
            <p>Book uploads are not available yet.</p>
            <p className="muted-copy">This is where your books and their source-linked discoveries will live.</p>
          </div>
        </section>
        <p className="library-note">Every detail begins with a passage.</p>
      </main>
      <footer><span>Vision</span><span>Read the words. See the world.</span></footer>
    </div>
  );
}

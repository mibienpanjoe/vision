import type { Moment, Revision, SampleImage } from "./scenario-fixtures";
import { moments, sampleImage } from "./scenario-fixtures";

export function PromptCard({ current, image, busy, onMoment, onCopy, onImage, onDetails }: {
  current: Revision; image: SampleImage | null; busy: boolean;
  onMoment: (moment: Moment) => void; onCopy: () => void; onImage: () => void;
  onDetails: (kind: "sources" | "versions") => void;
}) {
  return <section className="conversation-card" aria-labelledby="prompt-heading" aria-busy={busy}>
    <div className="conversation-card-heading"><h2 id="prompt-heading">Your image prompt</h2><span className="muted-copy">Version {current.version}</span></div>
    <p className="conversation-prompt" data-testid="active-prompt">{current.prompt}</p>
    <div className="conversation-actions">
      <button type="button" onClick={onCopy}>Copy prompt</button>
      <button type="button" className="secondary" onClick={onImage} disabled={busy || image?.status === "pending" || image?.status === "unknown"}>Generate image</button>
      <button type="button" className="conversation-link" onClick={() => onDetails("sources")}>Sources</button>
      <button type="button" className="conversation-link" onClick={() => onDetails("versions")}>Versions & export</button>
    </div>
    {["childhood", "home"].includes(current.moment) && <div className="conversation-moments" role="group" aria-label="Other appearances">
      {moments.map(moment => <button type="button" className="secondary" key={moment.id} disabled={busy}
        aria-pressed={current.moment === moment.id} onClick={() => onMoment(moment.id)}>
        <strong>{moment.title}</strong><span>{moment.difference}</span>
      </button>)}
    </div>}
    {image?.status === "ready" && <figure className="conversation-image">
      {/* A static sample SVG exercises image association without a paid call. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={sampleImage(image.version)} alt="Sample placeholder: an open doorway, not a generated character image" width="640" height="360" />
      <figcaption>Sample image · prompt version {image.version}</figcaption>
      {image.version !== current.version && <p className="muted-copy">From an earlier prompt version</p>}
      <a download={`sample-prompt-${image.version}.svg`} href={sampleImage(image.version)}>Download sample image</a>
    </figure>}
  </section>;
}

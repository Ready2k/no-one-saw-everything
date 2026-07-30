import { useState } from "react";
import { useEscapeToClose } from "../useEscapeToClose";

interface Detective101ModalProps {
  onClose: () => void;
}

interface Section {
  id: string;
  icon: string;
  label: string;
  body: JSX.Element;
}

function Opt({ name, children }: { name: string; children: React.ReactNode }) {
  return <div className="manual-opt"><strong>{name}</strong><span>{children}</span></div>;
}

function Aside({ children }: { children: React.ReactNode }) {
  return <p className="manual-aside">🕵️ {children}</p>;
}

function Exhibit({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="manual-opt manual-exhibit"><strong>🔎 {title}</strong><span>{children}</span></div>;
}

function Shot({ file, alt, caption }: { file: string; alt: string; caption: string }) {
  return (
    <figure className="manual-shot full">
      <img src={`/manual/current/${file}`} alt={alt} loading="lazy" />
      <figcaption>🔎 {caption}</figcaption>
    </figure>
  );
}

const SECTIONS: Section[] = [
  {
    id: "start",
    icon: "🎩",
    label: "Start here",
    body: <>
      <h3>Welcome to the Bureau</h3>
      <p>Every rookie detective thinks they will crack the case by glaring at a suspect hard enough. They will not. <strong>No One Saw Everything</strong> is a fair-play mystery: the answer is in the case, but it is usually hiding behind somebody else's version of the morning.</p>
      <Shot file="01-case-hub.png" alt="The current Case Hub showing the active case folder, Bureau rail, and case inbox" caption="The Case Hub — your desk, your current file, and several opportunities to make an excellent decision." />
      <Exhibit title="The Case Hub">Your desk: a case file in the middle, the Bureau rail to the left, and the recent-case inbox to the right. It is less an interface than a very organised accusation waiting to happen.</Exhibit>
      <Opt name="The left rail">Open a new or generated case, the case library, settings, and—when developer access is enabled—Map Studio. The folder in the centre opens the active case; the inbox at right reopens a recent file without making you rummage through a filing cabinet.</Opt>
      <Opt name="Case File">Read the victim, reporting witness, discovery location, murder window, and replay range before pressing <strong>Begin investigation</strong>. A detective who skips the briefing is just a person in a coat with a theory.</Opt>
      <Aside>Progress lives with each case. Switching files is safe; Restart is the button with consequences.</Aside>
    </>,
  },
  {
    id: "timeline",
    icon: "⏪",
    label: "Reconstruct time",
    body: <>
      <h3>Rewind and Map Replay</h3>
      <p>These are the same morning in two disguises: Rewind is the statement on paper; Map Replay is the moment you realise the statement involves an impossible amount of walking.</p>
      <Shot file="03-rewind.png" alt="The current Rewind timeline and event list" caption="Rewind — a complete public record of a morning that would prefer not to be complete." />
      <Exhibit title="Rewind">The event ledger. The murder window is the shaded strip, while the filters let you reduce a busy village to one person, one location, and one increasingly suspicious ten minutes.</Exhibit>
      <Opt name="Rewind">Set the time range, use the murder-window shortcut, and filter by location or person. Event entries distinguish public sightings from unclear ones. Pin an event to add it to your notes and, where applicable, surface its lead.</Opt>
      <Opt name="Map Replay">Filter the animated map by place or person, then scrub, play, or change playback speed. Selecting one person can reveal their movement trace; gaps mean there was no publicly identifiable sighting—not necessarily that they teleported.</Opt>
      <Shot file="04-map-replay.png" alt="The current Map Replay screen with the village map, timeline, and observed events" caption="Map Replay — because seeing two routes miss each other by a minute is better than reading it twice." />
      <Opt name="Map details">Click an event marker to read and pin it. Click a location to inspect it directly from the side panel. After an accusation, Truth replay becomes available and reveals the whole morning, including the bits everyone would rather you had missed.</Opt>
      <Aside>A timeline proves opportunity, not guilt. Make it collide with a search scene and an interview before you marry the theory.</Aside>
    </>,
  },
  {
    id: "search",
    icon: "🔍",
    label: "Search scenes",
    body: <>
      <h3>Places and the post-mortem</h3>
      <p>People leave evidence behind in rooms because rooms are terrible at keeping secrets.</p>
      <Shot file="05-places.png" alt="The current Places screen with location list, search scene, and evidence panel" caption="Places — sweep carefully, click deliberately, and try not to look too pleased when the magnifier finds something." />
      <Exhibit title="Search scene">The location list stays on the left; the scene itself is in the centre; your finds and notes sit at the right. The magnifier is not decorative. It is your quiet, nosy friend.</Exhibit>
      <Opt name="Places">Choose a searchable location from the left list. The scene is the playable search surface: move the magnifier over the art and investigate when it reacts. The right panel records found evidence and location notes.</Opt>
      <Opt name="Private locations">Private badges identify back rooms and personal spaces. They remain searchable, but entering one in the wrong moment may be remembered. Even a perfect detective should knock occasionally.</Opt>
      <Opt name="Victim">On the Suspects screen, select the victim for the morgue view. Fold back the sheet with the gloves, then use the magnifier to examine the body. The other tray instruments are not interactive.</Opt>
      <Aside>Search before confronting a suspect whenever you can. A clue is much more fun when they do not know you have it.</Aside>
    </>,
  },
  {
    id: "interview",
    icon: "🎭",
    label: "Interview people",
    body: <>
      <h3>Suspects</h3>
      <p>The interview room is where perfectly normal villagers discover they have opinions about being asked where they were at 07:52.</p>
      <Shot file="06-suspects.png" alt="The current Suspects screen with roster, interview dossier, and quick tools" caption="Suspects — a dossier, a transcript, and a perfectly respectable amount of pressure." />
      <Exhibit title="Interview dossier">The roster selects a resident; the central dossier keeps their answers and statement replay together; the side panel holds your judgement and the quick tools.</Exhibit>
      <Opt name="Dossier and transcript">Choose a living resident from the roster to see their dossier, your conversation, and their current demeanour. Use the replay control on an observed statement when it is available to return to the relevant moment.</Opt>
      <Opt name="Quick tools">Ask a free-text question or use the quick prompts for alibi, relationship, last seen, whereabouts, a location, or a discovered clue. Only discovered evidence can be used in a confrontation.</Opt>
      <Opt name="Challenges">When a statement conflicts with evidence, a challenge can appear. A successful challenge adds pressure and may change how the resident responds; it does not turn a weak clue into a magic confession.</Opt>
      <Opt name="Judgement">Set a private suspicion level and add notes from answers. These labels organise your case; they do not affect the accusation result.</Opt>
    </>,
  },
  {
    id: "board",
    icon: "📌",
    label: "Build the case",
    body: <>
      <h3>Case Board and accusation</h3>
      <p>This is the satisfying bit: the evidence stops being a pile and starts becoming a case. String is optional. Dramatic pauses are not.</p>
      <Shot file="07-case-board.png" alt="The current Case Board with suspect cards, evidence catalogue, and notebook" caption="The Case Board — where hunches earn their keep, or get quietly crossed out." />
      <Opt name="Investigation Board">The board brings together suspect cards, guidance, the evidence catalogue, and notebook entries. Markers and pinned notes help you organise a theory; use them as working notes rather than proof.</Opt>
      <Opt name="Notebook">Create a note, set its kind, and optionally link it to a suspect. Event pins and interview answers can also become notes, so keep the board concise enough to revisit.</Opt>
      <Opt name="Accuse">Choose the killer and explain motive, method, and opportunity in your own words. Cite the evidence and notes that support the argument. Submitting locks the case and opens the reveal and grading breakdown.</Opt>
      <Aside>There is no routine undo after an accusation. Take the extra five minutes; your future self is a very harsh superior officer.</Aside>
    </>,
  },
  {
    id: "studio",
    icon: "🗺️",
    label: "Map Studio",
    body: <>
      <h3>Developer tools and scene manipulation</h3>
      <p>Map Studio is the Bureau's behind-the-scenes workshop, available from the hub when developer access is enabled. It changes the layout and scene data used by the game, so this is where a little curiosity can become a very real saved change.</p>
      <Shot file="08-map-studio.png" alt="The current Map Studio with tool palette, canvas, and property controls" caption="Map Studio — the town's workshop, where every lamp, mist plume, clue hotspot, and roofline answers to you." />
      <Exhibit title="The Studio">Tools and scene sources live at left, the working canvas occupies the centre, and the exact properties of your selected thing appear at right. Like a crime board, but the strings actually move buildings.</Exhibit>
      <Opt name="Choose scope and view">Select the canonical town template or a case override, then switch between <strong>External</strong> (roofed overview) and <strong>Internal</strong> (roofless close-up) views. Internal bounds can inherit the external bounds or be edited independently.</Opt>
      <Opt name="Place and shape">The tool palette supports selection, pan, tile paint, erase, rectangle, fill, picker, props, lights, ambient effects, and building placement. Drag objects on the canvas; use the properties panel for exact position, size, rotation, layer, opacity, timing, and render policy.</Opt>
      <Opt name="Manipulate scenes">Select a location to resize or rotate its bounds, snap it to the painted structure, and set exterior or interior mode. Select a clue from the case list to open its HD search art and position its hotspot and search radius as percentages of that scene.</Opt>
      <Opt name="Dress the town">Props can link to clue objects. Lights have independent external/internal placement and active times. Ambient sprites add water shimmer, smoke, mist, birds, or motes with timing and opacity. Building bundles carry their art, entrance, dressing, and rotation; <strong>Connect paths</strong> routes entrances to the path network.</Opt>
      <Opt name="Preview and save">Use the underlay chooser and opacity control to align work to town or location art. Undo/redo, import/export, validations, minimap, and keyboard shortcuts are in the header and workspace. <strong>Save Layout</strong> is the only action that writes the reviewed layout; resolve validation warnings first. The town has survived this long without a smoke plume hovering over the pub's roof—do not be the reason it changes.</Opt>
      <Aside>The separate <strong>/dev/ambient-town</strong> route is a visual preview for testing map art, mood, labels, and ambient playback. It does not replace Map Studio’s saved scene editing.</Aside>
    </>,
  },
  {
    id: "tips",
    icon: "🥃",
    label: "Field notes",
    body: <>
      <h3>Notes from the Chief</h3>
      <p>Off the record, from someone who has closed a few of these:</p>
      <section className="chief-field-card" aria-label="Chief's field card">
        <div className="chief-card-topline"><span>PERSONAL MEMO · EYES ONLY</span><b>CHIEF'S RULE #7</b></div>
        <blockquote>“The first story is rarely the lie. It is the part of the lie they rehearsed.”</blockquote>
        <div className="chief-case-rhythm" aria-label="Investigation rhythm">
          <span><b>01</b> Watch</span>
          <span><b>02</b> Search</span>
          <span><b>03</b> Test</span>
          <span><b>04</b> Prove</span>
        </div>
        <p>Watch the morning. Search the scene. Test the story. Prove the case. In that order, if you enjoy being right.</p>
      </section>
      <ul className="manual-list">
        <li>Rewind first, then use Map Replay to test whether a route is actually plausible.</li>
        <li>Search the scene before asking its owner about it.</li>
        <li>Unclear sightings are leads to corroborate, not mistakes to ignore.</li>
        <li>Use the Board to separate facts, statements, and your theories.</li>
        <li>Do not confuse pressure, suspicion labels, or red strings with evidence. They are props, not proof.</li>
      </ul>
    </>,
  },
];

export default function Detective101Modal({ onClose }: Detective101ModalProps) {
  useEscapeToClose(onClose);
  const [sectionId, setSectionId] = useState(SECTIONS[0].id);
  const active = SECTIONS.find((section) => section.id === sectionId) ?? SECTIONS[0];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal detective-manual" onClick={(event) => event.stopPropagation()} style={{ maxWidth: "980px", width: "95%", maxHeight: "88vh", padding: 0, display: "flex", flexDirection: "column", gap: 0, overflow: "hidden" }}>
        <div className="manual-header">
          <div><span className="brand-eyebrow">Bureau Training Manual</span><h2 style={{ margin: "0.2rem 0 0" }}>🕵️ Detective 101</h2></div>
          <button type="button" className="btn-secondary" onClick={onClose}>Close</button>
        </div>
        <div className="manual-body">
          <nav className="manual-toc">
            {SECTIONS.map((section) => <button key={section.id} className={section.id === sectionId ? "manual-toc-item active" : "manual-toc-item"} aria-current={section.id === sectionId ? "page" : undefined} onClick={() => setSectionId(section.id)}><span className="manual-toc-icon">{section.icon}</span><span>{section.label}</span></button>)}
          </nav>
          <div className="manual-content">{active.body}</div>
        </div>
      </div>
    </div>
  );
}

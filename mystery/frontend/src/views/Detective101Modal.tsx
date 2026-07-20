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
  return (
    <div className="manual-opt">
      <strong>{name}</strong>
      <span>{children}</span>
    </div>
  );
}

function Aside({ children }: { children: React.ReactNode }) {
  return <p className="manual-aside">🕵️ {children}</p>;
}

/** A screenshot exhibit. `full` renders wide; omit it for a tight zoomed-in crop. */
function Shot({
  file,
  alt,
  caption,
  full,
}: {
  file: string;
  alt: string;
  caption?: string;
  full?: boolean;
}) {
  return (
    <figure className={full ? "manual-shot full" : "manual-shot zoom"}>
      <img src={`/manual/${file}`} alt={alt} loading="lazy" />
      {caption && <figcaption>🔎 {caption}</figcaption>}
    </figure>
  );
}

/** Lay a couple of zoomed exhibits side by side instead of stacking them. */
function ShotRow({ children }: { children: React.ReactNode }) {
  return <div className="manual-shot-row">{children}</div>;
}

const SECTIONS: Section[] = [
  {
    id: "welcome",
    icon: "🎩",
    label: "Foreword",
    body: (
      <>
        <h3>Welcome to the Bureau</h3>
        <p>
          Every rookie detective thinks they'll crack the case by staring hard enough at a
          suspect's face. They won't. This manual exists because the department got tired of
          new hires wandering into the morgue asking the corpse for its alibi.
        </p>
        <Shot
          file="00-intro-cinematic.jpg"
          alt="The body-discovery cinematic showing the victim, the discovery time, and the scene"
          caption="Exhibit A — the opening scene. Plays once, the first time a new case lands on your desk."
          full
        />
        <p>
          <strong>No One Saw Everything</strong> is a fair-play mystery: everything you need to
          name the killer is somewhere in the game, discoverable through play. Nothing is
          hidden behind a dice roll — only behind your own thoroughness. Rewind the morning,
          watch where people went, search the places that matter, ask sharp questions, catch
          people in their lies, and build a case that survives the accusation.
        </p>
        <Aside>
          Rule #0: everyone is hiding <em>something</em>. Doesn't mean everyone's a killer.
          Half of them are just embarrassed about where they really were.
        </Aside>
        <p className="muted small">
          Use the tabs on the left to walk through every screen in the Bureau — each one comes
          with real screenshots, not just my word for it. Or skip straight to the case; solving
          a mystery without reading the manual is also a time-honoured detective tradition.
        </p>
      </>
    ),
  },
  {
    id: "hub",
    icon: "🗄️",
    label: "The Case Hub",
    body: (
      <>
        <h3>The Case Hub</h3>
        <p>
          This is the desk you sit at before and between cases — your home screen. From here you
          manage which case is active; nothing here touches your progress on that case's board.
        </p>
        <Shot
          file="01-hub-full.jpg"
          alt="The Case Hub landing screen with the active case panel, action grid, and recent cases"
          caption="The Case Hub — your desk. The active case sits front and centre; everything else is a drawer."
          full
        />
        <Opt name="Continue Investigation / Start a New Case">
          The big panel up top. If a case is already open on your desk, this drops you straight
          back into it. If your desk is clear, it invites you to open one — a detective with no
          active case is just a person in a coat.
        </Opt>
        <Opt name="📁 New Case · 🎲 Generate Case · 📚 Case Library · ⚙️ Settings">
          The four-button drawer. New Case pulls from the department's archive; Generate Case
          commissions a fresh AI-written scenario; Case Library browses everything you've
          generated so far; Settings covers audio, LLM, and generation preferences.
        </Opt>
        <Shot
          file="01c-hub-actions.png"
          alt="The four action buttons: New Case, Generate Case, Case Library, Settings"
          caption="The drawer of options — pick your poison."
        />
        <Opt name="🕵️ Rank badge / 🔊 Audio controls">
          Top right of the desk. The rank badge opens your detective record — cases solved vs.
          closed, tracked locally on this device. The speaker icon mutes or adjusts ambience and
          stingers; the Bureau does not judge detectives who investigate in silence.
        </Opt>
        <Shot
          file="01b-hub-toolbar.png"
          alt="The rank badge and audio control widgets in the top right of the hub"
          caption="Rank badge (left) and audio controls (right) — your only two on-screen widgets outside a case."
        />
        <Opt name="📖 How to Play">You're soaking in it.</Opt>
        <Aside>
          Recent Cases (right column) lists your last few case files — click one to jump
          straight back in without digging through the whole library.
        </Aside>
      </>
    ),
  },
  {
    id: "case-file",
    icon: "🗞️",
    label: "The Case File",
    body: (
      <>
        <h3>Case File (first tab, "Overview")</h3>
        <p>
          The briefing. This is what lands on your desk the moment a case opens: who's dead,
          who found them, where, and the estimated window in which it happened.
        </p>
        <Shot
          file="02-overview-full.jpg"
          alt="The Case File overview screen showing the victim, discovery facts, and Begin Investigation button"
          caption="The Case File — read it twice. It's the only page in the Bureau that owes you nothing but facts."
          full
        />
        <Opt name="Discovery time & victim">
          The headline facts of the case — fixed, not up for interpretation.
        </Opt>
        <Opt name="Found by / Where / Murder window / Rewind available">
          The bones of the case. The murder window in particular is worth memorising — it's the
          timeframe you'll be leaning on hardest once you start cross-checking alibis. "Rewind
          available" is the full stretch of the morning you can replay; nothing outside it
          happened where you can see it.
        </Opt>
        <Shot
          file="02b-overview-facts.png"
          alt="The facts list: found by, where, estimated murder window, and rewind availability"
          caption="The four facts that anchor the whole investigation."
        />
        <Opt name="Begin investigation">
          Jumps you into Rewind. This is the button that ends the paperwork and starts the
          actual detective work.
        </Opt>
        <Shot
          file="02c-overview-begin.png"
          alt="The Begin Investigation button"
          caption="Press when ready. There's no prize for lingering on the briefing."
        />
        <Aside>
          Detectives who skip the briefing are the ones who show up to interview the gardener
          about a murder that happened in the library.
        </Aside>
      </>
    ),
  },
  {
    id: "rewind",
    icon: "⏪",
    label: "Rewind",
    body: (
      <>
        <h3>Rewind</h3>
        <p>
          The village's morning, replayed as a scrolling feed of everything that happened in
          public view — or partly in view, or barely in view. This is where you build your
          first mental map of who went where.
        </p>
        <Shot
          file="03-rewind-full.jpg"
          alt="The Rewind screen with the time strip, filters, and the scrolling event feed"
          caption="Rewind — the morning, minute by minute, as the village actually saw it."
          full
        />
        <Opt name="Time strip / From / To sliders">
          The bar along the top marks the murder window in a shaded band; drag the From/To
          handles below it to narrow or widen what you're watching.
        </Opt>
        <Opt name="Murder window chip / Full period chip / Location & Who filters">
          The murder window chip snaps the view straight to the estimated time of death — your
          most-used button, deservedly so. The full-period chip zooms back out. Location and Who
          narrow the feed further; filtering by a person only shows moments where they were
          publicly identifiable.
        </Opt>
        <Shot
          file="03b-rewind-controls.png"
          alt="The full Rewind control panel: time strip, from/to sliders, murder window chip, and filters"
          caption="The whole control panel in one glance — scrub, snap, and filter."
          full
        />
        <Opt name="Event visibility badges / Pin">
          Some events are stamped <em>unclear</em> or <em>obscured</em> — a figure glimpsed at a
          distance, a shape half-seen through a window. These aren't bugs; they're exactly the
          ambiguity a fair-play mystery is supposed to give you to untangle. Pin sends an event to
          your Case Board for later reference, and can surface new evidence in the process.
        </Opt>
        <Shot
          file="03d-rewind-event-row.png"
          alt="A single event row with its time, description, location, witnesses, and pin button"
          caption="One event row — time, what happened, who was there, and the Pin button on the right."
        />
        <Aside>
          You cannot pin your way to a conviction. Pinning is a bookmark, not proof. Save the
          board for what actually holds up.
        </Aside>
      </>
    ),
  },
  {
    id: "map",
    icon: "🗺️",
    label: "Map Replay",
    body: (
      <>
        <h3>Map Replay</h3>
        <p>
          The same morning as Rewind, but staged on an actual map with little animated figures
          walking their routes. Occasionally the fastest way to spot "wait, how were they in two
          places at once?" is to just watch it happen.
        </p>
        <Shot
          file="04-map-full.jpg"
          alt="The Map Replay screen showing the village map with agent pins and the observed events feed"
          caption="Map Replay — the whole village, wandering in real time."
          full
        />
        <Opt name="Location / Who filters / Trace toggle">
          Thin the map down to one place or one person's movements. Once a specific person is
          picked, a trace toggle appears to draw their path as a trail across the map — handy for
          "where exactly did they wander during the window."
        </Opt>
        <Shot
          file="04b-map-toolbar.png"
          alt="The map's location and agent filter dropdowns"
          caption="Filter the map before you scrub it — fewer footprints, clearer picture."
        />
        <Opt name="Playback controls">
          Play, pause, and a speed selector. Scrub the timeline directly if you'd rather jump
          than watch.
        </Opt>
        <Shot
          file="04c-map-playback.png"
          alt="The playback bar: play button, current time, scrubber, and speed selector"
          caption="Play it live, or just drag the dot — both get you there."
        />
        <Opt name="Click a pin / marker / Truth mode toggle">
          Clicking a pin opens event details or jumps straight to that suspect's interview panel.
          Truth mode only unlocks <em>after</em> you've made your accusation — before that, the
          map never shows you the ground truth. That's not a limitation, that's the whole point
          of the game.
        </Opt>
        <Aside>
          If two people's tracks look like they should have crossed paths but the event feed
          never shows them meeting — that's not a glitch, that's a lead.
        </Aside>
      </>
    ),
  },
  {
    id: "places",
    icon: "🔍",
    label: "Places",
    body: (
      <>
        <h3>Places</h3>
        <p>
          Rewind and Map Replay show you where people <em>were</em>. Places lets you search
          where they <em>left things</em>.
        </p>
        <Shot
          file="05c-places-detail.jpg"
          alt="The Places screen with a location selected, showing the magnifying search and found evidence"
          caption="A location under the lens — search status, found evidence, and notes, all in one pane."
          full
        />
        <Opt name="Location list (left)">
          Every searchable location on the estate. Locations marked{" "}
          <span className="badge ambiguous">private</span> are back-rooms and personal spaces —
          you can still search them, but doing so where someone could see you may affect how
          they feel about you later.
        </Opt>
        <Shot
          file="05b-places-list.png"
          alt="The location list with private badges on back-rooms"
          caption="Every door on the estate. Purple tags mean you're trespassing a little."
        />
        <Opt name="Search status / Magnifying glass search">
          The status line shows how many clues you've found here out of the total hidden. Sweep
          the magnifying lens over the scene — it glints when it passes something worth a closer
          look. This is the game's one honest-to-goodness minigame, and it rewards patience over
          frantic clicking.
        </Opt>
        <Shot
          file="05d-places-magnifier.png"
          alt="The magnifying glass search tool sweeping over a location"
          caption="Sweep, don't spam. The glint tells you when to click."
        />
        <Opt name="Found evidence">
          Everything you've already turned up here, catalogued as clue cards.
        </Opt>
        <Aside>
          A location with zero hidden clues left isn't a location you've "beaten" — it just
          means the next clue is going to come from a person's mouth, not the furniture.
        </Aside>
      </>
    ),
  },
  {
    id: "suspects",
    icon: "🎭",
    label: "Suspects",
    body: (
      <>
        <h3>Suspects</h3>
        <p>
          The interrogation room. Pick a name from the roster on the left; everyone but the
          victim gets an interview panel, and the victim gets an autopsy table instead — corpses
          make notoriously poor conversationalists.
        </p>
        <Shot
          file="06-suspects-full.jpg"
          alt="The Suspects screen with the roster on the left and an interview panel open"
          caption="A suspect under questioning — dossier, transcript, and your judgement, side by side."
          full
        />
        <Opt name="Suspect roster">
          Portrait, occupation, and — once you've judged them — your own suspicion label. The
          portrait's border tints as pressure builds, so you can spot who's rattled at a glance.
        </Opt>
        <ShotRow>
          <Shot
            file="06b-suspects-roster.png"
            alt="The suspect roster list with portraits and occupations"
            caption="The full roster, at a glance."
          />
          <Shot
            file="06c-suspects-dossier.png"
            alt="A suspect's dossier card: portrait, name, occupation, traits, and routine summary"
            caption="Their dossier — traits and routine, before you've asked a single question."
          />
        </ShotRow>
        <Opt name="Free-text question box / Predefined topics">
          Type anything, in your own words, and the game classifies it and routes it to a
          grounded answer. Or use the predefined buttons — alibi, last seen, relationship, "what
          were you doing at [time]" — when you don't feel like typing.
        </Opt>
        <Shot
          file="06d-suspects-questions.png"
          alt="The question builder with free-text input and predefined topic buttons"
          caption="Ask it your way, or pick from the department's greatest hits."
        />
        <Opt name="Question about a place / Confront with evidence">
          Ask what a suspect knows about a specific location, or put a discovered clue directly
          in front of them and watch how they react. Confrontation requires evidence you've
          actually found — you can't confront someone with a clue that only exists in your
          imagination.
        </Opt>
        <Opt name="Contradictions you can press">
          Appears automatically once you're holding evidence that conflicts with something
          they've told you. Hit Challenge and watch the story crack — or, occasionally, watch
          them talk their way out of it if your evidence doesn't quite land.
        </Opt>
        <Opt name="Interview transcript">
          Full record of the conversation so far. A ✨ next to a line means the flavour text was
          rewritten by the LLM layer — hover it to see the plain deterministic answer underneath,
          in case you don't trust flowery prose over facts (correctly so, some might say).
        </Opt>
        <Opt name="Your judgement (right panel) / Pressure meter">
          Your private suspicion label — unmarked through prime suspect, or likely innocent
          through cleared. Purely for your own bookkeeping; it doesn't feed the accusation
          grading. Pressure climbs as you challenge and corner someone; it's a side effect of
          good interrogation, not a goal in itself.
        </Opt>
        <Shot
          file="06e-suspects-judgement.png"
          alt="The judgement panel with the suspicion dropdown and pressure meter"
          caption="Your private notebook — nobody in the village can read this over your shoulder."
        />
        <Opt name="Autopsy panel (victim only)">
          The subject arrives on the slab under a sheet. Take the <strong>gloves</strong> from
          the instrument tray to fold it back — only then does your magnifier find anything;
          same sweep-and-glint search as Places, run over the body instead of a room. Click the
          gloves again to re-cover the subject when you're done. The tray's other tools are all
          marked "coroner's use only" — you're a detective, not a surgeon, and the Bureau would
          very much like to keep it that way.
        </Opt>
        <Shot
          file="06f-autopsy-full.jpg"
          alt="The morgue: the covered subject on the examination slab, instrument tray on the left, coroner's report clipboard on the right"
          caption="The morgue. The subject is covered when you arrive — reach for the gloves."
          full
        />
        <Shot
          file="06g-autopsy-sheet.png"
          alt="The examination slab with the sheet folded back to the foot, body revealed for the magnifier"
          caption="Sheet folded back — now the magnifier can do its work."
        />
        <Aside>
          A suspect going quiet or defensive is not a confession. Plenty of innocent people
          clam up the second a detective corners them in a room — wouldn't you?
        </Aside>
      </>
    ),
  },
  {
    id: "board",
    icon: "📌",
    label: "Case Board",
    body: (
      <>
        <h3>Case Board</h3>
        <p>
          Your corkboard, string and all. Everything you've gathered lives here — this is where
          scattered interviews and evidence turn into an actual case.
        </p>
        <Shot
          file="07-board-full.jpg"
          alt="The Case Board with the suspects column, guidance and evidence column, and notes column"
          caption="Three columns: who you suspect, what you've found, and what you've written down."
          full
        />
        <Opt name="Suspects column / Marker checkboxes / Claims">
          Every suspect as a card: portrait, occupation, suspicion badge, and expandable claims
          and linked evidence. Red Herring, Cleared, Prime Suspect are tick boxes purely for your
          own case-management sanity — tick generously, changing your mind later costs nothing
          but pride.
        </Opt>
        <Shot
          file="07b-board-suspect-card.png"
          alt="A single suspect card on the board with marker checkboxes"
          caption="One suspect card — badge, markers, and the claims tucked underneath."
        />
        <Opt name="Guidance panel / Evidence column">
          Gentle nudges when you seem stuck, and every clue you've discovered anywhere in the
          game, all catalogued in one list.
        </Opt>
        <Opt name="Notes column">
          Write your own: plain notes, contradictions, theories, or open questions. Pin a note to
          a suspect and a red thread is drawn straight from the board pin to their card — very
          satisfying, mildly over-dramatic, entirely optional.
        </Opt>
        <Shot
          file="07c-board-notes-form.png"
          alt="The note-creation form with type selector, pin-to-suspect dropdown, title, and body"
          caption="Write it down. Future-you, three suspects deep, will thank present-you."
        />
        <Aside>
          The string is cosmetic. The department will not accept "but it was pinned on the
          board" as evidence in itself — you still need the clue and the claim behind it.
        </Aside>
      </>
    ),
  },
  {
    id: "accuse",
    icon: "⚖️",
    label: "Accuse",
    body: (
      <>
        <h3>Accuse</h3>
        <p>
          The last tab, set apart from the rest for a reason: this is a one-way door. Submitting
          here reveals the truth of the whole case and grades your reasoning against it.
        </p>
        <Shot
          file="08-accuse-full.jpg"
          alt="The Accuse screen with the accusation form and supporting evidence checklist"
          caption="The final page. Everything before this was rehearsal."
          full
        />
        <Opt name="Who killed them?">
          Pick from every living suspect. No going back after this loads — make sure the rest of
          the form is ready first.
        </Opt>
        <Opt name="Motive / Method / Opportunity">
          Write your case in your own words. You're not filling in blanks for a multiple-choice
          quiz — the game is genuinely marking the substance of what you argue.
        </Opt>
        <Shot
          file="08b-accuse-form.png"
          alt="The accusation form fields: who, motive, method, and opportunity"
          caption="Four fields. Say what you actually think happened."
        />
        <Opt name="Supporting evidence & notes">
          Tick every clue and note that backs up your accusation. Cite generously — an accusation
          with no supporting evidence is just a guess wearing a trenchcoat.
        </Opt>
        <Shot
          file="08c-accuse-evidence.png"
          alt="The supporting evidence and notes checklist"
          caption="Cite your sources. This isn't a courtroom, but it might as well be."
        />
        <Opt name="Submit accusation">
          Locks the case. What follows is the reveal ceremony: the real killer, motive, method,
          and a breakdown of what you got right, what you missed, and where the herrings were
          hiding.
        </Opt>
        <Aside>
          There is no "undo" on an accusation short of resetting the whole case. Detectives who
          rush this screen end up explaining themselves to a superior officer. Take the extra
          five minutes.
        </Aside>
      </>
    ),
  },
  {
    id: "glossary",
    icon: "📔",
    label: "Field Glossary",
    body: (
      <>
        <h3>Field Glossary</h3>
        <Opt name="Suspicion levels">
          Your own private read on a suspect: unmarked → person of interest → suspect → prime
          suspect, or likely innocent → cleared. Set it from their interview panel or the board;
          it's advisory, not a game mechanic.
        </Opt>
        <Opt name="Pressure">
          How rattled a suspect is from being challenged. Rises with successful confrontations,
          shows up as a meter and a portrait tint. High pressure changes their demeanour, not
          the facts they know.
        </Opt>
        <Opt name="Demeanour">
          Cosmetic label — Unquestioned, Cooperative, Evasive, Contradicted, Cleared — derived
          from transcript length, pressure, and whether you've caught them out. Flavour, not a
          verdict.
        </Opt>
        <Opt name="Event visibility">
          Public (everyone could plausibly have seen it), unclear/public-partial (glimpsed,
          ambiguous), or hidden (you'll never see it before the reveal — by design). What you get
          shown is always exactly what a real witness standing there could have known.
        </Opt>
        <Opt name="Claims vs. clues">
          A claim is something a suspect told you. A clue is physical or forensic evidence you
          found yourself. Contradictions happen when a claim and a clue can't both be true —
          that collision is the engine of the whole game.
        </Opt>
        <Opt name="Background villagers">
          A few faces wandering the map are pure atmosphere — not suspects, not witnesses, not
          interviewable. If someone never shows up on the Suspects tab or the Board, that's why.
        </Opt>
      </>
    ),
  },
  {
    id: "tips",
    icon: "🥃",
    label: "Notes from the Chief",
    body: (
      <>
        <h3>Notes from the Chief</h3>
        <p>
          Off the record, from someone who's closed a few of these:
        </p>
        <ul className="manual-list">
          <li>Rewind first, interview second. Know the shape of the morning before you start asking people to explain it.</li>
          <li>An alibi that lines up perfectly with what you already saw on the map is worth more than a dozen dramatic confessions.</li>
          <li>Search a room <em>before</em> you interview the person who lives in it. Confronting someone with evidence they don't know you have is where the real cracks show.</li>
          <li>If a suspect's story and the Rewind feed disagree on where they were, that disagreement is the case. Chase it with the Confront tool, not with vibes.</li>
          <li>Don't accuse the moment you're allowed to. Allowed to and ready to are different things — the Board's guidance panel will tell you when you're closer to the latter.</li>
          <li>Every red herring in this department was put there on purpose. Getting fooled by one isn't a bug report, it's Tuesday.</li>
        </ul>
        <Aside>Go on. The village isn't going to interrogate itself.</Aside>
      </>
    ),
  },
];

export default function Detective101Modal({ onClose }: Detective101ModalProps) {
  useEscapeToClose(onClose);
  const [sectionId, setSectionId] = useState(SECTIONS[0].id);
  const active = SECTIONS.find((s) => s.id === sectionId) ?? SECTIONS[0];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal detective-manual"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "980px",
          width: "95%",
          maxHeight: "88vh",
          padding: 0,
          display: "flex",
          flexDirection: "column",
          gap: 0,
          overflow: "hidden",
        }}
      >
        <div className="manual-header">
          <div>
            <span className="brand-eyebrow">Bureau Training Manual</span>
            <h2 style={{ margin: "0.2rem 0 0" }}>🕵️ Detective 101</h2>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="manual-body">
          <nav className="manual-toc">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                className={s.id === sectionId ? "manual-toc-item active" : "manual-toc-item"}
                aria-current={s.id === sectionId ? "page" : undefined}
                onClick={() => setSectionId(s.id)}
              >
                <span className="manual-toc-icon">{s.icon}</span>
                <span>{s.label}</span>
              </button>
            ))}
          </nav>
          <div className="manual-content">{active.body}</div>
        </div>
      </div>
    </div>
  );
}

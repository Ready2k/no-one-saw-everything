import { useWorld } from "../App";
import { timeOfDayLabel } from "../api";
import Portrait from "../components/Portrait";
import { sfx } from "../sfx";

export default function Overview({ onBegin }: { onBegin: () => void }) {
  const { caseOverview: c } = useWorld();
  const period = timeOfDayLabel(c.sim_start_time);
  return (
    <div className="overview">
      <div className="discovery-card">
        <div className="discovery-time">{c.discovery_time}</div>
        <h1>{c.victim.full_name} is dead.</h1>
        <p className="overview-text">{c.overview_text}</p>
        <dl className="facts">
          <div>
            <dt>Found by</dt>
            <dd>
              <Portrait agent={c.discovered_by} /> {c.discovered_by.full_name}
            </dd>
          </div>
          <div>
            <dt>Where</dt>
            <dd>{c.discovery_location.name}</dd>
          </div>
          <div>
            <dt>Estimated murder window</dt>
            <dd>
              {c.murder_window[0]} – {c.murder_window[1]}
            </dd>
          </div>
          <div>
            <dt>Rewind available</dt>
            <dd>
              {c.sim_start_time} – {c.discovery_time}
            </dd>
          </div>
        </dl>
        <button
          className="primary"
          onClick={() => {
            sfx.pageTurn();
            onBegin();
          }}
        >
          Begin investigation
        </button>
        <p className="hint-text">
          Rewind the {period}. Watch who went where. Inspect the places that
          matter. Question everyone. Pin what doesn't add up.
        </p>
      </div>
    </div>
  );
}

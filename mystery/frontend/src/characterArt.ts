import type { AgentPublic } from "./types";

// One visual bible shared by every authored case. Cases reuse residents, so
// keeping their likenesses here prevents the same person changing appearance
// from one mystery to the next.
const LIFELIKE_CALM: Record<string, string> = {
  agent_clara: "/art/case_005/portraits/clara_wells_calm.avif",
  agent_owen: "/art/case_005/portraits/owen_price_calm.avif",
  agent_ben: "/art/case_005/portraits/ben_carter_calm.avif",
  agent_nadia: "/art/case_005/portraits/nadia_cole_calm.avif",
  agent_elias: "/art/case_005/portraits/elias_grant_calm.avif",
  agent_col: "/art/case_005/portraits/col_hartley_calm.avif",
  agent_marcus: "/art/portraits/lifelike/marcus_bell_calm.avif",
  agent_isabella: "/art/portraits/lifelike/isabella_reed_calm.avif",
  agent_priya: "/art/portraits/lifelike/priya_shah_calm.avif",
  agent_ruth: "/art/portraits/lifelike/ruth_calder_calm.avif",
  agent_dr_haig: "/art/portraits/lifelike/dr_haig_calm.avif",
  agent_fred: "/art/portraits/lifelike/fred_dunmore_calm.avif",
  agent_solicitor: "/art/portraits/lifelike/mr_whittle_calm.avif",
  agent_bg_rosa: "/art/portraits/lifelike/rosa_fenn_calm.avif",
  agent_rosa: "/art/portraits/lifelike/rosa_fenn_calm.avif",
  agent_bg_wren: "/art/portraits/lifelike/wren_ashby_calm.avif",
  agent_bg_sal: "/art/portraits/lifelike/sal_ibori_calm.avif",
  agent_bg_min: "/art/portraits/lifelike/min_okafor_calm.avif",
  agent_bg_cole: "/art/portraits/lifelike/cole_byrne_calm.avif",
  agent_bg_dez: "/art/portraits/lifelike/dez_holt_calm.avif",
  agent_bg_birdie: "/art/portraits/lifelike/birdie_voss_calm.avif",
  agent_bg_tam: "/art/portraits/lifelike/tam_doyle_calm.avif",
  agent_tam: "/art/portraits/lifelike/tam_doyle_calm.avif",
  agent_bg_gus: "/art/portraits/lifelike/gus_farrow_calm.avif",
  agent_bg_effie: "/art/portraits/lifelike/effie_marsh_calm.avif",
};

const LIFELIKE_DECEASED: Record<string, string> = {
  agent_clara: "/art/case_005/portraits/clara_wells_deceased.avif",
  agent_marcus: "/art/portraits/lifelike/marcus_bell_deceased.avif",
  agent_isabella: "/art/portraits/lifelike/isabella_reed_deceased.avif",
  agent_elias: "/art/portraits/lifelike/elias_grant_deceased.avif",
  agent_owen: "/art/portraits/lifelike/owen_price_deceased.avif",
};

export function lifelikeCalmPortrait(agent: Pick<AgentPublic, "agent_id" | "portrait_art">): string | null {
  return LIFELIKE_CALM[agent.agent_id] ?? agent.portrait_art?.calm ?? null;
}

export function lifelikeDeceasedPortrait(agent: Pick<AgentPublic, "agent_id" | "portrait_art">): string | null {
  return LIFELIKE_DECEASED[agent.agent_id] ?? null;
}

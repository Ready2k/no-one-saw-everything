import type { AgentPublic } from "./types";

// One visual bible shared by every authored case. Cases reuse residents, so
// keeping their likenesses here prevents the same person changing appearance
// from one mystery to the next.
const LIFELIKE_CALM: Record<string, string> = {
  agent_clara: "/art/case_005/portraits/clara_wells_calm.png",
  agent_owen: "/art/case_005/portraits/owen_price_calm.png",
  agent_ben: "/art/case_005/portraits/ben_carter_calm.png",
  agent_nadia: "/art/case_005/portraits/nadia_cole_calm.png",
  agent_elias: "/art/case_005/portraits/elias_grant_calm.png",
  agent_col: "/art/case_005/portraits/col_hartley_calm.png",
  agent_marcus: "/art/portraits/lifelike/marcus_bell_calm.png",
  agent_isabella: "/art/portraits/lifelike/isabella_reed_calm.png",
  agent_priya: "/art/portraits/lifelike/priya_shah_calm.png",
  agent_ruth: "/art/portraits/lifelike/ruth_calder_calm.png",
  agent_dr_haig: "/art/portraits/lifelike/dr_haig_calm.png",
  agent_fred: "/art/portraits/lifelike/fred_dunmore_calm.png",
  agent_solicitor: "/art/portraits/lifelike/mr_whittle_calm.png",
  agent_bg_rosa: "/art/portraits/lifelike/rosa_fenn_calm.png",
  agent_bg_wren: "/art/portraits/lifelike/wren_ashby_calm.png",
  agent_bg_sal: "/art/portraits/lifelike/sal_ibori_calm.png",
  agent_bg_min: "/art/portraits/lifelike/min_okafor_calm.png",
  agent_bg_cole: "/art/portraits/lifelike/cole_byrne_calm.png",
  agent_bg_dez: "/art/portraits/lifelike/dez_holt_calm.png",
  agent_bg_birdie: "/art/portraits/lifelike/birdie_voss_calm.png",
  agent_bg_tam: "/art/portraits/lifelike/tam_doyle_calm.png",
  agent_bg_gus: "/art/portraits/lifelike/gus_farrow_calm.png",
  agent_bg_effie: "/art/portraits/lifelike/effie_marsh_calm.png",
};

const LIFELIKE_DECEASED: Record<string, string> = {
  agent_clara: "/art/case_005/portraits/clara_wells_deceased.png",
  agent_marcus: "/art/portraits/lifelike/marcus_bell_deceased.png",
  agent_isabella: "/art/portraits/lifelike/isabella_reed_deceased.png",
  agent_elias: "/art/portraits/lifelike/elias_grant_deceased.png",
  agent_owen: "/art/portraits/lifelike/owen_price_deceased.png",
};

export function lifelikeCalmPortrait(agent: Pick<AgentPublic, "agent_id" | "portrait_art">): string | null {
  return LIFELIKE_CALM[agent.agent_id] ?? agent.portrait_art?.calm ?? null;
}

export function lifelikeDeceasedPortrait(agent: Pick<AgentPublic, "agent_id" | "portrait_art">): string | null {
  return LIFELIKE_DECEASED[agent.agent_id] ?? null;
}

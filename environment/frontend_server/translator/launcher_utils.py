"""
Launcher utilities: scan the storage folder for simulation runs and extract
review data (metadata, progress, conversations, memory counts).

Used by the graphical launcher / run-browser views. All paths are relative to
the frontend_server working directory, matching the rest of translator/views.py.
"""
import os
import re
import json
import datetime
import time

STORAGE = "storage"
TEMP_STORAGE = "temp_storage"
SIM_LIBRARY = os.path.join(STORAGE, "sim_library")

# Forks the launcher offers as "base" templates to start a new run from.
# Anything matching these prefixes is treated as a reusable base, not a run.
BASE_PREFIXES = ("base_the_ville",)


# ── Sim library (persona template CRUD) ──────────────────────────────────────

def _library_slug(name):
  """Convert a persona name to a filesystem-safe slug, e.g. 'Isabella Rodriguez' → 'isabella_rodriguez'."""
  return "".join(c if c.isalnum() or c == "-" else "_" for c in name.lower()).strip("_")


def library_list():
  """Return sorted list of all persona profiles in the sim library."""
  if not os.path.isdir(SIM_LIBRARY):
    return []
  profiles = []
  for slug in sorted(os.listdir(SIM_LIBRARY)):
    if slug.startswith("."):
      continue
    p = _safe_load(os.path.join(SIM_LIBRARY, slug, "profile.json"))
    if p:
      profiles.append(p)
  return profiles


def library_get(slug):
  """Return a single library profile dict by slug, or None."""
  return _safe_load(os.path.join(SIM_LIBRARY, slug, "profile.json"))


def library_save(slug, data):
  """Write (create or update) a library profile. Returns the saved dict."""
  d = os.path.join(SIM_LIBRARY, slug)
  os.makedirs(d, exist_ok=True)
  path = os.path.join(d, "profile.json")
  existing = _safe_load(path) or {}
  existing.update(data)
  existing["slug"] = slug
  if "created" not in existing:
    existing["created"] = datetime.datetime.now().isoformat(timespec="seconds")
  existing["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
  with open(path, "w") as f:
    json.dump(existing, f, indent=2)
  return existing


def library_delete(slug):
  """Delete a library profile directory. Returns True if it existed."""
  import shutil
  d = os.path.join(SIM_LIBRARY, slug)
  if os.path.isdir(d):
    shutil.rmtree(d)
    return True
  return False


# ── Spawn-tile map ────────────────────────────────────────────────────────────
# Maps "sector:arena" (from a persona's living_area) to an (x, y) tile.
# Built once from the static maze CSV files.

_MAZE_MATRIX = os.path.join(
    os.path.dirname(__file__), "..", "static_dirs", "assets",
    "the_ville", "matrix")

_SPAWN_TILES = None  # lazy singleton


def _build_spawn_tiles():
  """Parse the Tiled CSV maze to build {sector:arena -> (x, y)}."""
  blocks_path = os.path.join(_MAZE_MATRIX, "special_blocks",
                             "spawning_location_blocks.csv")
  maze_path   = os.path.join(_MAZE_MATRIX, "maze",
                             "spawning_location_maze.csv")
  slb = {}
  try:
    with open(blocks_path) as f:
      for line in f:
        parts = [p.strip() for p in line.strip().split(",")]
        if len(parts) >= 4:
          slb[int(parts[0])] = {"sector": parts[2], "arena": parts[3]}
  except Exception:
    return {}
  W = 140  # maze width tiles
  result = {}
  try:
    with open(maze_path) as f:
      vals = [int(v.strip()) for v in f.read().split(",") if v.strip()]
    for idx, val in enumerate(vals):
      if val and val in slb:
        x, y = idx % W, idx // W
        key = f'{slb[val]["sector"]}:{slb[val]["arena"]}'
        if key not in result:          # keep first occurrence (sp-A)
          result[key] = (x, y)
  except Exception:
    pass
  return result


def get_spawn_tile(living_area):
  """Return (x, y) spawn tile for a living_area string like
  'the Ville:sector:arena', or None if not found."""
  global _SPAWN_TILES
  if _SPAWN_TILES is None:
    _SPAWN_TILES = _build_spawn_tiles()
  parts = living_area.split(":")
  if len(parts) >= 3:
    key = f"{parts[1]}:{parts[2]}"
    return _SPAWN_TILES.get(key)
  return None


# ── Full spatial-memory tree ──────────────────────────────────────────────────
# A persona's spatial_memory.json is normally just the subset of locations
# *that persona* has personally discovered (e.g. an existing persona only
# knows their own home, workplace, and a few hangouts). Copying one persona's
# partial knowledge onto a brand-new persona means they crash the moment they
# try to act anywhere that persona never went -- most reliably, their own new
# living_area. So new personas instead get the full map, parsed once from the
# same Tiled CSVs that back get_spawn_tile()/the location picker.

_FULL_SPATIAL_TREE = None  # lazy singleton: {world: {sector: {arena: [objects]}}}


def _load_blocks_dict(path):
  """Parse a special_blocks CSV (id, world, ..., name) into {id: name}."""
  d = {}
  try:
    with open(path) as f:
      for line in f:
        parts = [p.strip() for p in line.strip().split(",")]
        if len(parts) >= 2:
          d[parts[0]] = parts[-1]
  except Exception:
    pass
  return d


def _load_maze_row(path):
  try:
    with open(path) as f:
      return [v.strip() for v in f.read().split(",")]
  except Exception:
    return []


def _build_full_spatial_tree():
  """Parse the maze CSVs into {world: {sector: {arena: [objects]}}} for every
  location on the map."""
  blocks_dir = os.path.join(_MAZE_MATRIX, "special_blocks")
  maze_dir   = os.path.join(_MAZE_MATRIX, "maze")

  world_blocks = _load_blocks_dict(os.path.join(blocks_dir, "world_blocks.csv"))
  world_name = next(iter(world_blocks.values()), "the Ville")
  sb  = _load_blocks_dict(os.path.join(blocks_dir, "sector_blocks.csv"))
  ab  = _load_blocks_dict(os.path.join(blocks_dir, "arena_blocks.csv"))
  gob = _load_blocks_dict(os.path.join(blocks_dir, "game_object_blocks.csv"))

  sector_maze = _load_maze_row(os.path.join(maze_dir, "sector_maze.csv"))
  arena_maze  = _load_maze_row(os.path.join(maze_dir, "arena_maze.csv"))
  gobj_maze   = _load_maze_row(os.path.join(maze_dir, "game_object_maze.csv"))

  tree = {}
  n = min(len(sector_maze), len(arena_maze), len(gobj_maze))
  for idx in range(n):
    sector = sb.get(sector_maze[idx])
    if not sector:
      continue
    arena = ab.get(arena_maze[idx])
    if not arena:
      continue
    objs = tree.setdefault(world_name, {}).setdefault(sector, {}).setdefault(arena, [])
    obj = gob.get(gobj_maze[idx])
    if obj and obj not in objs:
      objs.append(obj)
  return tree


def get_full_spatial_tree():
  global _FULL_SPATIAL_TREE
  if _FULL_SPATIAL_TREE is None:
    _FULL_SPATIAL_TREE = _build_full_spatial_tree()
  return _FULL_SPATIAL_TREE


# ── Pre-fork directory builder ────────────────────────────────────────────────

def _empty_associative_memory(am_dir):
  """Write empty associative memory files into am_dir."""
  os.makedirs(am_dir, exist_ok=True)
  with open(os.path.join(am_dir, "nodes.json"), "w") as f:
    json.dump({}, f)
  with open(os.path.join(am_dir, "embeddings.json"), "w") as f:
    json.dump({}, f)
  with open(os.path.join(am_dir, "kw_strength.json"), "w") as f:
    json.dump({"kw_strength_event": {}, "kw_strength_thought": {}}, f)


def build_new_persona_dir(persona_dir, profile, template_scratch):
  """Create a complete bootstrap_memory directory for a brand-new persona.

  persona_dir       - target path, e.g. storage/{sim}/personas/{Name}
  profile           - dict from the sim library (scratch.json fields)
  template_scratch  - scratch dict from an existing persona (for defaults)
  """
  bm = os.path.join(persona_dir, "bootstrap_memory")
  os.makedirs(bm, exist_ok=True)

  # Resolve spawn tile from living_area
  living_area = profile.get("living_area") or template_scratch.get("living_area", "")
  tile = get_spawn_tile(living_area) if living_area else None
  if tile is None:
    tile = (template_scratch.get("curr_tile") or [73, 14])
    if isinstance(tile, list):
      tile = tuple(tile)

  name = profile.get("name", "New Persona")
  parts = name.strip().split()
  first = parts[0] if parts else name
  last  = " ".join(parts[1:]) if len(parts) > 1 else ""

  # Build scratch: start from template defaults, overlay profile values,
  # then reset runtime-state fields for a fresh start.
  scratch = dict(template_scratch)
  for k in ["name", "first_name", "last_name", "age", "innate", "learned",
            "currently", "lifestyle", "daily_plan_req", "living_area",
            "vision_r", "att_bandwidth", "retention", "recency_decay",
            "importance_trigger_max", "recency_w", "relevance_w",
            "importance_w", "concept_forget", "daily_reflection_time",
            "daily_reflection_size"]:
    if k in profile and profile[k] != "":
      scratch[k] = profile[k]

  scratch["name"]       = name
  scratch["first_name"] = first
  scratch["last_name"]  = last
  scratch["curr_tile"]  = list(tile)

  # Runtime state: fresh slate. Mirror a never-run persona's bootstrap
  # scratch.json exactly (all act_* fields None/empty) rather than fabricating
  # an in-progress "sleeping" action -- act_check_finished() branches on
  # act_address being truthy and then dereferences act_start_time, so a
  # truthy act_address with a None act_start_time crashes the first move().
  scratch["curr_time"]                  = None
  scratch["daily_req"]                  = []
  scratch["f_daily_schedule"]           = []
  scratch["f_daily_schedule_hourly_org"] = []
  scratch["act_address"]      = None
  scratch["act_start_time"]   = None
  scratch["act_duration"]     = None
  scratch["act_description"]  = None
  scratch["act_pronunciatio"] = None
  scratch["act_event"]        = [name, None, None]
  scratch["act_obj_description"]  = None
  scratch["act_obj_pronunciatio"] = None
  scratch["act_obj_event"]        = [None, None, None]
  scratch["chatting_with"]        = None
  scratch["chat"]                 = None
  scratch["chatting_with_buffer"] = {}
  scratch["chatting_end_time"]    = None
  scratch["act_path_set"]         = False
  scratch["planned_path"]         = []
  scratch["importance_trigger_curr"] = scratch.get("importance_trigger_max", 150)
  scratch["importance_ele_n"]        = 8
  scratch["thought_count"]           = 5

  with open(os.path.join(bm, "scratch.json"), "w") as f:
    json.dump(scratch, f, indent=2)

  # Spatial memory: full map, not a borrowed template's partial knowledge --
  # see get_full_spatial_tree() docstring for why.
  with open(os.path.join(bm, "spatial_memory.json"), "w") as f:
    json.dump(get_full_spatial_tree(), f, indent=2)

  # Associative memory: empty (no prior memories)
  _empty_associative_memory(os.path.join(bm, "associative_memory"))

  return tile


def prefork_directory(fork_sim_code, target_name, keep_personas=None,
                      add_profiles=None):
  """Build the target sim directory from a fork with persona modifications.

  keep_personas - list of existing persona names to include (None = all)
  add_profiles  - list of library profile dicts to inject as new personas

  Returns the target directory path, or raises on error.
  """
  import shutil
  fork_dir   = os.path.join(STORAGE, fork_sim_code)
  target_dir = os.path.join(STORAGE, target_name)

  if not os.path.isdir(fork_dir):
    raise FileNotFoundError(f"Fork source not found: {fork_dir}")
  if os.path.exists(target_dir):
    raise FileExistsError(f"Target already exists: {target_dir}")

  # Copy the full fork
  shutil.copytree(fork_dir, target_dir)

  personas_dir = os.path.join(target_dir, "personas")

  # Remove excluded personas
  if keep_personas is not None:
    keep_set = {p.strip() for p in keep_personas}
    for name in os.listdir(personas_dir):
      if not name.startswith(".") and name not in keep_set:
        shutil.rmtree(os.path.join(personas_dir, name))

  # Get a template persona for defaults (first remaining one)
  remaining = [p for p in os.listdir(personas_dir) if not p.startswith(".")]
  if not remaining:
    raise ValueError("No personas left in fork after exclusions.")
  template_name = remaining[0]
  template_bm   = os.path.join(personas_dir, template_name, "bootstrap_memory")
  template_scratch_path  = os.path.join(template_bm, "scratch.json")
  with open(template_scratch_path) as f:
    template_scratch = json.load(f)

  # Inject new personas from library. New personas also need to be registered
  # in reverie/meta.json's persona_names (reverie.py only spawns names listed
  # there) and given a spawn tile in the step-0 environment file (reverie.py
  # looks up init_env[persona_name]["x"/"y"] for every name in that list) --
  # otherwise they exist on disk but are silently never instantiated.
  added_names = []
  for profile in (add_profiles or []):
    persona_name = profile.get("name", "").strip()
    if not persona_name:
      continue
    persona_dir = os.path.join(personas_dir, persona_name)
    if os.path.exists(persona_dir):
      continue  # don't overwrite existing
    tile = build_new_persona_dir(persona_dir, profile, template_scratch)
    added_names.append((persona_name, tile))

  # Sync reverie/meta.json's persona_names with the final roster (exclusions
  # removed above + additions just built) -- reverie.py only spawns names
  # listed there, regardless of what's actually in personas_dir.
  meta_path = os.path.join(target_dir, "reverie", "meta.json")
  with open(meta_path) as f:
    meta = json.load(f)
  final_roster = sorted(p for p in os.listdir(personas_dir)
                        if not p.startswith("."))
  meta["persona_names"] = final_roster
  with open(meta_path, "w") as f:
    json.dump(meta, f, indent=2)

  if added_names:
    env_path = os.path.join(target_dir, "environment",
                            f"{meta.get('step', 0)}.json")
    env = _safe_load(env_path) or {}
    for persona_name, tile in added_names:
      x, y = tile
      env[persona_name] = {"maze": meta["maze_name"], "x": x, "y": y}
    with open(env_path, "w") as f:
      json.dump(env, f, indent=2)

  return target_dir


def _safe_load(path):
  try:
    with open(path) as f:
      return json.load(f)
  except Exception:
    return None


def _count_movement_steps(sim_dir):
  move_dir = os.path.join(sim_dir, "movement")
  if not os.path.isdir(move_dir):
    return 0
  n = 0
  for f in os.listdir(move_dir):
    if f.endswith(".json"):
      n += 1
  return n


def _persona_names(sim_dir):
  pdir = os.path.join(sim_dir, "personas")
  if not os.path.isdir(pdir):
    return []
  return sorted(p for p in os.listdir(pdir) if not p.startswith("."))


def _sim_time_reached(meta, steps):
  """Best-effort wall-clock time the run reached, from meta or step count."""
  if meta and meta.get("curr_time"):
    return meta["curr_time"]
  if meta and meta.get("start_date") and meta.get("sec_per_step") and steps:
    try:
      start = datetime.datetime.strptime(
          meta["start_date"] + " 00:00:00", "%B %d, %Y %H:%M:%S")
      start += datetime.timedelta(seconds=meta["sec_per_step"] * steps)
      return start.strftime("%B %d, %Y, %H:%M:%S")
    except Exception:
      return None
  return None


def _is_base(name):
  # A base template starts with a base prefix and is not itself a derived run
  # (derived runs carry a -run-<timestamp> or -step-<n> suffix).
  if "-run-" in name or "-step-" in name:
    return False
  return any(name.startswith(p) for p in BASE_PREFIXES)


def _any_reverie_process_alive():
  """Best-effort check for a live `reverie.py` backend process anywhere on the
  machine, not just ones the launcher itself spawned. Runs started by hand
  (e.g. from a terminal, fork/name typed in interactively) are real children
  of init once their parent shell exits, so launcher_pid.json's pid can be
  stale/dead while the simulation is still actually progressing."""
  import subprocess
  try:
    out = subprocess.run(["ps", "-A", "-o", "command="],
                         capture_output=True, text=True, timeout=3).stdout
  except Exception:
    return False
  return any("reverie.py" in line for line in out.splitlines())


def _live_run_sim_code():
  """sim_code of the run currently being driven by a backend process, or None.

  Prefers the launcher's own bookkeeping (precise: pid + sim_code together).
  Falls back to curr_sim_code.json + "some reverie.py process is alive" for
  runs started outside the launcher, where we only know the last sim_code the
  frontend was pointed at, not which process owns it.
  """
  meta_pid = _safe_load(os.path.join(TEMP_STORAGE, "launcher_pid.json")) or {}
  sim_code = meta_pid.get("sim_code")
  if sim_code and _pid_alive(meta_pid.get("pid")):
    return sim_code

  curr = _safe_load(os.path.join(TEMP_STORAGE, "curr_sim_code.json")) or {}
  sim_code = curr.get("sim_code")
  if sim_code and _any_reverie_process_alive():
    return sim_code
  return None


_NAME_TIMESTAMP_RE = re.compile(r"(\d{8})-(\d{4})")


def _name_embedded_timestamp(name):
  """Real launch time encoded in the run's own name, e.g. the launcher's
  default "Claude_20260629-2230" or a fork's "...-run-20260628-2147" suffix
  (both generated via datetime.now().strftime("%Y%m%d-%H%M") in this same
  UTC-pinned process -- see _run_started_at). This survives filesystem copies
  that filesystem timestamps (birthtime/mtime) don't, which matters because
  this whole storage tree can be cloned/restored as a unit (e.g. by backups
  or environment snapshots), wiping out each directory's individual history."""
  m = _NAME_TIMESTAMP_RE.search(name)
  if not m:
    return None
  try:
    dt = datetime.datetime.strptime(m.group(0), "%Y%m%d-%H%M")
  except ValueError:
    return None
  return dt.replace(tzinfo=datetime.timezone.utc).timestamp()


def _run_started_at(sim_dir, name):
  """Best-effort real-world launch timestamp for a run. Prefers the timestamp
  embedded in the run's own name (see _name_embedded_timestamp); falls back
  to the filesystem creation time (st_birthtime, macOS/BSD) or the
  metadata-change time (st_ctime) as the closest cross-platform proxy for
  runs with no such name (e.g. forked example data)."""
  embedded = _name_embedded_timestamp(name)
  if embedded is not None:
    return embedded
  st = os.stat(sim_dir)
  return getattr(st, "st_birthtime", None) or st.st_ctime


def scan_runs():
  """Return (runs, bases): runs is a list of dicts for non-base simulations,
  bases is a list of base-template names available to fork from."""
  runs = []
  bases = []
  if not os.path.isdir(STORAGE):
    return runs, bases

  live_sim_code = _live_run_sim_code()

  for name in sorted(os.listdir(STORAGE)):
    sim_dir = os.path.join(STORAGE, name)
    if not os.path.isdir(sim_dir) or name.startswith("."):
      continue
    if sim_dir == SIM_LIBRARY:
      continue  # persona profile storage, not a simulation run

    if _is_base(name):
      bases.append(name)
      continue

    meta = _safe_load(os.path.join(sim_dir, "reverie", "meta.json"))
    steps = _count_movement_steps(sim_dir)
    personas = _persona_names(sim_dir)
    sim_time = _sim_time_reached(meta, steps)
    live = (name == live_sim_code)
    started_at = _run_started_at(sim_dir, name)

    # Status heuristic: a run with movement files that stopped before a full
    # day (8640 steps at 10s/step) is "partial"; >= a full day is "complete";
    # no movement files means it never advanced. A run the backend is
    # currently driving is always "running", regardless of step count.
    if live:
      status = "running"
    elif steps == 0:
      status = "empty"
    elif steps >= 8640:
      status = "complete"
    else:
      status = "partial"

    runs.append({
        "name": name,
        "steps": steps,
        "personas": personas,
        "persona_count": len(personas),
        "sim_time": sim_time,
        "fork": (meta or {}).get("fork_sim_code"),
        "status": status,
        "has_replay": steps > 0,
        "live": live,
        "started_at": started_at,
        # Explicit UTC: Django pins this process's TZ to settings.TIME_ZONE
        # ('UTC') via time.tzset(), so naive fromtimestamp() would silently
        # render UTC wall-clock time mislabeled as local.
        "started_at_label": datetime.datetime.fromtimestamp(
                                started_at, tz=datetime.timezone.utc)
                                .strftime("%b %d, %Y, %I:%M %p UTC"),
    })

  # Most-recently-launched runs first.
  runs.sort(key=lambda r: r["started_at"], reverse=True)
  return runs, bases


def _extract_conversations(sim_dir, limit=20):
  """Scan movement files for non-empty chat arrays and return unique convos."""
  move_dir = os.path.join(sim_dir, "movement")
  convos = []
  seen = set()
  if not os.path.isdir(move_dir):
    return convos

  files = sorted(
      (f for f in os.listdir(move_dir) if f.endswith(".json")),
      key=lambda f: int(f[:-5]) if f[:-5].isdigit() else 0)

  for fname in files:
    data = _safe_load(os.path.join(move_dir, fname))
    if not data:
      continue
    curr_time = data.get("meta", {}).get("curr_time")
    for pname, pdata in data.get("persona", {}).items():
      chat = pdata.get("chat")
      if not chat:
        continue
      # De-duplicate: the same conversation is stored on both participants and
      # across several consecutive steps. Key on the first line text.
      key = chat[0][1] if chat and len(chat[0]) > 1 else str(chat)
      if key in seen:
        continue
      seen.add(key)
      convos.append({
          "time": curr_time,
          "lines": [{"speaker": ln[0], "text": ln[1]} for ln in chat
                    if len(ln) >= 2],
      })
      if len(convos) >= limit:
        return convos
  return convos


def _memory_summary(sim_dir, persona):
  nodes = _safe_load(os.path.join(
      sim_dir, "personas", persona, "bootstrap_memory",
      "associative_memory", "nodes.json"))
  counts = {"event": 0, "thought": 0, "chat": 0, "total": 0}
  if not nodes:
    return counts
  for n in nodes.values():
    t = n.get("type")
    if t in counts:
      counts[t] += 1
    counts["total"] += 1
  return counts


def _schedule_summary(sim_dir, persona):
  scratch = _safe_load(os.path.join(
      sim_dir, "personas", persona, "bootstrap_memory", "scratch.json"))
  if not scratch:
    return None
  return {
      "curr_time": scratch.get("curr_time"),
      "daily_plan": scratch.get("daily_req") or scratch.get("daily_plan_req"),
      "hourly": scratch.get("f_daily_schedule_hourly_org"),
      "act_description": scratch.get("act_description"),
      "act_address": scratch.get("act_address"),
  }


def safe_log_name(sim_code):
  """Filesystem-safe per-run log filename."""
  safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in sim_code)
  return os.path.join(TEMP_STORAGE, f"launcher_run_{safe}.log")


def _tail(path, max_lines=60, max_bytes=16000):
  if not os.path.exists(path):
    return ""
  try:
    with open(path, "rb") as f:
      f.seek(0, os.SEEK_END)
      size = f.tell()
      f.seek(max(0, size - max_bytes))
      data = f.read().decode("utf-8", errors="replace")
  except Exception:
    return ""
  lines = data.splitlines()[-max_lines:]
  return "\n".join(_collapse_repeats(lines))


def _collapse_repeats(lines):
  """Collapse runs of 3+ consecutive identical lines into one + a (xN) tag,
  so repeated debug spam doesn't drown out the rest of the tail."""
  out = []
  i = 0
  while i < len(lines):
    j = i + 1
    while j < len(lines) and lines[j] == lines[i]:
      j += 1
    count = j - i
    if count >= 3:
      out.append(f"{lines[i]}  (×{count})")
    else:
      out.extend(lines[i:j])
    i = j
  return out


def _pid_alive(pid):
  if not pid:
    return False
  try:
    pid = int(pid)
  except (TypeError, ValueError):
    return False
  # The backend is a child of this Django process; if it has exited it becomes
  # a zombie that os.kill(pid, 0) still reports as alive. Reap it first so a
  # finished/stopped run is correctly detected as dead.
  try:
    wpid, _ = os.waitpid(pid, os.WNOHANG)
    if wpid == pid:
      return False
  except ChildProcessError:
    pass  # not our child (e.g. worker was reloaded) -- fall through to kill(0)
  except Exception:
    pass
  try:
    os.kill(pid, 0)
    return True
  except Exception:
    return False


def live_run_status(sim_code):
  """Realtime status for the run console: progress, persona activity, log tail,
  and whether the backend process is still alive."""
  sim_dir = os.path.join(STORAGE, sim_code)
  steps = _count_movement_steps(sim_dir)

  # Latest movement frame -> per-persona current activity.
  personas = []
  sim_time = None
  move_dir = os.path.join(sim_dir, "movement")
  if os.path.isdir(move_dir):
    nums = [int(f[:-5]) for f in os.listdir(move_dir)
            if f.endswith(".json") and f[:-5].isdigit()]
    if nums:
      latest = _safe_load(os.path.join(move_dir, f"{max(nums)}.json"))
      if latest:
        sim_time = latest.get("meta", {}).get("curr_time")
        for name, p in latest.get("persona", {}).items():
          desc = p.get("description", "")
          personas.append({
              "name": name,
              "emoji": p.get("pronunciatio", ""),
              "activity": desc.split(" @ ")[0] if " @ " in desc else desc,
              "location": desc.split(" @ ")[-1] if " @ " in desc else "",
              "chatting": bool(p.get("chat")),
          })

  # Process liveness + launch target from the pid file the launcher wrote.
  pid = None
  target_steps = None
  stop_requested = False
  started_at = None
  meta_pid = _safe_load(os.path.join(TEMP_STORAGE, "launcher_pid.json")) or {}
  if meta_pid.get("sim_code") == sim_code:
    pid = meta_pid.get("pid")
    target_steps = meta_pid.get("steps")
    stop_requested = bool(meta_pid.get("stop_requested"))
    started_at = meta_pid.get("started_at")
  alive = _pid_alive(pid)

  log_tail = _tail(safe_log_name(sim_code))
  crashed = "Traceback (most recent call last)" in log_tail

  if alive and stop_requested:
    state = "stopping"
  elif alive:
    state = "running"
  elif stop_requested:
    state = "stopped"
  elif crashed:
    state = "crashed"
  elif steps > 0:
    state = "finished"
  else:
    state = "starting"

  # Sub-phase of "running"/"starting" so the page can describe what the
  # backend is actually doing before the first movement file exists (forking
  # the run directory, then generating persona identities/schedules), rather
  # than just sitting on "Step 0" with no explanation.
  movement0_exists = os.path.exists(os.path.join(sim_dir, "movement", "0.json"))
  if state in ("starting", "running") and not movement0_exists:
    phase = "forking" if not os.path.isdir(sim_dir) else "initializing"
  else:
    phase = "stepping"

  elapsed = (time.time() - started_at) if started_at else None
  eta_seconds = None
  if alive and elapsed and target_steps and 0 < steps < target_steps:
    rate = steps / elapsed
    if rate > 0:
      eta_seconds = (target_steps - steps) / rate

  return {
      "sim_code": sim_code,
      "steps": steps,
      "target_steps": target_steps,
      "sim_time": sim_time,
      "personas": personas,
      "log_tail": log_tail,
      "alive": alive,
      "state": state,
      "phase": phase,
      "elapsed_seconds": elapsed,
      "eta_seconds": eta_seconds,
  }


def run_review_data(sim_code):
  """Full review payload for a single run."""
  sim_dir = os.path.join(STORAGE, sim_code)
  if not os.path.isdir(sim_dir):
    return None

  meta = _safe_load(os.path.join(sim_dir, "reverie", "meta.json"))
  steps = _count_movement_steps(sim_dir)
  personas = _persona_names(sim_dir)
  convos = _extract_conversations(sim_dir)

  persona_data = []
  for p in personas:
    persona_data.append({
        "name": p,
        "underscore": p.replace(" ", "_"),
        "memory": _memory_summary(sim_dir, p),
        "schedule": _schedule_summary(sim_dir, p),
    })

  return {
      "name": sim_code,
      "meta": meta or {},
      "steps": steps,
      "sim_time": _sim_time_reached(meta, steps),
      "personas": persona_data,
      "conversations": convos,
      "conversation_count": len(convos),
  }

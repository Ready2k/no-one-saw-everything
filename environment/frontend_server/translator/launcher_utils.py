"""
Launcher utilities: scan the storage folder for simulation runs and extract
review data (metadata, progress, conversations, memory counts).

Used by the graphical launcher / run-browser views. All paths are relative to
the frontend_server working directory, matching the rest of translator/views.py.
"""
import os
import json
import datetime

STORAGE = "storage"
TEMP_STORAGE = "temp_storage"

# Forks the launcher offers as "base" templates to start a new run from.
# Anything matching these prefixes is treated as a reusable base, not a run.
BASE_PREFIXES = ("base_the_ville",)


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


def scan_runs():
  """Return (runs, bases): runs is a list of dicts for non-base simulations,
  bases is a list of base-template names available to fork from."""
  runs = []
  bases = []
  if not os.path.isdir(STORAGE):
    return runs, bases

  for name in sorted(os.listdir(STORAGE)):
    sim_dir = os.path.join(STORAGE, name)
    if not os.path.isdir(sim_dir) or name.startswith("."):
      continue

    if _is_base(name):
      bases.append(name)
      continue

    meta = _safe_load(os.path.join(sim_dir, "reverie", "meta.json"))
    steps = _count_movement_steps(sim_dir)
    personas = _persona_names(sim_dir)
    sim_time = _sim_time_reached(meta, steps)

    # Status heuristic: a run with movement files that stopped before a full
    # day (8640 steps at 10s/step) is "partial"; >= a full day is "complete";
    # no movement files means it never advanced.
    if steps == 0:
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
    })

  # Most-recently-modified runs first (mtime of the run directory).
  runs.sort(key=lambda r: os.path.getmtime(os.path.join(STORAGE, r["name"])),
            reverse=True)
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
  lines = data.splitlines()
  return "\n".join(lines[-max_lines:])


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
  meta_pid = _safe_load(os.path.join(TEMP_STORAGE, "launcher_pid.json")) or {}
  if meta_pid.get("sim_code") == sim_code:
    pid = meta_pid.get("pid")
    target_steps = meta_pid.get("steps")
    stop_requested = bool(meta_pid.get("stop_requested"))
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

  return {
      "sim_code": sim_code,
      "steps": steps,
      "target_steps": target_steps,
      "sim_time": sim_time,
      "personas": personas,
      "log_tail": log_tail,
      "alive": alive,
      "state": state,
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

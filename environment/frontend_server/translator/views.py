"""
Author: Joon Sung Park (joonspk@stanford.edu)
File: views.py
"""
import os
import string
import random
import json
import csv
from os import listdir
import os

import datetime
from django.shortcuts import render, redirect, HttpResponseRedirect
from django.http import HttpResponse, JsonResponse
from global_methods import *

from django.templatetags.static import static
from .models import *

def landing(request): 
  context = {}
  template = "landing/landing.html"
  return render(request, template, context)


def demo(request, sim_code, step, play_speed="2"): 
  move_file = f"compressed_storage/{sim_code}/master_movement.json"
  meta_file = f"compressed_storage/{sim_code}/meta.json"
  step = int(step)
  play_speed_opt = {"1": 1, "2": 2, "3": 4,
                    "4": 8, "5": 16, "6": 32}
  if play_speed not in play_speed_opt: play_speed = 2
  else: play_speed = play_speed_opt[play_speed]

  # Loading the basic meta information about the simulation.
  meta = dict() 
  with open (meta_file) as json_file: 
    meta = json.load(json_file)

  sec_per_step = meta["sec_per_step"]
  start_datetime = datetime.datetime.strptime(meta["start_date"] + " 00:00:00", 
                                              '%B %d, %Y %H:%M:%S')
  for i in range(step): 
    start_datetime += datetime.timedelta(seconds=sec_per_step)
  start_datetime = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")

  # Loading the movement file
  raw_all_movement = dict()
  with open(move_file) as json_file: 
    raw_all_movement = json.load(json_file)
 
  # Loading all names of the personas
  persona_names = dict()
  persona_names = []
  persona_names_set = set()
  for p in list(raw_all_movement["0"].keys()): 
    persona_names += [{"original": p, 
                       "underscore": p.replace(" ", "_"), 
                       "initial": p[0] + p.split(" ")[-1][0]}]
    persona_names_set.add(p)

  # <all_movement> is the main movement variable that we are passing to the 
  # frontend. Whereas we use ajax scheme to communicate steps to the frontend
  # during the simulation stage, for this demo, we send all movement 
  # information in one step. 
  all_movement = dict()

  # Preparing the initial step. 
  # <init_prep> sets the locations and descriptions of all agents at the
  # beginning of the demo determined by <step>. 
  init_prep = dict() 
  for int_key in range(step+1): 
    key = str(int_key)
    val = raw_all_movement[key]
    for p in persona_names_set: 
      if p in val: 
        init_prep[p] = val[p]
  persona_init_pos = dict()
  for p in persona_names_set: 
    persona_init_pos[p.replace(" ","_")] = init_prep[p]["movement"]
  all_movement[step] = init_prep

  # Finish loading <all_movement>
  for int_key in range(step+1, len(raw_all_movement.keys())): 
    all_movement[int_key] = raw_all_movement[str(int_key)]

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": json.dumps(persona_init_pos), 
             "all_movement": json.dumps(all_movement), 
             "start_datetime": start_datetime,
             "sec_per_step": sec_per_step,
             "play_speed": play_speed,
             "mode": "demo"}
  template = "demo/demo.html"

  return render(request, template, context)


def UIST_Demo(request): 
  return demo(request, "March20_the_ville_n25_UIST_RUN-step-1-141", 2160, play_speed="3")


def home(request):
  f_curr_sim_code = "temp_storage/curr_sim_code.json"
  f_curr_step = "temp_storage/curr_step.json"

  if not check_if_file_exists(f_curr_step): 
    context = {}
    template = "home/error_start_backend.html"
    return render(request, template, context)

  with open(f_curr_sim_code) as json_file:
    sim_code = json.load(json_file)["sim_code"]

  with open(f_curr_step) as json_file:
    step = json.load(json_file)["step"]

  # Do not delete curr_step.json — keeping it means page refreshes continue
  # to show the current sim state rather than the "start backend" error.

  persona_names = []
  persona_names_set = set()
  for i in find_filenames(f"storage/{sim_code}/personas", ""): 
    x = i.split("/")[-1].strip()
    if x[0] != ".": 
      persona_names += [[x, x.replace(" ", "_")]]
      persona_names_set.add(x)

  persona_init_pos = []
  file_count = []
  for i in find_filenames(f"storage/{sim_code}/environment", ".json"):
    x = i.split("/")[-1].strip()
    if x[0] != ".": 
      file_count += [int(x.split(".")[0])]
  curr_json = f'storage/{sim_code}/environment/{str(max(file_count))}.json'
  with open(curr_json) as json_file:  
    persona_init_pos_dict = json.load(json_file)
    for key, val in persona_init_pos_dict.items(): 
      if key in persona_names_set: 
        persona_init_pos += [[key, val["x"], val["y"]]]

  context = {"sim_code": sim_code,
             "step": step, 
             "persona_names": persona_names,
             "persona_init_pos": persona_init_pos,
             "mode": "simulate"}
  template = "home/home.html"
  return render(request, template, context)


def _replay_meta(sim_code):
  """Reads storage/{sim_code}/reverie/meta.json and returns (start_datetime,
  sec_per_step) -- start_datetime is a datetime at the run's day-start
  (00:00:00), matching the same convention demo() uses for master_movement
  playback. Used to convert step <-> clock time without scanning every
  movement file."""
  meta_file = f"storage/{sim_code}/reverie/meta.json"
  with open(meta_file) as json_file:
    meta = json.load(json_file)
  start_datetime = datetime.datetime.strptime(
    meta["start_date"] + " 00:00:00", '%B %d, %Y %H:%M:%S')
  return start_datetime, meta["sec_per_step"]


def _replay_max_step(sim_code):
  """Highest step number with a movement/{step}.json file on disk -- bounds
  the replay scrubber. Grows over time for a still-running sim."""
  step_nums = []
  for i in find_filenames(f"storage/{sim_code}/movement", ".json"):
    x = i.split("/")[-1].strip()
    if x[0] != ".":
      step_nums += [int(x.split(".")[0])]
  return max(step_nums) if step_nums else 0


def replay(request, sim_code, step):
  sim_code = sim_code
  step = int(step)

  persona_names = []
  persona_names_set = set()
  for i in find_filenames(f"storage/{sim_code}/personas", ""):
    x = i.split("/")[-1].strip()
    if x[0] != ".":
      persona_names += [[x, x.replace(" ", "_")]]
      persona_names_set.add(x)

  # Spawn personas at the position recorded for the requested <step>, not
  # whatever the latest/current environment file happens to be -- otherwise
  # sprites spawn at the run's final position and visibly jump once replay
  # starts walking from an earlier step.
  env_json = f'storage/{sim_code}/environment/{step}.json'
  if not check_if_file_exists(env_json):
    env_json = f'storage/{sim_code}/environment/0.json'
  persona_init_pos = []
  with open(env_json) as json_file:
    persona_init_pos_dict = json.load(json_file)
    for key, val in persona_init_pos_dict.items():
      if key in persona_names_set:
        persona_init_pos += [[key, val["x"], val["y"]]]

  start_datetime, sec_per_step = _replay_meta(sim_code)
  max_step = _replay_max_step(sim_code)

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": persona_init_pos,
             "mode": "replay",
             "start_datetime": start_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
             "sec_per_step": sec_per_step,
             "max_step": max_step}
  template = "home/home.html"
  return render(request, template, context)


def replay_movement(request, sim_code, step):
  """Read-only lookup of a single recorded step's movement data, for the
  playback scrubber/seek controls. Deliberately separate from
  update_environment(), which is part of the live backend handshake and
  expects a matching environment/{step}.json write beforehand -- this just
  reads whatever has already been recorded, with no side effects."""
  step = int(step)
  move_file = f"storage/{sim_code}/movement/{step}.json"
  if not check_if_file_exists(move_file):
    return JsonResponse({"found": False})
  with open(move_file) as json_file:
    content = json_file.read()
  if not content.strip():
    return JsonResponse({"found": False})
  data = json.loads(content)
  data["found"] = True
  return JsonResponse(data)


def replay_bounds(request, sim_code):
  """Read-only {max_step, start_datetime, sec_per_step} for the playback
  controls -- polled occasionally so the scrubber's upper bound can grow
  while a still-running sim is being watched."""
  start_datetime, sec_per_step = _replay_meta(sim_code)
  return JsonResponse({
    "max_step": _replay_max_step(sim_code),
    "start_datetime": start_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
    "sec_per_step": sec_per_step,
  })


def replay_persona_state(request, sim_code, step, persona_name): 
  sim_code = sim_code
  step = int(step)

  persona_name_underscore = persona_name
  persona_name = " ".join(persona_name.split("_"))
  memory = f"storage/{sim_code}/personas/{persona_name}/bootstrap_memory"
  if not os.path.exists(memory): 
    memory = f"compressed_storage/{sim_code}/personas/{persona_name}/bootstrap_memory"

  with open(memory + "/scratch.json") as json_file:  
    scratch = json.load(json_file)

  with open(memory + "/spatial_memory.json") as json_file:  
    spatial = json.load(json_file)

  with open(memory + "/associative_memory/nodes.json") as json_file:  
    associative = json.load(json_file)

  a_mem_event = []
  a_mem_chat = []
  a_mem_thought = []

  for count in range(len(associative.keys()), 0, -1): 
    node_id = f"node_{str(count)}"
    node_details = associative[node_id]

    if node_details["type"] == "event":
      a_mem_event += [node_details]

    elif node_details["type"] == "chat":
      a_mem_chat += [node_details]

    elif node_details["type"] == "thought":
      a_mem_thought += [node_details]
  
  context = {"sim_code": sim_code,
             "step": step,
             "persona_name": persona_name, 
             "persona_name_underscore": persona_name_underscore, 
             "scratch": scratch,
             "spatial": spatial,
             "a_mem_event": a_mem_event,
             "a_mem_chat": a_mem_chat,
             "a_mem_thought": a_mem_thought}
  template = "persona_state/persona_state.html"
  return render(request, template, context)


def persona_current_state(request, sim_code, persona_name):
  """
  <BACKEND to FRONTEND> Lightweight JSON snapshot of a single persona's
  planning context, used to populate the click-to-inspect popout in the
  simulation view. Returns what the agent is doing now, what's scheduled next,
  the high-level daily plan, and the most recent thoughts.
  """
  persona_name = " ".join(persona_name.split("_"))
  memory = f"storage/{sim_code}/personas/{persona_name}/bootstrap_memory"
  if not os.path.exists(memory):
    memory = f"compressed_storage/{sim_code}/personas/{persona_name}/bootstrap_memory"
  if not os.path.exists(memory):
    return JsonResponse({"error": f"No memory found for {persona_name}"}, status=404)

  with open(memory + "/scratch.json") as json_file:
    scratch = json.load(json_file)

  # Work out the current and next decomposed activity from the fine-grained
  # daily schedule, using how many minutes into the day curr_time is.
  now_task, next_task = None, None
  try:
    curr_dt = datetime.datetime.strptime(scratch["curr_time"], "%B %d, %Y, %H:%M:%S")
    minutes_into_day = curr_dt.hour * 60 + curr_dt.minute
    elapsed = 0
    schedule = scratch.get("f_daily_schedule", []) or []
    for i, (task, dur) in enumerate(schedule):
      elapsed += dur
      if minutes_into_day < elapsed:
        now_task = task
        if i + 1 < len(schedule):
          next_task = schedule[i + 1][0]
        break
  except (ValueError, KeyError, TypeError):
    pass

  # Pull the most recent thoughts from associative memory (most useful "key
  # points" of what the agent has been reflecting on).
  thoughts = []
  nodes_path = memory + "/associative_memory/nodes.json"
  if os.path.exists(nodes_path):
    with open(nodes_path) as json_file:
      associative = json.load(json_file)
    for count in range(len(associative.keys()), 0, -1):
      node = associative.get(f"node_{count}")
      if node and node.get("type") == "thought":
        desc = (node.get("description") or "").strip()
        # Skip empty / degenerate thoughts (small local models sometimes emit
        # placeholders like "this is blank").
        if desc and desc.lower() not in ("this is blank", "n/a", "none"):
          thoughts.append({"created": node.get("created"), "description": desc})
      if len(thoughts) >= 5:
        break

  # Current conversation, if any.
  chat = scratch.get("chat")

  return JsonResponse({
    "name": scratch.get("name", persona_name),
    "pronunciatio": scratch.get("act_pronunciatio", ""),
    "curr_time": scratch.get("curr_time", ""),
    "doing_now": scratch.get("act_description", ""),
    "location": scratch.get("act_address", "").split(":")[-1],
    "now_task": now_task,
    "next_task": next_task,
    "currently": scratch.get("currently", ""),
    "daily_plan": scratch.get("daily_req", []) or [],
    "thoughts": thoughts,
    "chat": chat,
  })


def path_tester(request):
  context = {}
  template = "path_tester/path_tester.html"
  return render(request, template, context)


def save_home_step(request):
  """
  <FRONTEND to FRONTEND>
  Persist the live simulation step the browser is currently showing into
  curr_step.json. The backend only writes curr_step.json once (at startup), so
  without this the home view always reloads at the start step. We call this
  right before navigating to a persona's State Details page so that returning
  to the simulation resumes the clock at the moment the user clicked, rather
  than restarting from 00:00.

  ARGS:
    request: Django request (JSON body with an integer "step")
  RETURNS:
    HttpResponse: string confirmation message.
  """
  data = json.loads(request.body)
  step = int(data["step"])
  with open("temp_storage/curr_step.json", "w") as outfile:
    outfile.write(json.dumps({"step": step}, indent=2))
  return HttpResponse("received")


def process_environment(request):
  """
  <FRONTEND to BACKEND>
  This sends the frontend visual world information to the backend server. 
  It does this by writing the current environment representation to 
  "storage/environment.json" file. 

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse: string confirmation message. 
  """
  # f_curr_sim_code = "temp_storage/curr_sim_code.json"
  # with open(f_curr_sim_code) as json_file:  
  #   sim_code = json.load(json_file)["sim_code"]

  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]
  environment = data["environment"]

  with open(f"storage/{sim_code}/environment/{step}.json", "w") as outfile:
    outfile.write(json.dumps(environment, indent=2))

  return HttpResponse("received")


def update_environment(request): 
  """
  <BACKEND to FRONTEND> 
  This sends the backend computation of the persona behavior to the frontend
  visual server. 
  It does this by reading the new movement information from 
  "storage/movement.json" file.

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse
  """
  # f_curr_sim_code = "temp_storage/curr_sim_code.json"
  # with open(f_curr_sim_code) as json_file:  
  #   sim_code = json.load(json_file)["sim_code"]

  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]

  response_data = {"<step>": -1}
  if (check_if_file_exists(f"storage/{sim_code}/movement/{step}.json")):
    try:
      with open(f"storage/{sim_code}/movement/{step}.json") as json_file:
        content = json_file.read()
      if content.strip():
        response_data = json.loads(content)
        response_data["<step>"] = step
    except (json.JSONDecodeError, OSError):
      pass  # file still being written — return {"<step>": -1} so the map retries

  return JsonResponse(response_data)


def path_tester_update(request):
  """
  Processing the path and saving it to path_tester_env.json temp storage for
  conducting the path tester.

  ARGS:
    request: Django request
  RETURNS:
    HttpResponse: string confirmation message.
  """
  data = json.loads(request.body)
  camera = data["camera"]

  with open(f"temp_storage/path_tester_env.json", "w") as outfile:
    outfile.write(json.dumps(camera, indent=2))

  return HttpResponse("received")


# ============================================================================
# Graphical launcher / run browser
# ============================================================================
import subprocess
import sys
import signal
import time
from .launcher_utils import (scan_runs, run_review_data, live_run_status,
                             safe_log_name, prefork_directory, library_get,
                             _live_run_sim_code)

# Profiles offered in the launcher; value is the PROMPT_PROFILE env var.
LAUNCHER_PROFILES = [
    {"value": "chat-small", "label": "chat-small", "hint": "local small model (Gemma 4B)"},
    {"value": "chat-large", "label": "chat-large", "hint": "local large model (Qwen 14B)"},
    {"value": "gpt",        "label": "gpt",        "hint": "OpenAI GPT-3.5/4"},
    {"value": "cloud",      "label": "cloud",      "hint": "cloud API"},
]


def launcher(request):
  """Graphical replacement for start_simulation.sh: configure a new run and
  browse / review previous runs."""
  runs, bases = scan_runs()
  default_name = "Claude_" + datetime.datetime.now().strftime("%Y%m%d-%H%M")

  current_profile = "chat-large"
  prof = None
  try:
    with open("temp_storage/llm_profile.json") as f:
      prof = json.load(f).get("profile")
  except Exception:
    prof = None
  if prof:
    current_profile = prof

  context = {
      "runs": runs,
      "bases": bases,
      "profiles": LAUNCHER_PROFILES,
      "current_profile": current_profile,
      "default_name": default_name,
      "run_count": len(runs),
  }
  return render(request, "launcher/launcher.html", context)


def run_review(request, sim_code):
  """Detailed data-review page for a single run."""
  data = run_review_data(sim_code)
  if data is None:
    return HttpResponse(f"No such run: {sim_code}", status=404)
  return render(request, "launcher/run_review.html", {"run": data})


def open_run_map(request, sim_code):
  """Point the frontend at a stored run and open its map.

  A currently-live run goes to the live "simulate" view (home), same as
  before. Any other run -- finished, or just not the one actively being
  driven by a backend process -- goes to the read-only playback view
  (replay) instead, so its "Open map"/"Open map replay" links actually reach
  the scrubber/speed/time-jump controls rather than the live view stalling
  on a backend that isn't writing new steps for it.
  """
  if not os.path.isdir(f"storage/{sim_code}"):
    return HttpResponse(f"No such run: {sim_code}", status=404)

  if sim_code == _live_run_sim_code():
    os.makedirs("temp_storage", exist_ok=True)
    with open("temp_storage/curr_sim_code.json", "w") as f:
      f.write(json.dumps({"sim_code": sim_code}, indent=2))
    with open("temp_storage/curr_step.json", "w") as f:
      f.write(json.dumps({"step": 0}, indent=2))
    return redirect("home")

  return redirect("replay", sim_code=sim_code, step=0)


def launch_simulation(request):
  """Spawn the backend reverie server for a new run, driven non-interactively.

  Feeds: <fork> <name> run <steps> fin  -- so it runs <steps> then saves and
  exits cleanly (no EOF crash). The browser is redirected to the live map.
  """
  if request.method != "POST":
    return redirect("launcher")

  fork = request.POST.get("fork", "").strip()
  name = request.POST.get("name", "").strip()
  profile = request.POST.get("profile", "chat-large").strip()
  try:
    steps = int(request.POST.get("steps", "8640"))
  except ValueError:
    steps = 8640

  # Sim-level overrides: start_date (HTML date → "Month DD, YYYY") and sec_per_step.
  overrides = {}
  raw_date = request.POST.get("start_date", "").strip()
  if raw_date:
    try:
      overrides["start_date"] = datetime.datetime.strptime(
          raw_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
      pass
  raw_sps = request.POST.get("sec_per_step", "").strip()
  if raw_sps:
    try:
      overrides["sec_per_step"] = int(raw_sps)
    except ValueError:
      pass

  if not fork or not name:
    return HttpResponse("fork and name are required", status=400)

  # Reject names that would collide with an existing run.
  if os.path.isdir(f"storage/{name}"):
    return HttpResponse(f"A run named '{name}' already exists.", status=400)

  # ── Persona roster ────────────────────────────────────────────────────────
  # keep_personas: JSON list of existing persona names to keep (None = keep all)
  # add_personas:  JSON list of library slugs to inject as new personas
  keep_personas_raw  = request.POST.get("keep_personas", "").strip()
  add_personas_raw   = request.POST.get("add_personas",  "").strip()
  try:
    keep_personas = json.loads(keep_personas_raw) if keep_personas_raw else None
  except (ValueError, TypeError):
    keep_personas = None
  try:
    add_slugs = json.loads(add_personas_raw) if add_personas_raw else []
  except (ValueError, TypeError):
    add_slugs = []
  add_profiles = [p for s in add_slugs for p in [library_get(s)] if p]

  # If the roster differs from the fork's default, pre-build the target
  # directory here and pass fork=name so reverie.py does a self-fork no-op.
  effective_fork = fork
  if keep_personas is not None or add_profiles:
    try:
      prefork_directory(fork, name,
                        keep_personas=keep_personas,
                        add_profiles=add_profiles)
      effective_fork = name  # copyanything self-fork skips the copy
    except Exception as e:
      return HttpResponse(f"Pre-fork failed: {e}", status=500)

  # Paths relative to the frontend_server cwd.
  backend_dir = os.path.abspath("../../reverie/backend_server")
  venv_python = os.path.abspath("../../.venv/bin/python")
  python_bin = venv_python if os.path.exists(venv_python) else sys.executable

  # Drive the interactive backend via a stdin script.
  os.makedirs("temp_storage", exist_ok=True)
  input_path = os.path.abspath("temp_storage/launcher_input.txt")
  log_path = os.path.abspath(safe_log_name(name))
  with open(input_path, "w") as f:
    f.write(f"{effective_fork}\n{name}\nrun {steps}\nfin\n")
  with open("temp_storage/launch_overrides.json", "w") as f:
    json.dump(overrides, f)

  env = dict(os.environ)
  env["PROMPT_PROFILE"] = profile
  env["PYTHONPATH"] = backend_dir

  logf = open(log_path, "w")
  with open(input_path) as stdin_f:
    proc = subprocess.Popen(
        [python_bin, "reverie.py"],
        cwd=backend_dir,
        stdin=stdin_f,
        stdout=logf,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )

  # Launch the autonomous environment stepper alongside the backend.
  # It replaces the browser map's role of writing environment/{step}.json
  # for each step, so the simulation advances without a browser tab open.
  stepper_log = open(os.path.join("temp_storage", f"stepper_{safe_log_name(name).split('/')[-1]}"), "w")
  stepper_proc = subprocess.Popen(
      [python_bin, "run_stepper.py", name, str(steps), str(proc.pid)],
      cwd=backend_dir,
      stdout=stepper_log,
      stderr=subprocess.STDOUT,
      env=env,
      start_new_session=True,
  )

  # Point the frontend at the new run, record the chosen profile, and remember
  # the backend pid so the console can report whether it is still alive.
  with open("temp_storage/curr_sim_code.json", "w") as f:
    f.write(json.dumps({"sim_code": name}, indent=2))
  with open("temp_storage/curr_step.json", "w") as f:
    f.write(json.dumps({"step": 0}, indent=2))
  with open("temp_storage/llm_profile.json", "w") as f:
    f.write(json.dumps({"profile": profile}))
  with open("temp_storage/launcher_pid.json", "w") as f:
    f.write(json.dumps({"sim_code": name, "pid": proc.pid,
                        "steps": steps, "profile": profile,
                        "started_at": time.time()}))

  return redirect("run_console", sim_code=name)


def delete_run(request, sim_code):
  """Delete a stored run directory. Only non-base runs may be deleted."""
  if request.method != "POST":
    return JsonResponse({"error": "POST only"}, status=405)

  # Safety: never delete base templates.
  from .launcher_utils import _is_base
  if _is_base(sim_code):
    return JsonResponse({"error": "Cannot delete base templates"}, status=400)

  sim_dir = os.path.join("storage", sim_code)
  if not os.path.isdir(sim_dir):
    return JsonResponse({"error": "Run not found"}, status=404)

  import shutil
  try:
    shutil.rmtree(sim_dir)
  except Exception as e:
    return JsonResponse({"error": str(e)}, status=500)

  return JsonResponse({"ok": True})


def run_console(request, sim_code):
  """Live console page shown right after launch."""
  return render(request, "launcher/console.html", {"sim_code": sim_code})


def run_status(request, sim_code):
  """JSON polled by the console page for realtime progress + log tail."""
  return JsonResponse(live_run_status(sim_code))


def stop_run(request, sim_code):
  """Gracefully stop a running backend: SIGTERM triggers a save-and-exit in the
  backend, so all movement files, logs, and saved state are preserved. The
  console keeps showing how far the run got."""
  pid_path = "temp_storage/launcher_pid.json"
  info = {}
  try:
    with open(pid_path) as f:
      info = json.load(f)
  except Exception:
    info = {}

  if info.get("sim_code") != sim_code or not info.get("pid"):
    return JsonResponse({"ok": False, "reason": "no running process for this run"})

  pid = info["pid"]
  killed = False
  try:
    # The backend was launched with start_new_session=True, so it leads its own
    # process group; signal the whole group to catch any child processes too.
    os.killpg(os.getpgid(pid), signal.SIGTERM)
    killed = True
  except ProcessLookupError:
    killed = False  # already exited
  except Exception:
    try:
      os.kill(pid, signal.SIGTERM)
      killed = True
    except Exception:
      killed = False

  info["stop_requested"] = True
  with open(pid_path, "w") as f:
    f.write(json.dumps(info))

  if request.method == "POST" or request.headers.get(
      "x-requested-with") == "XMLHttpRequest":
    return JsonResponse({"ok": True, "killed": killed})
  return redirect("run_console", sim_code=sim_code)


# Fields from scratch.json that the user can view and edit in the launcher.
PERSONA_EDITABLE_FIELDS = [
    ("name",          "Full name"),
    ("age",           "Age"),
    ("innate",        "Innate traits"),
    ("learned",       "Learned background"),
    ("currently",     "Currently"),
    ("lifestyle",     "Lifestyle / sleep"),
    ("living_area",   "Location"),
    ("daily_plan_req","Daily routine"),
]

# Advanced cognitive / memory tuning fields (shown collapsed by default).
PERSONA_COGNITIVE_FIELDS = [
    ("vision_r",              "Vision radius",             "int",   "How far the persona can see (tiles)"),
    ("att_bandwidth",         "Attention bandwidth",       "int",   "Max events noticed per step"),
    ("retention",             "Retention",                 "int",   "Recent events kept in working memory"),
    ("recency_decay",         "Recency decay",             "float", "How fast memory recency fades (0.99 = fast, 0.999 = slow)"),
    ("importance_trigger_max","Reflection threshold",      "int",   "Poignancy points before a reflection fires"),
    ("recency_w",             "Recency weight",            "float", "Weight of recency in memory retrieval scoring"),
    ("relevance_w",           "Relevance weight",          "float", "Weight of relevance in memory retrieval scoring"),
    ("importance_w",          "Importance weight",         "float", "Weight of importance in memory retrieval scoring"),
]


def get_personas(request, sim_code):
  """Return persona scratch data and sim meta for all personas in a sim (JSON)."""
  sim_dir = os.path.join("storage", sim_code)
  if not os.path.isdir(sim_dir):
    return JsonResponse({"error": f"No such sim: {sim_code}"}, status=404)

  # Sim-level meta (start_date, sec_per_step) to pre-populate the launch form.
  meta = {}
  try:
    with open(os.path.join(sim_dir, "reverie", "meta.json")) as f:
      raw = json.load(f)
    if raw.get("start_date"):
      meta["start_date"] = datetime.datetime.strptime(
          raw["start_date"], "%B %d, %Y").strftime("%Y-%m-%d")
    meta["sec_per_step"] = raw.get("sec_per_step", 10)
  except Exception:
    pass

  personas = []
  pdir = os.path.join(sim_dir, "personas")
  for name in sorted(p for p in os.listdir(pdir) if not p.startswith(".")):
    scratch_path = os.path.join(pdir, name, "bootstrap_memory", "scratch.json")
    try:
      with open(scratch_path) as f:
        scratch = json.load(f)
    except Exception:
      scratch = {}
    personas.append({
        "name": name,
        "fields": {k: scratch.get(k, "") for k, _ in PERSONA_EDITABLE_FIELDS},
        "cognitive": {k: scratch.get(k, "") for k, *_ in PERSONA_COGNITIVE_FIELDS},
    })
  return JsonResponse({"personas": personas, "meta": meta})


def _load_location_tree(maze_name):
  """Parse a maze's special_blocks CSVs into {world: {sector: [arena,...]}}.
  Returns (tree, error) — error is set (and tree is {}) if the maze has no
  location data on disk."""
  blocks_dir = os.path.join(
      "static_dirs", "assets", maze_name, "matrix", "special_blocks")
  sector_csv = os.path.join(blocks_dir, "sector_blocks.csv")
  arena_csv = os.path.join(blocks_dir, "arena_blocks.csv")

  tree = {}
  try:
    with open(sector_csv, newline="") as f:
      for row in csv.reader(f):
        if len(row) < 3:
          continue
        world, sector = row[1].strip(), row[2].strip()
        tree.setdefault(world, {}).setdefault(sector, [])
    with open(arena_csv, newline="") as f:
      for row in csv.reader(f):
        if len(row) < 4:
          continue
        world, sector, arena = row[1].strip(), row[2].strip(), row[3].strip()
        arenas = tree.setdefault(world, {}).setdefault(sector, [])
        if arena not in arenas:
          arenas.append(arena)
  except FileNotFoundError:
    return {}, f"No location data for maze '{maze_name}'"

  for sectors in tree.values():
    for arenas in sectors.values():
      arenas.sort()

  return tree, None


def get_locations(request, sim_code):
  """Return the valid spatial hierarchy (world -> sector -> [arena,...]) for
  a sim's map, parsed from its special_blocks CSVs, so the launcher can offer
  a location picker instead of free-text entry."""
  maze_name = "the_ville"
  meta_path = os.path.join("storage", sim_code, "reverie", "meta.json")
  try:
    with open(meta_path) as f:
      maze_name = json.load(f).get("maze_name", maze_name)
  except Exception:
    pass

  tree, error = _load_location_tree(maze_name)
  if error:
    return JsonResponse({"error": error}, status=404)
  return JsonResponse({"tree": tree, "maze_name": maze_name})


def library_locations(request):
  """Return the spatial hierarchy for the default map, for the sim-library
  persona editor (which isn't tied to any particular sim/fork)."""
  maze_name = "the_ville"
  tree, error = _load_location_tree(maze_name)
  if error:
    return JsonResponse({"error": error}, status=404)
  return JsonResponse({"tree": tree, "maze_name": maze_name})


def save_persona(request, sim_code, persona_name):
  """Save edited persona scratch fields (POST, JSON body)."""
  if request.method != "POST":
    return JsonResponse({"error": "POST only"}, status=405)

  sim_dir = os.path.join("storage", sim_code)
  scratch_path = os.path.join(
      sim_dir, "personas", persona_name, "bootstrap_memory", "scratch.json")

  if not os.path.exists(scratch_path):
    return JsonResponse({"error": "persona not found"}, status=404)

  try:
    updates = json.loads(request.body)
  except Exception:
    return JsonResponse({"error": "invalid JSON"}, status=400)

  with open(scratch_path) as f:
    scratch = json.load(f)

  allowed_basic = {k for k, _ in PERSONA_EDITABLE_FIELDS}
  cog_types = {k: typ for k, _, typ, *_ in PERSONA_COGNITIVE_FIELDS}
  allowed = allowed_basic | set(cog_types)

  for key, val in updates.items():
    if key not in allowed:
      continue
    if key in cog_types:
      try:
        scratch[key] = int(val) if cog_types[key] == "int" else float(val)
      except (ValueError, TypeError):
        pass
    elif key == "age":
      try:
        scratch[key] = int(val)
      except (ValueError, TypeError):
        pass
    else:
      scratch[key] = str(val)
    if key == "name" and val:
      parts = str(val).strip().split()
      scratch["first_name"] = parts[0] if parts else ""
      scratch["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""

  with open(scratch_path, "w") as f:
    json.dump(scratch, f, indent=2)

  return JsonResponse({"ok": True})


# ============================================================================
# Sim library (persona template CRUD)
# ============================================================================
from .launcher_utils import (library_list, library_get, library_save,
                             library_delete, _library_slug)

_LIB_ALLOWED_BASIC = {k for k, _ in PERSONA_EDITABLE_FIELDS}
_LIB_COG_TYPES     = {k: typ for k, _, typ, *_ in PERSONA_COGNITIVE_FIELDS}
_LIB_ALLOWED       = _LIB_ALLOWED_BASIC | set(_LIB_COG_TYPES) | {"living_area"}


def _coerce_library_data(data):
  """Validate and coerce types for a library profile payload."""
  clean = {k: v for k, v in data.items() if k in _LIB_ALLOWED}
  # coerce cognitive fields
  for key, typ in _LIB_COG_TYPES.items():
    if key in clean:
      try:
        clean[key] = int(clean[key]) if typ == "int" else float(clean[key])
      except (ValueError, TypeError):
        clean.pop(key, None)
  # coerce age
  if "age" in clean:
    try:
      clean["age"] = int(clean["age"])
    except (ValueError, TypeError):
      clean.pop("age", None)
  # split first/last from full name
  if "name" in clean and clean["name"]:
    parts = str(clean["name"]).strip().split()
    clean["first_name"] = parts[0] if parts else ""
    clean["last_name"]  = " ".join(parts[1:]) if len(parts) > 1 else ""
  return clean


def sim_library_page(request):
  """Sim library page — lists all persona templates."""
  profiles = library_list()
  runs, _ = scan_runs()
  return render(request, "sims/library.html", {"profiles": profiles, "runs": runs})


def sim_library_api(request):
  """JSON list of all library profiles (used by launcher import picker)."""
  return JsonResponse({"profiles": library_list()})


def sim_library_get(request, slug):
  """Return a single library profile as JSON."""
  p = library_get(slug)
  if p is None:
    return JsonResponse({"error": "not found"}, status=404)
  return JsonResponse(p)


def sim_library_save(request, slug=None):
  """Create or update a library profile (POST, JSON body)."""
  if request.method != "POST":
    return JsonResponse({"error": "POST only"}, status=405)
  try:
    data = json.loads(request.body)
  except Exception:
    return JsonResponse({"error": "invalid JSON"}, status=400)

  name = str(data.get("name", "")).strip()
  if not name:
    return JsonResponse({"error": "name is required"}, status=400)

  # derive slug from name if not in URL
  if not slug:
    slug = _library_slug(name)
  if not slug:
    return JsonResponse({"error": "could not derive slug from name"}, status=400)

  clean = _coerce_library_data(data)
  saved = library_save(slug, clean)
  return JsonResponse({"ok": True, "slug": slug, "profile": saved})


def sim_library_import(request, sim_code, persona_name):
  """Import a persona from an existing run's scratch.json into the sim
  library, so it can be reused via "add from library" on future forks."""
  if request.method != "POST":
    return JsonResponse({"error": "POST only"}, status=405)

  scratch_path = os.path.join("storage", sim_code, "personas", persona_name,
                              "bootstrap_memory", "scratch.json")
  try:
    with open(scratch_path) as f:
      scratch = json.load(f)
  except Exception:
    return JsonResponse({"error": "persona not found"}, status=404)

  data = {k: scratch.get(k, "") for k, _ in PERSONA_EDITABLE_FIELDS}
  data.update({k: scratch.get(k, "") for k, *_ in PERSONA_COGNITIVE_FIELDS})

  name = str(data.get("name", "")).strip()
  if not name:
    return JsonResponse({"error": "persona has no name"}, status=400)

  slug = _library_slug(name)
  clean = _coerce_library_data(data)
  saved = library_save(slug, clean)
  return JsonResponse({"ok": True, "slug": slug, "profile": saved})


def sim_library_delete_view(request, slug):
  """Delete a library profile (POST)."""
  if request.method != "POST":
    return JsonResponse({"error": "POST only"}, status=405)
  ok = library_delete(slug)
  return JsonResponse({"ok": ok})








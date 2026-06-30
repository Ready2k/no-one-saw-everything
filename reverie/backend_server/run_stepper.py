"""
Autonomous environment stepper for the generative agents simulation.

The browser map normally drives each simulation step by:
  1. Posting current persona tile positions to /process_environment
  2. Polling /update_environment until the backend has computed the next step
  3. Animating personas, then repeating

This script replicates that loop server-side so the simulation runs
without a browser window open. It reads each completed movement file,
writes the next environment file, then waits for the backend to produce
the following movement file before advancing.

Usage:
  python run_stepper.py <sim_code> <target_steps> [<backend_pid>]

  sim_code      - name of the simulation run directory under frontend_server/storage/
  target_steps  - stop after this many completed movement steps
  backend_pid   - (optional) PID of the backend process; stepper exits if it dies
"""
import json
import os
import sys
import time

POLL_INTERVAL = 1.0   # seconds between checks for next movement file
INIT_TIMEOUT  = 7200  # seconds to wait for movement/0.json before giving up (2h covers slow init)

# Path from backend_server/ to the frontend storage directory.
FS_STORAGE = "../../environment/frontend_server/storage"
MAZE = "the_ville"


def _pid_alive(pid):
    if not pid:
        return True  # no PID given, assume alive
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _read_movement(sim_dir, step):
    path = os.path.join(sim_dir, "movement", f"{step}.json")
    with open(path) as f:
        return json.load(f)


def _write_environment(sim_dir, step, positions):
    path = os.path.join(sim_dir, "environment", f"{step}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(positions, f, indent=2)


def _movement_exists(sim_dir, step):
    return os.path.exists(os.path.join(sim_dir, "movement", f"{step}.json"))


def run(sim_code, target_steps, backend_pid=None):
    sim_dir = os.path.join(FS_STORAGE, sim_code)
    print(f"[stepper] starting for {sim_code}, target={target_steps} steps", flush=True)

    # Wait for backend to finish initialising (writes movement/0.json).
    waited = 0
    while not _movement_exists(sim_dir, 0):
        if not _pid_alive(backend_pid):
            print("[stepper] backend exited before initialising — stopping", flush=True)
            return
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
        if waited >= INIT_TIMEOUT:
            print("[stepper] timed out waiting for movement/0.json — stopping", flush=True)
            return

    print(f"[stepper] initialisation done, starting step loop", flush=True)

    step = 0
    while step < target_steps:
        if not _pid_alive(backend_pid):
            print(f"[stepper] backend exited at step {step} — stopping", flush=True)
            break

        # Read persona positions from the completed movement file.
        try:
            move = _read_movement(sim_dir, step)
        except Exception as e:
            print(f"[stepper] error reading movement/{step}.json: {e}", flush=True)
            time.sleep(POLL_INTERVAL)
            continue

        # Build the environment payload for the next step.
        env = {}
        for name, pdata in move.get("persona", {}).items():
            x, y = pdata["movement"]
            env[name] = {"maze": MAZE, "x": x, "y": y}

        next_step = step + 1
        _write_environment(sim_dir, next_step, env)
        print(f"[stepper] wrote environment/{next_step}.json, waiting for movement/{next_step}.json", flush=True)

        # Wait for backend to produce the next movement file.
        while not _movement_exists(sim_dir, next_step):
            if not _pid_alive(backend_pid):
                print(f"[stepper] backend exited while waiting for step {next_step}", flush=True)
                return
            time.sleep(POLL_INTERVAL)

        step = next_step

    print(f"[stepper] done — {step} steps completed", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: run_stepper.py <sim_code> <target_steps> [<backend_pid>]")
        sys.exit(1)

    sim_code_arg    = sys.argv[1]
    target_steps_arg = int(sys.argv[2])
    backend_pid_arg  = int(sys.argv[3]) if len(sys.argv) > 3 else None

    run(sim_code_arg, target_steps_arg, backend_pid_arg)

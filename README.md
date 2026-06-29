

# Generative Agents: Interactive Simulacra of Human Behavior 

<p align="center" width="100%">
<img src="cover.png" alt="Smallville" style="width: 80%; min-width: 300px; display: block; margin: auto;">
</p>

This repository accompanies our research paper titled "[Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)." It contains our core simulation module for generative agents—computational agents that simulate believable human behaviors—and their game environment. Below, we document the steps for setting up the simulation environment on your local machine and for replaying the simulation as a demo animation.

> **Fork note:** This fork adds local-LLM support, a browser-based graphical launcher, a persona/cognitive editor, and a crash-proofing pass that makes the simulation reliable with small open-source models (Gemma 4B, Qwen 14B, etc.) in addition to the original OpenAI backend.

## What's new in this fork

### Local LLM support
The simulation can now run against any OpenAI-compatible local inference server (LM Studio, llama.cpp, Ollama, etc.) instead of OpenAI. Configure the endpoint URL and model name in `utils.py` (`openai_api_base` and `local_model`) — the rest of the codebase works unchanged.

### Prompt profile system
All 30+ prompt templates are now organised into interchangeable **profiles** under `reverie/backend_server/persona/prompt_template/profiles/`:

| Profile | Target model | Notes |
|---------|-------------|-------|
| `chat-small` | Gemma 4B and other small chat models | Simplified prompts; explicit JSON output instructions |
| `chat-large` | Qwen 14B+ and other capable chat models | Same as `gpt` profile |
| `gpt` | OpenAI GPT-3.5 / GPT-4 | Original v3 prompt style |
| `cloud` | OpenAI / Anthropic / Gemini cloud APIs | Same as `gpt` profile |

The active profile is selected at startup via the launcher menu or the `PROMPT_PROFILE` environment variable.

### Graphical launcher
Navigate to `http://localhost:8000/launcher` to access a browser-based control panel that replaces the command-line startup flow:

- **Fork browser** — lists all existing simulations; click one to pre-fill the launch form
- **Launch form** — set the fork, new simulation name, LLM profile, start date, and seconds-per-step
- **Persona editor** — before launching, view and edit each agent's name, age, personality traits, background, and daily routine directly in the browser
- **Advanced cognitive settings** — per-persona controls for vision radius, attention bandwidth, retention, recency decay, reflection threshold, and the three memory retrieval weights (recency, importance, relevance)
- **Live console** — streams the simulation log in real time with a Stop button; no terminal required
- **Run review** — browse completed runs after the fact

### Autonomous stepper (`run_stepper.py`)
`reverie/backend_server/run_stepper.py` advances the simulation for a fixed number of steps and exits. The graphical launcher spawns it automatically alongside `reverie.py` when you start a run from the browser, so no browser tab needs to stay open. It can also be run manually:

    python run_stepper.py <sim_code> <target_steps>

### Convenience launch scripts
Two shell scripts at the repo root handle the full startup sequence:

- `start_environment.sh` — starts the Django frontend server
- `start_simulation.sh` — interactive CLI menu that lets you pick a profile, fork, and simulation name, then launches `reverie.py` (requires `start_environment.sh` running separately)

### Crash-proofing for local models
Local models produce malformed output far more often than GPT-3.5. A systematic pass fixed 12+ crash vectors:

- `gpt_structure.py` — `safe_generate_response` and `ChatGPT_safe_generate_response` now return the `fail_safe` value (instead of `False`) when retries are exhausted, preventing `TypeError: 'bool' object is not subscriptable` crashes throughout the codebase
- `task_decomp` — fixed three bugs: validate function swallowed parse errors silently; fail_safe had wrong shape (`["asleep"]` instead of `[["asleep", 60]]`); empty output caused `IndexError`
- `scratch.py` `save()` — guarded `None` values on `curr_time` / `act_start_time` that previously caused silent save failures (agent info card stayed blank)
- `reverie.py` — auto-creates the `movement/` directory on fork; auto-saves every 100 steps so the frontend info card stays current
- `action_arena` / `action_sector` prompts — strip echoed `{` prefix that Qwen-style models insert, preventing `KeyError` on spatial tree lookup
- 12 prompt functions — added `return fail_safe, [...]` after exhausted retry paths that previously fell through with no return value

---

## <img src="https://joonsungpark.s3.amazonaws.com:443/static/assets/characters/profile/Isabella_Rodriguez.png" alt="Generative Isabella">   Setting Up the Environment 
To set up your environment, you will need to generate a `utils.py` file and install the required packages.

### Step 1. Generate Utils File
In the `reverie/backend_server` folder (where `reverie.py` is located), create a new file titled `utils.py` and copy and paste the content below:

```python
import os

# OpenAI API key — set to "local" when using a local LLM gateway
openai_api_key  = "<Your OpenAI API key>"   # or "local"
key_owner       = "<Name>"

# LLM profile: gpt | chat-small | chat-large | cloud
# Override at startup with the PROMPT_PROFILE env var or the launcher menu.
PROMPT_PROFILE  = os.environ.get("PROMPT_PROFILE", "gpt")

# Local LLM gateway — only used when running a local model
openai_api_base = "http://127.0.0.1:8080/v1"   # your inference server URL
local_model     = "<your-model-name>"            # model name as your server expects it
local_cert      = ""                             # path to self-signed cert, or ""

maze_assets_loc = "../../environment/frontend_server/static_dirs/assets"
env_matrix      = f"{maze_assets_loc}/the_ville/matrix"
env_visuals     = f"{maze_assets_loc}/the_ville/visuals"

fs_storage      = "../../environment/frontend_server/storage"
fs_temp_storage = "../../environment/frontend_server/temp_storage"

collision_block_id = "32125"

debug = True
```

**For cloud APIs** (OpenAI, Anthropic, Gemini), create a `.env` file at the repo root:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

### Step 2. Install requirements.txt
Install everything listed in the `requirements.txt` file (strongly recommended: use a virtualenv). Python 3.9+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## <img src="https://joonsungpark.s3.amazonaws.com:443/static/assets/characters/profile/Klaus_Mueller.png" alt="Generative Klaus">   Running a Simulation

### Quick start (recommended)

**Option A — Graphical launcher (browser UI)**

Start the environment server, then use the browser to configure and launch runs:

```bash
# Terminal 1 — start the Django frontend server
./start_environment.sh
```

Then open [http://localhost:8000/launcher](http://localhost:8000/launcher) in your browser. From there you can pick a fork, set the LLM profile, edit personas, and start the simulation — all without a second terminal.

**Option B — Interactive CLI launcher**

```bash
# Terminal 1 — start the Django frontend server
./start_environment.sh

# Terminal 2 — CLI menu: picks profile, fork, and sim name, then runs reverie.py
./start_simulation.sh
```

`start_simulation.sh` presents an interactive menu and pipes your choices into `reverie.py`, leaving the "Enter option:" prompt for `run <N>` / `fin` / `exit` commands.

### Manual start
If you prefer the original command-line flow:

#### Step 1. Starting the Environment Server
Navigate to `environment/frontend_server` and run:

    python manage.py runserver

Go to [http://localhost:8000/](http://localhost:8000/) — if you see "Your environment server is up and running," it's working. Keep this terminal open.

#### Step 2. Starting the Simulation Server
In a second terminal, navigate to `reverie/backend_server` and run:

    python reverie.py

When prompted for "Enter the name of the forked simulation", type:

    base_the_ville_isabella_maria_klaus

When prompted for "Enter the name of the new simulation", type any name:

    test-simulation

#### Step 3. Running and Saving the Simulation
Navigate to [http://localhost:8000/simulator_home](http://localhost:8000/simulator_home). To run the simulation, type at the "Enter option" prompt:

    run <step-count>

One game step represents 10 seconds of in-game time. When done, type `fin` to save or `exit` to quit without saving.

#### Step 4. Replaying a Simulation
With the environment server running, navigate to:

    http://localhost:8000/replay/<simulation-name>/<starting-time-step>

For example, to replay a pre-simulated example starting at step 1:  
[http://localhost:8000/replay/July1_the_ville_isabella_maria_klaus-step-3-20/1/](http://localhost:8000/replay/July1_the_ville_isabella_maria_klaus-step-3-20/1/)

#### Step 5. Demoing a Simulation
To view a simulation with correct character sprites, first compress it by running the `compress` function in `reverie/compress_sim_storage.py`, then navigate to:

    http://localhost:8000/demo/<simulation-name>/<starting-time-step>/<simulation-speed>

`<simulation-speed>` ranges from 1 (slowest) to 5 (fastest). Pre-simulated example at medium speed:  
[http://localhost:8000/demo/July1_the_ville_isabella_maria_klaus-step-3-20/1/3/](http://localhost:8000/demo/July1_the_ville_isabella_maria_klaus-step-3-20/1/3/)

### Tips
- Save frequently with `fin` to avoid losing progress if the LLM endpoint hangs or a crash occurs.
- With local models, `sec_per_step=10` (default) takes roughly 1 hour of real time to advance from midnight to 9 AM in-game. Increase `sec_per_step` in the launcher to skip ahead faster.
- Conversation depth is set to 4 turns per exchange (reduced from the original 8) for local-model speed. Increase `range(4)` in `converse.py:agent_chat_v2` for longer conversations.

## <img src="https://joonsungpark.s3.amazonaws.com:443/static/assets/characters/profile/Maria_Lopez.png" alt="Generative Maria">   Simulation Storage Location
All simulations that you save will be located in `environment/frontend_server/storage`, and all compressed demos will be located in `environment/frontend_server/compressed_storage`. 

## <img src="https://joonsungpark.s3.amazonaws.com:443/static/assets/characters/profile/Sam_Moore.png" alt="Generative Sam">   Customization

There are two ways to optionally customize your simulations. 

### Author and Load Agent History
First is to initialize agents with unique history at the start of the simulation. To do this, you would want to 1) start your simulation using one of the base simulations, and 2) author and load agent history. More specifically, here are the steps:

#### Step 1. Starting Up a Base Simulation 
There are two base simulations included in the repository: `base_the_ville_n25` with 25 agents, and `base_the_ville_isabella_maria_klaus` with 3 agents. Load one of the base simulations by following the steps until step 2 above. 

#### Step 2. Loading a History File 
Then, when prompted with "Enter option: ", you should load the agent history by responding with the following command:

    call -- load history the_ville/<history_file_name>.csv
Note that you will need to replace `<history_file_name>` with the name of an existing history file. There are two history files included in the repo as examples: `agent_history_init_n25.csv` for `base_the_ville_n25` and `agent_history_init_n3.csv` for `base_the_ville_isabella_maria_klaus`. These files include semicolon-separated lists of memory records for each of the agents—loading them will insert the memory records into the agents' memory stream.

#### Step 3. Further Customization 
To customize the initialization by authoring your own history file, place your file in the following folder: `environment/frontend_server/static_dirs/assets/the_ville`. The column format for your custom history file will have to match the example history files included. Therefore, we recommend starting the process by copying and pasting the ones that are already in the repository.

### Create New Base Simulations
For a more involved customization, you will need to author your own base simulation files. The most straightforward approach would be to copy and paste an existing base simulation folder, renaming and editing it according to your requirements. This process will be simpler if you decide to keep the agent names unchanged. However, if you wish to change their names or increase the number of agents that the Smallville map can accommodate, you might need to directly edit the map using the [Tiled](https://www.mapeditor.org/) map editor.


## <img src="https://joonsungpark.s3.amazonaws.com:443/static/assets/characters/profile/Eddy_Lin.png" alt="Generative Eddy">   Authors and Citation 

**Authors:** Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein

Please cite our paper if you use the code or data in this repository. 
```
@inproceedings{Park2023GenerativeAgents,  
author = {Park, Joon Sung and O'Brien, Joseph C. and Cai, Carrie J. and Morris, Meredith Ringel and Liang, Percy and Bernstein, Michael S.},  
title = {Generative Agents: Interactive Simulacra of Human Behavior},  
year = {2023},  
publisher = {Association for Computing Machinery},  
address = {New York, NY, USA},  
booktitle = {In the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)},  
keywords = {Human-AI interaction, agents, generative AI, large language models},  
location = {San Francisco, CA, USA},  
series = {UIST '23}
}
```

## <img src="https://joonsungpark.s3.amazonaws.com:443/static/assets/characters/profile/Wolfgang_Schulz.png" alt="Generative Wolfgang">   Acknowledgements

We encourage you to support the following three amazing artists who have designed the game assets for this project, especially if you are planning to use the assets included here for your own project: 
* Background art: [PixyMoon (@_PixyMoon\_)](https://twitter.com/_PixyMoon_)
* Furniture/interior design: [LimeZu (@lime_px)](https://twitter.com/lime_px)
* Character design: [ぴぽ (@pipohi)](https://twitter.com/pipohi)

In addition, we thank Lindsay Popowski, Philip Guo, Michael Terry, and the Center for Advanced Study in the Behavioral Sciences (CASBS) community for their insights, discussions, and support. Lastly, all locations featured in Smallville are inspired by real-world locations that Joon has frequented as an undergraduate and graduate student---he thanks everyone there for feeding and supporting him all these years.



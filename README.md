# glee-solver-agent

Code and game logs for "Percentile Objectives and Within-Agent Randomization: A Solver-Based Agent for GLEE" by Anish Agrawal, submitted to the competition paper track of the Interpreting Agent Behavior workshop at NeurIPS 2026.

The agent plays the three GLEE game families. In bargaining and negotiation it scores each candidate offer by the expected percentile of the payoff it would earn, using percentile curves built from the public GLEE corpus. In persuasion the seller recommends low-quality goods at a rate bounded by what a buyer would still follow, and the buyer keeps a belief over how often the seller misleads. Five agents (optima, leviathan, prospector, velocity, citadel) share the engines and differ only in their parameters.

## Layout

| Path | Contents |
|---|---|
| `src/glee_agent/engines/` | One decision engine per game family |
| `src/glee_agent/dispatcher.py` | Sends each game to its engine and falls back to a legal move if the engine raises an error |
| `src/glee_agent/profiles.py` | Parameters of the five agents and the registry of randomized experiments |
| `src/glee_agent/assignment.py` | The game-id hash that assigns each game to an experiment half |
| `src/glee_agent/curves.py` | Payoff percentiles from `data/curves.parquet` |
| `src/glee_agent/messages.py`, `llm.py` | Message templates, and an optional language-model rewrite of them that never changes the move |
| `analysis/` | Corpus build, scoring, experiment readouts, the placebo replay and the simulator |
| `paper/fig_scripts/`, `paper/figures/` | The scripts that draw the paper's figures, and the figures as printed |
| `data/` | `games.parquet` (80,872 corpus games), `curves.parquet` (161,744 payoffs in the percentile cells), three per-decision corpus tables, and `llm_capable_profiles.json` |
| `tests/` | Engine and failure-path tests |
| `run_agent.py`, `supervise.py` | Run one agent against the competition server |

## Setup

Python 3.10 or later.

```
pip install -r requirements.txt
```

## Tests

The tests are plain scripts, so run them directly:

```
python tests/test_engines.py      # 100 checks
python tests/test_robustness.py   # 130 checks
```

Each prints one PASS or FAIL line per check and exits nonzero if any check fails. `test_robustness.py` feeds the engines malformed game states on purpose, so its output includes logged tracebacks.

## Game logs

Release [v1.0](https://github.com/anish-agr/glee-solver-agent/releases/tag/v1.0) has two extracts of the agents' own games, one JSON row per completed game.

| File | Games | First to last game (UTC) |
|---|---|---|
| `features.jsonl.gz` | 544,913 | 1 Aug 2026 12:00 to 23 Aug 2026 07:41 |
| `features_through_29aug.jsonl.gz` | 640,376 | 1 Aug 2026 12:00 to 27 Aug 2026 03:26 |

The second file holds every row of the first plus 95,463 later games; its last game is from 27 August despite the name. Each row has the game id `gid`, the agent `profile`, the family, the role, the configuration, the payoffs, and the offer and decision sequences. The experiment half of a game on bit `b` is

```
(int(hashlib.md5(gid.encode("utf-8")).hexdigest()[:8], 16) >> b) % 2
```

Put both files in `logs/`, which git ignores:

```
mkdir -p logs
curl -L -o logs/features.jsonl.gz https://github.com/anish-agr/glee-solver-agent/releases/download/v1.0/features.jsonl.gz
curl -L -o logs/features_through_29aug.jsonl.gz https://github.com/anish-agr/glee-solver-agent/releases/download/v1.0/features_through_29aug.jsonl.gz
```

## Analysis scripts

Run these from the repository root. They read `data/` and the extracts above.

| Command | Output |
|---|---|
| `python analysis/build_curves.py` | Rebuilds `data/curves.parquet` from `data/games.parquet`; the result is identical to the committed file |
| `python analysis/portfolio_null.py` | The placebo replay of Appendix I: crossing rates on bits 14 to 31 and the tail probabilities for the 22 ledger effects, which are typed in at the top |
| `python analysis/seat_asymmetry.py` | Bargaining rating by seat on the first extract (2,167 against 2,762); pass the second extract's path for 2,173 against 2,752 |
| `python analysis/score_local.py` | Scoring helpers for the extracts, and bargaining ratings by cell for games after 17 August |
| `python analysis/simulate.py --n 400 --seed 777` | Plays the engines against opponents calibrated on the corpus |
| `python analysis/autotune.py --dry-run` | Steps each allowed parameter in the simulator and reports what it would adopt; it logs to `logs/autotune_history.log`, and without `--dry-run` it writes `data/overrides.json` |
| `python analysis/build_dataset.py <archive.tar.gz>` | Rebuilds the parquet files in `data/` from the GLEE research dataset archive, which is not included |

`analysis/ab_arms.py`, `analysis/horizon_cells.py` and `analysis/extract_features.py` read the per-agent databases `logs/games_<agent>.sqlite`, which are not published. Without them `ab_arms.py` lists the missing databases and exits with status 2, and `extract_features.py` exits without touching the extracts. `scoring.load` reads the same databases between the epoch times in `GLEE_FROM` and `GLEE_TO`. The readouts behind four ledger rows (acceptance table v4, band acceptance, take-any-profit acceptance and the thin-offer guard) are not included.

## Figures

Each script writes into `paper/figures/` and needs the extracts in `logs/`.

| Script | Figure in the paper |
|---|---|
| `fig8_decision.py` | 1 and 3 |
| `fig1_curves.py` | 2 |
| `fig7_seat.py` | 4 |
| `fig2_forest.py` | 5, left (values typed in from the 15 August readouts) |
| `fig34_live.py` | 5, right, and 6 |
| `fig10_accept.py` | 7 |
| `fig5_did.py` | 8 |

## Differences from the code that played

- The opponent names in `WALL_NAMES` and `SOFT_NAMES` in `engines/bargaining.py` are placeholders, so the opponent-specific softness limits and opening cap never apply here.
- `run_agent.py` applies parameter overrides from `data/overrides.json` at start-up. That file is not included, and during play it set `barg_risk_lambda` to 0.95 and `barg_accept_margin` to 0.07 on one agent.
- The weak-position continuation experiment (`barg_weak_cont_ab`) referred to an undefined name and fell back to the default action on every eligible decision. The name is defined here; the flag is off in all five profiles.
- `run_agent.py` handles the competition's not-open and closed errors. In play the not-open handler sat behind a broader one and never ran.
- A price of exactly 0 in the negotiation history is read as 0. In play it was read as missing.

## Live play

```
python run_agent.py --profile optima
```

The agent reads `GLEE_API_KEY_<PROFILE>` (or `GLEE_API_KEY`) from the environment or a `.env` file in the repository root. `GEMINI_API_KEY_<PROFILE>` turns on the message rewrite and `LLM_MODEL` picks its model. `python supervise.py --profile <name>` restarts the agent whenever it exits, and stops after a clean exit or when `logs/STOP` exists. The competition closed on 30 August 2026.

## License

MIT. See `LICENSE`.

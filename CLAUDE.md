# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

All commands must be run from the project root (`Connect-4-Robot/`).

**Start the full game (real hardware):**
```bash
python -m connect4_engine.main
```

**Play AI in terminal (no hardware needed):**
```bash
python -m system_tests.play_ai_text
```

**Test Arduino LED detection / solenoids:**
```bash
python -m system_tests.test_arduino led --port COM5
python -m system_tests.test_arduino solenoids --port COM5
```

**Test robot arm locations (interactive edit mode):**
```bash
python -m system_tests.test_robot_locations --port COM11
python -m system_tests.test_robot_locations --port COM11 --no-edit
```

There is no automated test suite — `system_tests/` and `simulations/` serve as manual integration tests.

## Architecture

The system has three hardware controllers communicating over serial USB:

```
PC (Python) ──serial──> Arduino  (LED strip, solenoids, pump relay, puck detection)
PC (Python) ──serial──> MyCobot 280 arm (via pymycobot)
```

**Game flow:**
1. Arduino sends `START` → `Connect4Game.game_start()` → robot gives player a yellow puck
2. Player drops puck into board → LED strip detects it → Arduino sends `DROP <col>`
3. `Connect4Game.piece_dropped_in_board()` → board updated → AI calculates move
4. Robot picks red puck from stack and drops in AI's column (not detected by LED strip — pucks fall under it)
5. Robot gives player next yellow puck → repeat until win/draw
6. `game_over()` sends `RESET <column_stack>` to Arduino (opens solenoids to drop all pucks)

**Key design: puck indexing.** Both `drop_piece(column, puck_no)` and `give_player_puck(puck_no)` take a `puck_no` counter. `RobotCommunicator.get_puck_loc()` linearly interpolates between stack start/end positions so the arm reaches progressively deeper into the puck stacks as pucks are consumed.

### Module map

| Module | Role |
|---|---|
| `connect4_engine/main.py` | Entry point; wires hardware to game |
| `connect4_engine/game.py` | Game state machine, callback hub |
| `connect4_engine/core/board.py` | Pure board logic (numpy grid, win detection) |
| `connect4_engine/core/ai.py` | Wraps external `c4solver` binary via subprocess |
| `connect4_engine/hardware/arduino.py` | Serial read loop + `IArduino` interface |
| `connect4_engine/hardware/robot.py` | MyCobot280 arm movements + `IRobot` interface |
| `connect4_engine/hardware/mock.py` | `ArduinoDummy`, `RobotDummy` for testing without hardware |
| `connect4_engine/utils/config.py` | Loads `config.yaml`, resolves COM ports by OS |
| `connect4_engine/utils/logger.py` | Singleton `logger` + `@timed` decorator |

### Interfaces

`IArduino` and `IRobot` are the ABCs that all real and mock hardware implements. `Connect4Game` only types against these interfaces, so swapping in mocks requires only changing `main.py`.

`ArduinoCommunicator` runs `read_loop()` (blocking) in the main thread. Hardware callbacks (`game_start`, `_on_puck_dropped`, `interrupt_callback`) must be registered before calling `read_loop()`. Each `START` or `DROP` message spawns a worker thread; `interrupt_callback` sets `robot.killswitch` to abort in-flight arm movement.

### AI solver

`AIPascalPons` spawns `connect4_engine/core/c4solver.exe` (Windows) or `c4solver` (Linux) as a long-lived subprocess. It communicates via stdin/stdout using Pascal Pons' column-sequence format (1-indexed moves as a string, e.g. `"4415"`). The solver returns 7 space-separated scores; the engine samples from the top-k with softmax (`temp` controls randomness).

### Configuration

`config.yaml` at project root controls:
- Logging level/output/file
- COM ports for robot and Arduino (separate win/linux keys)
- `pause_between_moves` — if `true`, robot pauses and waits for Enter after each arm movement (useful for calibration)

Robot arm positions are stored in `connect4_engine/hardware/legacy_coords.json` (default) or a custom JSON passed via `--json-path`. The JSON contains `angle_table`, `chess_table`, and `drop_table` keyed by position name.

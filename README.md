# Connect 4 Robot

A robotic Connect 4 game where a MyCobot 280 robot arm plays against a human player. The system uses drop detection via LED strip sensors, automated puck dispensing with solenoids, and AI-powered gameplay.

## System Overview

```
┌───────────────────────────────────┐
│       PC MAIN CONTROLLER          │
│   ┌────────────┬────────────┐     │
│   │   Robot    │   Arduino  │     │
│   │ Interface  │ Interface  │     │
│   └────────────┴────────────┘     │
└─────────────┬──────┬──────────────┘
              │      │
        USB Serial   USB Serial
              │      │
     ┌────────▼─┐ ┌───▼────────────┐
     │  Robot   │ │   Arduino      │
     │  Arm     │ │ - LED Strip    │
     │  (via    │ | - Solenoids    │
     │pymycobot)│ │ - Sensors      │
     └──────────┘ └────────────────┘
```

## Architecture

The system consists of three main controllers:

1. **PC Main Controller** - Orchestrates gameplay, runs AI, manages state
2. **Arduino Controller** - Handles LED strip, solenoid puck release, drop detection sensors
3. **MyCobot 280 Robot Arm** - Picks and places pucks (using connected pump), delivers pucks to player

## Key Components

### Game Logic (`game.py`)
- **Responsibilities**: Orchestrate turns, check win/draw, trigger robot moves
- **Event Handler**: `on_player_drop(column)` - called when Arduino detects puck
- **Flow**: Player drops → Update board → Check win → Calculate AI move → Execute robot → Repeat

### Board (`core/board.py`)
- **Responsibilities**: Store state, validate moves, detect wins
- **Pure Logic**: No hardware dependencies, easily testable
- **API**: `drop_piece()`, `is_valid_move()`, `check_win()`, `is_draw()`, `get_state()`

### AI Engine (`core/ai.py`)
- **Algorithm**: Minimax with alpha-beta pruning
- **Input**: Board state as 2D array
- **Output**: Best column to play (0-6)
- **Configurable**: Search depth adjustable via `config.yaml`

### Arduino Interface (`hardware/arduino.py`)
- **Responsibilities**: Serial communication, command sending, event callbacks
- **Commands**: `RELEASE:<col>`, `LED:[ON/OFF]`, `RESET`, `STATUS`
- **Events**: `DROP:<col>` (puck detected), `READY`, `ERROR:<msg>`
- **Thread Model**: Background listener thread for async event handling

### Robot Interface (`hardware/robot.py`)
- **Wrapper**: Clean API around legacy `ArmInterface.py`
- **Methods**: `place_puck_at_column(col)`, `give_player_puck()`, `move_to_home()`
- **Position Management**: Loads calibrated positions from `positions.json`

### Mock Hardware (`hardware/mock.py`)
- **Purpose**: Enable development/testing without physical hardware
- **Classes**: `MockArduino`, `MockRobot`
- **Usage**: Set `simulation: true` in `config.yaml`


## Setup

### Prerequisites

- **Hardware** (for production use):
  - MyCobot 280 robot arm (M5 Stack version)
  - Arduino with custom PCB (LED strip + solenoid drivers + sensors)
  - USB connections for both
  
- **Software**:
  - Python 3.8+
  - Arduino IDE (for firmware upload)

## How to Play

1. System initializes and robot moves to home position
2. Robot gives yellow puck to player at pickup location
3. Player drops puck in any column (detected by LED strip sensor)
4. PC calculates best move and robot executes (picks red puck, drops in column)
5. Robot returns and gives next yellow puck to player
6. Repeat until someone wins or board is full
7. System displays winner via XXX??? and resets for new game


# System tests

Run from **project root** (Connect-4-Robot).

## 1. Game AI (text-only play)

No Arduino or robot. Play Connect 4 against the AI in the terminal.

```bash
python -m system_tests.play_ai_text
```

Enter column 0–6 or `quit`. After each game you can play again.

## 2. Robot location test

Runs the arm through a safe sequence; after each step you enter **edit mode**:

- **1** / **2**: nudge +X / -X (mm)
- **3** / **4**: nudge +Y / -Y
- **5** / **6**: nudge +Z / -Z
- **r**: release servos (move arm by hand)
- **l**: lock servos
- **v**: save current position to the step and write JSON
- **n**: next step (no save)

```bash
python -m system_tests.test_robot_locations --port COM11
python -m system_tests.test_robot_locations --port COM11 --json-path path/to/robot_locations.json
python -m system_tests.test_robot_locations --port COM11 --no-edit   # run sequence only, no edit mode
```

## 3. Arduino tests

**LED detection** – serial monitor for `DROP <col>` and `START`:

```bash
python -m system_tests.test_arduino led --port COM5
```

**Solenoids** – send OPEN, then CLOSE; optionally RESET:

```bash
python -m system_tests.test_arduino solenoids --port COM5
python -m system_tests.test_arduino solenoids --port COM5 --reset
```

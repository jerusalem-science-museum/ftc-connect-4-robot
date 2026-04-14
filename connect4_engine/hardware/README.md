# robot coordinates
the `coords.json` contains both cartesian & angles, used for calibration. in the final run of the game, we'll use `angles.json` with all the linear transformations baked in, to make sure the system is deterministic (since IK isn't).

for linear movements, we'll save all the values as a list of coords/angles in the json. that way list[list] == some linear movement.

to test that our saved linear movement is ok, we'll go back a step in the sequence and then do the newly saved sequence (since we only saved the final position, so we need to test the linear motion).
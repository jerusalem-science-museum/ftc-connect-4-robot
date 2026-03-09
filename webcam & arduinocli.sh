# Dependencies
sudo apt install -y cmake libjpeg-dev gcc g++ git

# Clone and build
git clone https://github.com/jacksonliam/mjpg-streamer.git
cd mjpg-streamer/mjpg-streamer-experimental
make
sudo make install

# then to run:
mjpg_streamer \
  -i "input_uvc.so -d /dev/video0 -fps 15 -q 50" \
  -o "output_http.so -w ./www -p 8080"

# and to connect from pc
http://<rpi-tailscale-ip>:8080/?action=stream


# arduino cli:
# Install
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Connect Arduino via USB, then:
arduino-cli board list          # find port (e.g. /dev/ttyUSB0 or /dev/ttyACM0)

# general compiling:
arduino-cli core install arduino:avr
arduino-cli compile --upload -v -p /dev/ttyUSB0 --fqbn arduino:avr:nano my_sketch/

sudo apt install picocom # for interactive shell w arduino
sudo apt-get install socat # for testing arduino commands without having a button or whatever

# create virtual serial pair
# sudo socat -d -d PTY,link=/dev/ttyUSB0,raw,echo=0 PTY,link=/dev/ttyVIRTUAL0,raw,echo=0

# put this in your bashrc for vi-lite commands.

# fun bashrc stuff.

# Auto-attach to tmux
# if command -v tmux &>/dev/null && [ -z "$TMUX" ]; then
#   tmux attach 2>/dev/null || tmux new-session
# fi
# PS1='\[\e[36m\]\W\[\e[0m\] \$ '
# set -o vi
# bind 'set show-mode-in-prompt on'
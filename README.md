## A Python audio visualizer with Spotify integration

### How to use:
The visualizer **does not** read audio data from Spotify. You have to figure out a way to route your audio output to a microphone input.

#### Windows:
Tools like [VB-Audio Cable](https://vb-audio.com/Cable/index.htm) or [Voicemeeter](https://vb-audio.com/Voicemeeter/index.htm) should do this pretty easily.

#### Linux:
You may be able to do this by default in PulseAudio or Pipewire, but I  like to use [qpwgraph](https://gitlab.freedesktop.org/rncbc/qpwgraph) or [Soundux](https://soundux.rocks/).

#### Mac:
I don't own a mac myself, but [VB-Audio Cable](https://vb-audio.com/Cable/index.htm) should work here too.\
\
After setting the audio and `tokens.json` file (check below) up, You'll be able to start the app. If you press escape you'll see a settings menu. There you have to select your input device at the bottom.\
Have fun!

### Gitignore:
The `tokens.json` file (root) has to look like:
```json
{
  "redirect_uri": "http://localhost:8888/callback",
  "client_id": "spotify_id",
  "client_secret": "spotify_secret"
}
```
You have to create it yourself as I'm not looking into sharing mine. If you don't know how to get those values, use a guide like [this](https://medium.com/@maxtingle/getting-started-with-spotifys-api-spotipy-197c3dc6353b).

### Important:
This has only been tested on Arch Linux. I cannot guarantee that this works anywhere else. If it doesn't work somewhere, please create an Issue.\
Don't create any issues about the third-party apps I linked. I don't have any control over them and won't be able to help you.

### More projects by me:
https://zohiu.de/projects/ 
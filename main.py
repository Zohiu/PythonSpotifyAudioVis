import io
import json
import time
import sys
import random
from urllib.request import urlopen

import pygame
from pygame import gfxdraw
import pygame_menu
from tkinter import messagebox, Tk

import math

import numpy as np
import sounddevice as sd

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import threading

scope = "user-read-playback-state"
with open("tokens.json", "r") as f:
    tokenstuff = json.loads(f.read())
spotify = spotipy.Spotify(
    client_credentials_manager = SpotifyOAuth(
        scope = scope,
        redirect_uri = tokenstuff["redirect_uri"],
        client_id = tokenstuff["client_id"],
        client_secret = tokenstuff["client_secret"]
    )
)


def reload_spotify():
    global track, artists, playing, progress, duration, album_art, is_playing
    error = True
    print("Getting Spotify info...")
    while error:
        try:
            track = spotify.current_user_playing_track()
            artists = track['item']['artists']
            playing = track['item']['name']
            progress = track['progress_ms']
            duration = track['item']['duration_ms']
            album_art = pygame.image.load(io.BytesIO(urlopen(track['item']['album']['images'][0]['url']).read()))
            is_playing = track['is_playing']
            error = False
        except Exception:
            error = True


# Initialize pygame window
pygame.init()
WIDTH, HEIGHT = 1280, 720
HEIGHT_USABLE = HEIGHT
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption('Zviz')
screen.fill((0, 0, 0))
clock = pygame.time.Clock()

# Hide tk window, just using it for popups anyway
tk = Tk()
tk.wm_withdraw()


def column_change(*args):
    global points, points_buffer
    points = []
    points_buffer = []
    for i in range(int(COLUMNS.get_value())):
        points.append((0, 300))
        points_buffer.append([(0, 300)])


def restart_main(*args):
    print(DEVICE.get_value())
    global abort
    abort = True
    time.sleep(0.01)
    abort = False
    main()


# Window details
MIN_HEIGHT = 600
MIN_WIDTH = 800

# Settings details
MENU_HEIGHT = 400
MENU_WIDTH = 600

# Pygame menu with settings
menu = pygame_menu.Menu('Settings', MENU_WIDTH, MENU_HEIGHT, theme = pygame_menu.themes.THEME_DARK)

ALL_MODES_DICT = {0: 'Outside', 1: 'Inside', 2: 'None'}
CURRENT_MODE = menu.add.range_slider(
    'Album art size', 0, list(ALL_MODES_DICT.keys()),
    slider_text_value_enabled = False,
    value_format = lambda x: ALL_MODES_DICT[x]
)
CURRENT_MODE.set_value(1)

BLOCK_DURATION = menu.add.range_slider('Audio Buffer Size', 50, (0, 150), 1, value_format = lambda x: str(int(x)), onchange = restart_main)
COLUMNS = menu.add.range_slider('Resolution', 500, (100, 1000), 1, value_format = lambda x: str(int(x)), onchange = column_change)
WAVE_BUFFER_SIZE = menu.add.range_slider('Smoothing', 5, (1, 25), 1, value_format = lambda x: str(int(x)))
GAIN = menu.add.range_slider('Audio Gain', 20, (1, 100), 1, value_format = lambda x: str(int(x)))
MAX_WAVE_HEIGHT = 0

WAVE_THICKNESS = menu.add.range_slider('Outline thickness', 2, (0, 10), 1, value_format = lambda x: str(int(x)))
OUTLINE_COLOR = menu.add.color_input('Outline color ', color_type = "rgb")
OUTLINE_COLOR.set_default_value((0, 0, 0))

DROP_SHADOW_SIZE = menu.add.range_slider('Shadow size', 5, (0, 25), 1, value_format = lambda x: str(int(x)))
DROP_SHADOW_OPACITY = menu.add.range_slider('Shadow opacity', 128, (0, 255), 1, value_format = lambda x: str(int(x)))

VIS_BORDER_SIZE = menu.add.range_slider('Element Borders', 25, (0, 100), 1, value_format = lambda x: str(int(x)))
FREQ_RANGE = menu.add.range_slider('Frequency range', (20, 2500), (20, 20000), 1)
FPS = menu.add.range_slider('FPS', 60, (1, 500), 1, value_format = lambda x: str(int(x)))

SPOTIFY_SIZES_DICT = {-2: '10', 0: '8', 2: '6'}
SPOTIFY_SIZE = menu.add.range_slider(
    'Album art size', 0, list(SPOTIFY_SIZES_DICT.keys()),
    slider_text_value_enabled = False,
    value_format = lambda x: SPOTIFY_SIZES_DICT[x]
)
SPOTIFY_SIZE.set_value(2)

# Add all available devices to the list
all_devices = []
for device in sd.query_devices():
    all_devices.append((device["name"], device["index"]))

DEVICE = menu.add.dropselect(
    title = 'Input Device',
    items = all_devices,
    font_size = 16,
    selection_option_font_size = 20,
    onchange = restart_main
)

menu.disable()

# General vars needed
abort = False
fullscreen = False
freq_values_buffer = [[], [], [], [], []]
current_circles = []
current_wave_colors = []


def new_circle():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    
    radius = random.randint(10, int(WIDTH / 24 + HEIGHT / 24))
    
    temp_WIDTH = WIDTH - radius
    temp_HEIGHT = HEIGHT - radius
    
    x = random.randint(radius, temp_WIDTH)
    y = random.randint(radius, temp_HEIGHT)
    
    current_circles.append(((r, g, b), (x, y), radius))


def clear_circles():
    current_circles.clear()


def draw_circles():
    for circle in current_circles:
        pygame.draw.circle(screen, circle[0], circle[1], circle[2])


def new_wave_colors():
    current_wave_colors.clear()
    for i in range(2):
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        current_wave_colors.append((r, g, b))


# Setup points vars and colors and spotify, so it doesn't crash on first run due to missing entries
column_change()
new_wave_colors()
reload_spotify()


# This gets executed by the sounddevice input stream and allows to get real-time audio data
def callback(indata, frames, time_unused, status):
    global delta_f, fftsize, low_bin, points
    delta_f = (FREQ_RANGE.get_value()[1] - FREQ_RANGE.get_value()[0]) / (int(COLUMNS.get_value()) - 1)
    fftsize = math.ceil(samplerate / delta_f)
    low_bin = math.floor(FREQ_RANGE.get_value()[0] / delta_f)
    
    # Only execute if there is any data, to avoid random crashes.
    if any(indata):
        # I have no idea how this works, but it makes numbers from numbers and works.
        magnitude = np.abs(np.fft.rfft(indata[:, 0], n = fftsize))
        magnitude *= int(GAIN.get_value()) / fftsize
        
        # Calculate the actual real wave data. Taken from wiki.
        # DON'T TOUCH! I HAVE NO IDEA HOW TO EVER MAKE THIS WORK AGAIN
        if HEIGHT / 2 < int(MAX_WAVE_HEIGHT):
            _height = HEIGHT / 2
        else:
            _height = int(MAX_WAVE_HEIGHT)
        
        line = (int(np.clip(x, 0, 1) * (_height - 1))
                for x in magnitude[low_bin:low_bin + int(COLUMNS.get_value())])
        
        points = []

        # Calculate the actual point positions on the display from the wave data
        index = 0
        for x in line:
            index += 1
            points.append(((index * (WIDTH - VIS_BORDER_SIZE.get_value() * 2) / int(COLUMNS.get_value())) + VIS_BORDER_SIZE.get_value(), HEIGHT_USABLE / 2 - x))


# Sounddevice input stream
def main(*args):
    # All global vars needed in this!
    global screen, HEIGHT, WIDTH, abort, DEVICE, samplerate, fullscreen, progress, HEIGHT_USABLE, MAX_WAVE_HEIGHT
    
    _device = None
    spotify_update_clock = 0
    
    # If the bypass is not set, do fancy stuff for device.
    # If it's set, the device will just be None.
    if len(args) == 0:
        # Get sound device from settings
        try:
            _device = DEVICE.get_value()[1]
        except ValueError:
            _device = None
        samplerate = sd.query_devices(_device, 'input')['default_samplerate']
    
    try:
        with sd.InputStream(
                device = _device,
                channels = 1,
                callback = callback,
                blocksize = int(samplerate * BLOCK_DURATION.get_value() / 1000),
                samplerate = samplerate
        ):
            while True:
                # Set current window size
                WIDTH, HEIGHT = pygame.display.get_surface().get_size()

                _size_between_album_art_and_top_border = 1.1

                _spotify_scale = int(SPOTIFY_SIZES_DICT[SPOTIFY_SIZE.get_value()])
                _spotify_win_size = int(VIS_BORDER_SIZE.get_value()) + HEIGHT / _spotify_scale * _size_between_album_art_and_top_border
                _spotify_top_coord = HEIGHT - _spotify_win_size
                
                HEIGHT_USABLE = HEIGHT - _spotify_win_size
                MAX_WAVE_HEIGHT = HEIGHT_USABLE / 2 - int(VIS_BORDER_SIZE.get_value())
                
                # Make this stoppable
                global abort
                if abort:
                    return
                
                # Reset screen to draw new frame
                screen.fill((0, 0, 0))
                
                # Handling the points buffer, remove first entry if there are more than WAVE_BUFFER_SIZE entries.
                # try-except because it threw errors and this "solved" that. Lmao.
                _index = 0
                for group in points_buffer:
                    try:
                        group.append(points[_index])
                        while len(group) > int(WAVE_BUFFER_SIZE.get_value()):
                            group.pop(0)
                        _index += 1
                    except IndexError:
                        pass
                
                # Taking the points buffer to calculate the average of the last WAVE_BUFFER_SIZE runs.
                # AKA smoothing the wave
                _smooth_points = [(VIS_BORDER_SIZE.get_value(), HEIGHT_USABLE / 2)]
                for group in points_buffer:
                    _all = 0
                    for point in group:
                        _all += point[1]
                    
                    _all = _all / len(group)
                    _smooth_points.append((group[0][0], _all))
                
                _smooth_points.append((WIDTH - VIS_BORDER_SIZE.get_value(), HEIGHT_USABLE / 2))
                
                # Calculate opposite of points, to mirror the wave at the bottom
                _points_rev = []
                for i in _smooth_points:
                    _points_rev.append((i[0], (i[1] - HEIGHT_USABLE / 2) * -1 + HEIGHT_USABLE / 2))
                
                # Other effects
                _sub_bass_freq = round(len(_points_rev) * ((FREQ_RANGE.get_value()[0] + 60) / FREQ_RANGE.get_value()[1]))
                _bass_freq = round(len(_points_rev) * ((FREQ_RANGE.get_value()[0] + 250) / FREQ_RANGE.get_value()[1]))
                _low_mid_freq = round(len(_points_rev) * ((FREQ_RANGE.get_value()[0] + 500) / FREQ_RANGE.get_value()[1]))
                _mid_freq = round(len(_points_rev) * ((FREQ_RANGE.get_value()[0] + 1000) / FREQ_RANGE.get_value()[1]))
                
                # Get average val of each frequency range
                # Use _points_rev since it's where louder = higher value.
                _freq_values = []
                _index = 0
                for lst in [
                    (_points_rev[:_sub_bass_freq], 4),  # Second val = activation threshold
                    (_points_rev[_sub_bass_freq:_bass_freq], 3),
                    (_points_rev[_bass_freq:_low_mid_freq], 2),
                    (_points_rev[_low_mid_freq:_mid_freq], 1),
                    (_points_rev[_mid_freq:], 0)
                ]:
                    _sum = 0
                    for value in lst[0]:
                        _sum += value[1] - HEIGHT / 2
                    _freq_values.append((round(_sum / len(lst[0]), 1), lst[1]))
                    freq_values_buffer[_index].append(round(_sum / len(lst[0]), 1))
                    _index += 1
                
                # get the freq values average list
                # and don't let freq_values_buffer get too large.
                _freq_values_average = []
                for freq in freq_values_buffer:
                    while len(freq) > int(WAVE_BUFFER_SIZE.get_value()):
                        freq.pop(0)
                    _freq_values_average.append(sum(freq) / len(freq))
                
                _outputtest = []
                _index = 0
                for val in _freq_values:
                    if val[0] > _freq_values_average[_index] + val[1]:
                        _outputtest.append(True)
                    else:
                        _outputtest.append(False)
                
                draw_circles()
                
                if _outputtest[0]:
                    if random.random() < 0.1:
                        new_wave_colors()
                    for i in range(5):
                        clear_circles()
                    # pygame.draw.circle(screen, (255, 0, 0), (WIDTH / 2 - 150, HEIGHT / 2), 50)
                
                if _outputtest[1]:
                    if random.random() < 0.1:
                        new_circle()
                    # pygame.draw.circle(screen, (255, 255, 0), (WIDTH / 2 - 75, HEIGHT / 2), 50)
                elif _outputtest[2]:
                    if random.random() < 0.1:
                        new_circle()
                    # pygame.draw.circle(screen, (0, 255, 0), (WIDTH / 2, HEIGHT / 2), 50)
                elif _outputtest[3]:
                    if random.random() < 0.1:
                        new_circle()
                    # pygame.draw.circle(screen, (0, 255, 255), (WIDTH / 2 + 75, HEIGHT / 2), 50)
                elif _outputtest[3]:
                    if random.random() < 0.1:
                        new_circle()
                    # pygame.draw.circle(screen, (0, 0, 255), (WIDTH / 2 + 150, HEIGHT / 2), 50)
                else:
                    # If only sub bass has a signal, new wave colors pls
                    if _outputtest[0]:
                        if random.random() < 0.1:
                            new_wave_colors()
                    
                    # If everything above sub bass doesn't have a signal, make some circles
                    for i in range(5):
                        if random.random() < 0.1:
                            new_circle()
                
                if random.random() < 0.01:
                    clear_circles()
                
                norm = _freq_values_average[0]
                for i in _freq_values_average:
                    if i != norm:
                        break
                else:
                    # Weird python thing, else after a for loop only executes when the loop wasn't broken.
                    clear_circles()

                # Inside mode, need to change around some stuff
                if CURRENT_MODE.get_value() == 1:
                    for point in _smooth_points:
                        _smooth_points[_smooth_points.index(point)] = (point[0], point[1] + HEIGHT_USABLE / 2)
                    
                    
                    for point in _points_rev:
                        _points_rev[_points_rev.index(point)] = (point[0], point[1] - HEIGHT_USABLE / 2 + int(VIS_BORDER_SIZE.get_value()))


                # Drop shadow points calculations
                _drop_default = []
                for point in _smooth_points:
                    _drop_default.append((point[0], point[1] - int(DROP_SHADOW_SIZE.get_value())))
                _drop_default[0] = (_smooth_points[0][0], _smooth_points[0][1])
                _drop_default[-1] = (_smooth_points[-1][0], _smooth_points[-1][1])

                _drop_rev = []
                for point in _points_rev:
                    _drop_rev.append((point[0], point[1] + int(DROP_SHADOW_SIZE.get_value())))
                _drop_rev[0] = (_points_rev[0][0], _points_rev[0][1])
                _drop_rev[-1] = (_points_rev[-1][0], _points_rev[-1][1])
                
                # Don't draw in mode 2.
                if CURRENT_MODE.get_value() < 2:
                    # Draw shadow
                    pygame.gfxdraw.filled_polygon(screen, _drop_default, (0, 0, 0, int(DROP_SHADOW_OPACITY.get_value())))
                    pygame.gfxdraw.filled_polygon(screen, _drop_rev, (0, 0, 0, int(DROP_SHADOW_OPACITY.get_value())))
                    
                    # Draw default and mirrored shape
                    pygame.gfxdraw.filled_polygon(screen, _smooth_points, current_wave_colors[0])
                    pygame.gfxdraw.filled_polygon(screen, _points_rev, current_wave_colors[1])
                    
                    # Draw default and mirrored outlines
                    try:
                        pygame.draw.lines(screen, color = OUTLINE_COLOR.get_value(), points = _smooth_points, closed = False, width = int(WAVE_THICKNESS.get_value()))
                        pygame.draw.lines(screen, color = OUTLINE_COLOR.get_value(), points = _points_rev, closed = False, width = int(WAVE_THICKNESS.get_value()))
                    except ValueError:
                        pygame.draw.lines(screen, color = (255, 255, 255), points = _smooth_points, closed = False, width = int(WAVE_THICKNESS.get_value()))
                        pygame.draw.lines(screen, color = (255, 255, 255), points = _points_rev, closed = False, width = int(WAVE_THICKNESS.get_value()))

                # Update spotify data
                if spotify_update_clock > 5:
                    spotify_update_clock = 0
                    # reload in a thread to not freeze the app while it's waiting for spotify
                    threading.Thread(target = reload_spotify).start()
                
                # Don't make the progress bar go longer than it can!
                if progress > duration:
                    spotify_update_clock += 100
                    progress = duration
                
                # Draw spotify stuff
                # Spotify window stuff - NEEDED now and right after!
                _spotify_scale = int(SPOTIFY_SIZES_DICT[SPOTIFY_SIZE.get_value()])
                _spotify_top_coord = HEIGHT - int(VIS_BORDER_SIZE.get_value()) - HEIGHT / _spotify_scale*_size_between_album_art_and_top_border
                
                # transparent background for spotify area
                _s = pygame.Surface((WIDTH, HEIGHT - int(VIS_BORDER_SIZE.get_value()) + HEIGHT - HEIGHT / _spotify_scale))
                _s.set_alpha(int(DROP_SHADOW_OPACITY.get_value()))
                _s.fill((0, 0, 0))
                screen.blit(_s, (0, _spotify_top_coord))
                
                # line above transparent background - seperator
                try:
                    pygame.draw.line(screen, color = OUTLINE_COLOR.get_value(), start_pos = (0, _spotify_top_coord), end_pos = (WIDTH, _spotify_top_coord), width = int(WAVE_THICKNESS.get_value()))
                except ValueError:
                    pygame.draw.line(screen, color = (255, 255, 255), start_pos = (0, _spotify_top_coord), end_pos = (WIDTH, _spotify_top_coord), width = int(WAVE_THICKNESS.get_value()))
                
                # Album art
                screen.blit(
                    pygame.transform.scale(album_art, (HEIGHT / _spotify_scale, HEIGHT / _spotify_scale)),
                    (int(VIS_BORDER_SIZE.get_value()), -int(VIS_BORDER_SIZE.get_value()) + HEIGHT - HEIGHT / _spotify_scale)
                )
                
                # Song title
                text = pygame.font.Font('Roboto-Bold.ttf', int(HEIGHT / _spotify_scale * 0.25)).render(f"{playing}", True, (255, 255, 255))
                textRect = text.get_rect()
                textRect.center = (
                (int(VIS_BORDER_SIZE.get_value()) + HEIGHT / _spotify_scale * 1.075) + textRect.size[0] / 2, -int(VIS_BORDER_SIZE.get_value()) + HEIGHT - HEIGHT / _spotify_scale + textRect.height / 2)
                screen.blit(text, textRect)
                # When text too big for screen f
                if textRect.size[0] > WIDTH - int(VIS_BORDER_SIZE.get_value()) * 2 - HEIGHT / _spotify_scale:
                    pass
                
                # artists
                _title_height = textRect.height
                _artists = ""
                for artist in artists:
                    _artists += f"{artist['name']}, "
                text = pygame.font.Font('Roboto-Bold.ttf', int(HEIGHT / _spotify_scale * 0.15)).render(_artists[:-2], True, (255, 255, 255))
                textRect = text.get_rect()
                textRect.center = (
                    (int(VIS_BORDER_SIZE.get_value()) + HEIGHT / _spotify_scale * 1.075) + textRect.size[0] / 2,
                    -int(VIS_BORDER_SIZE.get_value()) + HEIGHT - HEIGHT / _spotify_scale + textRect.height / 2 + _title_height)
                screen.blit(text, textRect)
                
                # Time progress text
                _seconds = int((progress / 1000) % 60)
                _minutes = int((progress / (1000 * 60)) % 60)
                if len(str(_seconds)) == 1:
                    _seconds = f"0{_seconds}"
                _current = f"{_minutes}:{_seconds}"
                
                text = pygame.font.Font('Roboto-Bold.ttf', int(HEIGHT / _spotify_scale * 0.15)).render(_current, True, (255, 255, 255))
                textRect = text.get_rect()
                textRect.center = ((int(VIS_BORDER_SIZE.get_value()) + HEIGHT / _spotify_scale * 1.075) + textRect.size[0] / 2, HEIGHT - int(VIS_BORDER_SIZE.get_value()) - textRect.size[1] / 2)
                screen.blit(text, textRect)
                
                # Total time text
                _seconds = int((duration / 1000) % 60)
                _minutes = int((duration / (1000 * 60)) % 60)
                if len(str(_seconds)) == 1:
                    _seconds = f"0{_seconds}"
                _total = f"{_minutes}:{_seconds}"
                
                text = pygame.font.Font('Roboto-Bold.ttf', int(HEIGHT / _spotify_scale * 0.15)).render(_total, True, (255, 255, 255))
                textRect = text.get_rect()
                textRect.center = ((int(VIS_BORDER_SIZE.get_value()) + HEIGHT / _spotify_scale * 1.1) + textRect.size[0] / 2 + int(WIDTH / _spotify_scale * 3) - textRect.size[0],
                                   HEIGHT - int(VIS_BORDER_SIZE.get_value()) - textRect.size[1] / 2)
                screen.blit(text, textRect)
                
                # Progress bar border
                pygame.draw.rect(
                    screen, (255, 255, 255),
                    pygame.Rect(
                        (int(VIS_BORDER_SIZE.get_value()) + HEIGHT / _spotify_scale * 1.1) - HEIGHT / _spotify_scale * 0.025,  # top x
                        HEIGHT - int(VIS_BORDER_SIZE.get_value()) - textRect.height - HEIGHT / _spotify_scale * 0.12 - HEIGHT / _spotify_scale * 0.025,  # top y
                        int(WIDTH / _spotify_scale * 3) + HEIGHT / _spotify_scale * 0.025,  # Progress / max length
                        HEIGHT / _spotify_scale * 0.08 + HEIGHT / _spotify_scale * 0.025 * 2  # Height
                    )
                )
                
                # Progress bar
                pygame.draw.rect(
                    screen, (0, 0, 0),
                    pygame.Rect(
                        (int(VIS_BORDER_SIZE.get_value()) + HEIGHT / _spotify_scale * 1.1),  # top x
                        HEIGHT - int(VIS_BORDER_SIZE.get_value()) - textRect.height - HEIGHT / _spotify_scale * 0.12,  # top y
                        int(WIDTH / _spotify_scale * 3) * progress / duration,  # Progress / max length
                        HEIGHT / _spotify_scale * 0.08  # Height
                    )
                )
                
                # Pygame event handling
                events = pygame.event.get()
                for event in events:
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            if menu.is_enabled():
                                menu.disable()
                            else:
                                menu.enable()
                        
                        elif event.key == pygame.K_f or event.key == pygame.K_F11:
                            if fullscreen:
                                screen = pygame.display.set_mode((MIN_WIDTH, MIN_HEIGHT), pygame.RESIZABLE)
                                fullscreen = False
                            else:
                                screen = pygame.display.set_mode((1920, 1080), pygame.FULLSCREEN)
                                fullscreen = True
                    
                    elif event.type == pygame.VIDEORESIZE:
                        width, height = event.size
                        if width < MIN_WIDTH:
                            width = MIN_WIDTH
                            screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                        if height < MIN_HEIGHT:
                            height = MIN_HEIGHT
                            screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                
                # Pygame-menu "event handling"
                if menu.is_enabled():
                    menu.update(events)
                    menu.draw(screen)
                
                # Update!
                pygame.display.flip()
                dt = clock.tick(int(FPS.get_value()))
                spotify_update_clock += dt / 1000
                if is_playing:
                    progress += dt

    
    except Exception as e:
        raise e
        messagebox.showwarning(f'Warning!', f'{e}')
        tk.update()
        main(True)


if __name__ == "__main__":
    # This just works, don't touch plz
    try:
        device = DEVICE.get_value()[1]
    except ValueError:
        device = None
    samplerate = sd.query_devices(device, 'input')['default_samplerate']
    
    delta_f = (FREQ_RANGE.get_value()[1] - FREQ_RANGE.get_value()[0]) / (int(COLUMNS.get_value()) - 1)
    fftsize = math.ceil(samplerate / delta_f)
    low_bin = math.floor(FREQ_RANGE.get_value()[0] / delta_f)
    
    main()
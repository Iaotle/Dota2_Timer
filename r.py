from __future__ import annotations
import datetime
import pyautogui
import cv2 as cv
import numpy as np
from threading import Timer
import threading
import os
import time
import curses
from queue import Queue
from playsound import playsound
import easyocr
import argparse
from Dota2_Timer import Dota2_Timer
from utils.cooldown import Respawn_Duration, Mode

BORDER_WIDTH = 1
X_OFFSET = 4
Y_OFFSET = 2


parser = argparse.ArgumentParser(description='Dota 2 Timer')
parser.add_argument('--turbo', action='store_true', help='Turbo mode', default=False)
parser.add_argument('--debug', action='store_true', help='Debug mode (sets all timers to 20 seconds)', default=False)
parser.add_argument('--confidence', action='store_true', help='Show model confidence', default=False)
parser.add_argument('--refresh_interval', type=int, help='Refresh interval in seconds', default=1)
parser.add_argument('--refresh_interval_curses', type=int, help='Refresh interval for the frontend (ms)', default=500)
args = parser.parse_args()


reader = easyocr.Reader(['en'])
events_window = (0, 480, 800, 520)
items_window = (1500, 1250, 720, 130)
time_window = (1242, 30, 68, 20)
global_game_timedelta = datetime.timedelta(hours=0, minutes=0, seconds=0)



def pretty_percent(value: float, size: int = 20, showPercentage: bool = False, lsep = '[', rsep = ']', fill='■') -> str:
    # TODO: handle negative percentages by normalizing
    # show percentage, then show a progress bar that is filled depending on percentage
    percent = f"{value:.2%}"
    percent = percent.rjust(7)
    progress = int(value * size)
    ret = f"{lsep}{fill * progress}{' ' * (size - progress)}{rsep}"
    if showPercentage:
        return f"{ret} {percent}"
    return ret


def progress_bar(progress: float, message: str, return_size: int = 20, showPercentage: bool = False, lsep = '[', rsep = ']', fill='■') -> str:
    """
    Create a progress bar with a message and a percentage.
    Total string size that will be returned is return_size."""
    percent = f"{progress:.2%}"
    percent = percent.rjust(7)
    
    current_message_size = len(message) + len(lsep) + len(rsep) + len(fill) + 1 # +1 for the space
    
    if showPercentage:
        current_message_size += len(percent) + 1 # +1 for the space
    progress_bar_size = return_size - current_message_size
    progress = int(progress * progress_bar_size)
    ret = f"{lsep}{fill * progress}{' ' * (progress_bar_size - progress)}{rsep}"
    
    if showPercentage:
        ret += f" {percent}"
    ret += f" {message}"
    return ret
    


c = threading.Condition()
class RunImageRecognition(threading.Thread):
    def __init__(self, queue: Queue[list, str, int], *args, **kwargs):
        super(RunImageRecognition,self).__init__(*args, **kwargs)
        self.queue = queue
    
    
    def run(self):
        # mutex
        c.acquire()
        self.run_image_detection(*self.queue.get())
        c.notify()
        c.release()
        
    def run_image_detection(self, timers: list[Dota2_Timer], conf_win: TerminalWindow, history: dict, game_time: str, y: int, x: int):
        s = pyautogui.screenshot()
        s = cv.cvtColor(np.array(s), cv.COLOR_RGB2BGR)
        conf_win.clear()
        
        screenshot = s[time_window[1]:time_window[1]+time_window[3], time_window[0]:time_window[0]+time_window[2]]
        result = reader.readtext(screenshot)
        if (len(result) > 0):
            result = result[0]
            # result is [bbox, text, confidence]
            game_time = result[1].replace(".", ":") 
            
        outputs = {}
        for timer in timers:
            if timer.started < timer.max_instances:
                found, output = timer.detect_image(s)
                outputs = outputs | output
                if found:
                    started = timer.start_timer(output)
                    if (started and game_time and timer.history):
                        # string_time.rjust(7)
                        history[time.time()] = f"{game_time} {timer.name}"
                        
        conf_win.write(f"OCR Time: {game_time}")
        # parse dota 2 timer (5:36:30 h:m:s or 6:30 h:m)
        actual_time = game_time.split(":")
        # check if length is 3 and all parts are numbers
        if not all([part.isdigit() for part in actual_time]):
            actual_time = None
        elif len(actual_time) == 3:
            actual_time = datetime.timedelta(hours=int(actual_time[0]), minutes=int(actual_time[1]), seconds=int(actual_time[2]))
        elif len(actual_time) == 2:
            actual_time = datetime.timedelta(hours=0, minutes=int(actual_time[0]), seconds=int(actual_time[1]))
        conf_win.write(f"Date Time Converted: {actual_time}")
        conf_win.write(f"Confidences:")
        global_game_timedelta = actual_time if actual_time else global_game_timedelta
        longest_image = max([len(image) for image in outputs.keys()])
        # height
        lines, cols = conf_win.getmaxyx()
        for image, confidence in outputs.items():
            padded_image = image.ljust(longest_image)
            total_length = cols - 2 * BORDER_WIDTH - 2 * X_OFFSET
            conf_win.write(progress_bar(confidence, padded_image, total_length, showPercentage=True))
            
        # start a new game if we see early game time
        starting_times = ["0:00", "0:01", "0:02", "0:03", "0:04", "0:05"]
        latest_entry_key = sorted(history.keys())[-1] if history else None
        print(f"Latest entry key: {latest_entry_key}")
        print(f"Latest entry: {history[latest_entry_key]}")
        print(f"Starting times: {starting_times}", history[latest_entry_key].startswith('0'))
        if latest_entry_key and any(starting_time in history[latest_entry_key] for starting_time in starting_times) and not history[latest_entry_key].startswith('0'): # we can start a new game
            history[time.time()] = "-" * (x - 2 * BORDER_WIDTH - 2 * X_OFFSET)
            history[time.time() + 1] = f"{game_time} New Game"
            for timer in timers:
                timer.reset()
            
        conf_win.finishWrite()
        
        return game_time


    
    
class WindowGrid:
    def __init__(self, stdscr: curses._CursesWindow, x, y):
        """
        Create a grid of windows x by y, with the main window being stdscr. Rescale windows to fit the screen when resized.
        """
        self.windows = list()
        self.stdscr = stdscr
        self.lines, self.cols = self.stdscr.getmaxyx()
        self.x = x
        self.y = y
        self.windowWidth = self.cols / x
        self.windowHeight = self.lines / y
        self.windowBounds = dict()
    
    def resize(self, lines, cols):
        self.lines, self.cols = lines, cols
        self.windowWidth = self.cols / self.x
        self.windowHeight = self.lines / self.y
        for window in self.windows:
            self._resizeWindow(window)
    
    def _resizeWindow(self, window: TerminalWindow):
        bounds = self.windowBounds[window]
        grid_x, grid_y, cell_width, cell_height = bounds
        nlines = self.windowHeight * cell_height
        ncols = self.windowWidth * cell_width
        begin_y = self.windowHeight * grid_y
        begin_x = self.windowWidth * grid_x
        
        print(f"Resizing window to {int(nlines)}x{int(ncols)} at {int(begin_y)}, {int(begin_x)}")
        window.resize(int(nlines), int(ncols))
        window.mvwin(int(begin_y), int(begin_x))
    
    def resizeWindow(self, window: TerminalWindow, grid_x, grid_y, cell_width = 1, cell_height = 1):
        if grid_x and grid_y:
            self.windowBounds[window] = (grid_x, grid_y, cell_width, cell_height)
        else:
            grid_x, grid_y, _, _ = self.windowBounds[window]
            self.windowBounds[window] = (grid_x, grid_y, cell_width, cell_height)
        self._resizeWindow(window)
    
        
    def addWindow(self, grid_x = 0, grid_y = 0, cell_width = 1, cell_height = 1) -> TerminalWindow:
        """
        Add a window to the grid at position x, y with width and height in grid cells.
        In a 3x3 grid, the top left window would be at 0, 0 with width 1 and height 1.
        A window that takes the top row is at 0, 0 with width 3 and height 1.
        """
        if (len(self.windows) > self.x * self.y):
            raise Exception("Too many windows")
        # if (grid_x + cell_width > self.x or grid_y + cell_height > self.y):
        #     raise Exception("Window out of bounds", grid_x, grid_y, cell_width, cell_height)
        if (cell_width < 1 or cell_height < 1):
            raise Exception("Window too small")
        if (cell_width > self.x or cell_height > self.y):
            raise Exception("Window too large")
        # TODO: check for overlap
        
        nlines = self.windowHeight * cell_height
        ncols = self.windowWidth * cell_width
        
        begin_y = self.windowHeight * grid_y
        begin_x = self.windowWidth * grid_x
        if (cell_width > 1 and grid_x + cell_width == self.x):
            # last window in row, take up remaining space
            ncols += self.cols % self.x
        if (cell_height > 1 and grid_y + cell_height == self.y):
            # last window in column, take up remaining space
            nlines += self.cols % self.y
            
            
        window = TerminalWindow(int(nlines), int(ncols), int(begin_y), int(begin_x))
        self.windows.append(window)
        self.windowBounds[window] = (grid_x, grid_y, cell_width, cell_height)
        return window


class SelfGrowingWindowGrid(WindowGrid):
    """
    Grid that only takes anchor points and grows windows to fill the screen.
    """
    def growWindows(self):
        # sort windows by y, then x
        self.windows.sort(key=lambda x: (self.windowBounds[x][1], self.windowBounds[x][0]), reverse=True)
        
        lines, cols = self.stdscr.getmaxyx()
        for window in self.windows:
            bounds = self.windowBounds[window]
            grid_x, grid_y, cell_width, cell_height = bounds
            anchor_x = self.windowWidth * grid_x
            anchor_y = self.windowHeight * grid_y
            
            # reset cell width and height
            cell_width = 1
            cell_height = 1
            
            # grow until we hit lines
            while anchor_y + self.windowHeight * cell_height < lines:
                cell_height += 1
            # grow until we hit cols
            while anchor_x + self.windowWidth * cell_width < cols:
                cell_width += 1
            
            # update window bounds
            self.windowBounds[window] = grid_x, grid_y, cell_width, cell_height
            
            
            lines, cols = min(anchor_y, lines), max(anchor_x, cols)
        
        # resize all windows
        for window in self.windows:
            self._resizeWindow(window)
    
    def _checkOverlap(self, window: TerminalWindow, max_x, max_y):
        
        anchor_y, anchor_x = window.getbegyx()
        
        for other_window in self.windows:
            if other_window == window:
                continue
            other_bounds = self.windowBounds[other_window]
            other_grid_x, other_grid_y, other_cell_width, other_cell_height = other_bounds
            other_anchor_x = self.windowWidth * other_grid_x
            other_anchor_y = self.windowHeight * other_grid_y
            
            other_max_x = other_anchor_x + self.windowWidth * other_cell_width
            other_max_y = other_anchor_y + self.windowHeight * other_cell_height
                                
            if (anchor_x < other_max_x and anchor_y < other_max_y and
                max_x > other_anchor_x and max_y > other_anchor_y):
                return True
        return False
    
    def growWindowsWidthFirst(self):
        self.windows.sort(key=lambda x: (self.windowBounds[x][0], self.windowBounds[x][1])) # sort by x, then y
        lines, cols = self.stdscr.getmaxyx()
        for window in self.windows:
            anchor_y, anchor_x = window.getbegyx()
            grid_x, grid_y, cell_width, cell_height = self.windowBounds[window]
            
            # Grow width we hit cols or overlap with another window
            while anchor_x + self.windowWidth * cell_width < cols:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width
                
                max_x += self.windowWidth
                
                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_width += 1

            # Grow height we hit lines or overlap with another window
            while anchor_y + self.windowHeight * cell_height < lines:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width
                
                max_y += self.windowHeight
                
                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_height += 1
            
            # Update window bounds
            self.windowBounds[window] = grid_x, grid_y, cell_width, cell_height
        # resize all windows
        for window in self.windows:
            self._resizeWindow(window)
    
    def growWindowsHeightFirst(self):
        self.windows.sort(key=lambda x: (self.windowBounds[x][1], self.windowBounds[x][0])) # sort by y, then x
        lines, cols = self.stdscr.getmaxyx()
        for window in self.windows:
            anchor_y, anchor_x = window.getbegyx()
            grid_x, grid_y, cell_width, cell_height = self.windowBounds[window]
            
            # Grow height we hit lines or overlap with another window
            while anchor_y + self.windowHeight * cell_height < lines:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width
                
                max_y += self.windowHeight
                
                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_height += 1
            
            # Grow width we hit cols or overlap with another window
            while anchor_x + self.windowWidth * cell_width < cols:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width
                
                max_x += self.windowWidth
                
                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_width += 1

            # Update window bounds
            self.windowBounds[window] = grid_x, grid_y, cell_width, cell_height
        # resize all windows
        for window in self.windows:
            self._resizeWindow(window)
            
            
            
            

class TerminalWindow:
    def __getattr__(self, item):
        return self.window.__getattribute__(item)
    
    def __init__(self, nlines, ncols, begin_y, begin_x):
        self.disabled = False
        self.window = curses.newwin(nlines, ncols, begin_y, begin_x)
        self.height, self.width = self.window.getmaxyx()
        self.x_offset = X_OFFSET
        self.y_offset = Y_OFFSET
        self.border_width = BORDER_WIDTH
        # TODO: writeable area is   x[BORDER_WIDTH + X_OFFSET] to x[ncols - BORDER_WIDTH - X_OFFSET]
        #                           y[BORDER_WIDTH + Y_OFFSET] to y[nlines - BORDER_WIDTH - Y_OFFSET]
    
    def resize(self, nlines, ncols):
        self.window.resize(nlines, ncols)
        self.height, self.width = nlines, ncols # bookkeeping
    
    def write(self, text):
        y, x = self.window.getmaxyx()
        # offset from each border
        if not self.disabled:
            # split text into lines of correct length and write them
            length = self.width - self.x_offset * 2 - self.border_width * 2
            if length:
                lines = [text[i:i+length] for i in range(0, len(text), length)]
                # print(lines)
                for line in lines:
                    self._write(line)
    
    def writeProgressBar(self, progress: float, message: str, showPercentage: bool = False, lsep = '[', rsep = ']', fill='■'):
        """
        Create a progress bar with a message and a percentage.
        Will write a progress bar to the full width of the window."""
        if not self.disabled:
            percent = f"{progress:.2%}"
            percent = percent.rjust(7)
            
            return_size = self.width - self.x_offset * 2 - self.border_width * 2
            
            current_message_size = len(message) + len(lsep) + len(rsep) + len(fill) + 1 # +1 for the space
            
            if showPercentage:
                current_message_size += len(percent) + 1 # +1 for the space
            progress_bar_size = return_size - current_message_size
            progress = int(progress * progress_bar_size)
            ret = f"{lsep}{fill * progress}{' ' * (progress_bar_size - progress)}{rsep}"
            
            if showPercentage:
                ret += f" {percent}"
            ret += f" {message}"
            return ret
    
    def writeLine(self, character):
        if not self.disabled:
            self._write(character * (self.width - self.x_offset * 2 - self.border_width * 2))
    
    def _write(self, text):
        # strip out newlines
        text = text.replace("\n", "")
        if not self.disabled and text:
            if (len(text) > self.width - self.x_offset * 2 - self.border_width * 2):
                raise Exception("Text too long for line")
            self.y_offset += 1
            if self.y_offset > self.height - self.border_width: #
                self.y_offset = Y_OFFSET
                # raise Exception("Reached the end of the window")
            self.window.addstr(self.y_offset, self.x_offset, f"{text}")
    
    def finishWrite(self, reset: bool = True):
        if not self.disabled:
            if reset:
                self.y_offset = Y_OFFSET
            self.window.border()
            self.window.refresh()



class TormentorTimer(Dota2_Timer):
    # 2 concurrent timers, one for each tormentor. The radiant/dire tormentor respawns every 10 minutes.
    def __init__(self, name: str, cooldowns: Respawn_Duration):
        super().__init__(name, cooldowns)
        self.trigger_images([os.path.join("tormentor/images", img) for img in os.listdir("tormentor/images")])
        self.search_area(*events_window)
        
        # TODO: have respawn sound based on radiant/dire in filename
        self.history = True
        self.confidence = 0.85
        self.max_instances = 2
        # TODO: use self.cooldowns when starting timer
    def start_timer(self, output):
        """Start the timer based on the detected image."""
        if self.disabled:
            return False
        if self.started < self.max_instances:
            self.started += 1
            self.duration = self.cooldowns.tormentor_cooldown()
            if "radiant" in self.detected_image_name and not "radiant" in self.name.lower():
                self.name = f"Radiant Tormentor"
                self.audio_alert('./tormentor/radiant_tormentor_respawn.mp3')
            elif "dire" in self.detected_image_name and not "dire" in self.name.lower():
                self.name = f"Dire Tormentor"
                self.audio_alert('./tormentor/dire_tormentor_respawn.mp3')
            elif len(self.timers) > 0:
                # see if confidence for the opposite of last detected tormentor is high
                # output[image] = max_conf
                
                for image, confidence in output.items():
                    if confidence > self.confidence:
                        if "radiant" in image and not "radiant" in self.name.lower():
                            self.name = f"Radiant Tormentor"
                            self.audio_alert('./tormentor/radiant_tormentor_respawn.mp3')
                        elif "dire" in image and not "dire" in self.name.lower():
                            self.name = f"Dire Tormentor"
                            self.audio_alert('./tormentor/dire_tormentor_respawn.mp3')
                last_started_time = sorted(self.timers.keys())[-1]
                since_last = time.time() - last_started_time
                # print(f"Timer started {since_last:.0f}s ago")
                if since_last > 60:
                    new_timer = Timer(self.duration - since_last, self.finished)
                    new_timer.daemon = True
                    self.timers[time.time()] = new_timer
                    new_timer.start()
                    return True
                else:
                    self.started -= 1     
                    return False
                
            new_timer = Timer(self.duration, self.finished)
            new_timer.daemon = True
            self.timers[time.time()] = new_timer
            new_timer.start()
            return True
        
class RoshanTimer(Dota2_Timer):
    def __init__(self, name: str, cooldowns: Respawn_Duration):
        super().__init__(name, cooldowns)
        self.trigger_images(['roshan\\roshan.png'])
        self.search_area(*events_window)
        self.audio_alert('./roshan/roshan_respawn.mp3')
        self.history = True
        self.confidence = 0.95
        def callback(self: RoshanTimer):
            self.duration = cooldowns.roshan_cooldown()
        self.onDetected(callback)
    # TODO: roshan has a 3 minute window to respawn, so we can have another timer for that

# TODO:
# class RuneTimer(Dota2_Timer):
    # a bottle is in one of two states: a rune or a normal bottle
    # when we detect a normal bottle, always cancel the rune timer and start checking for a rune. stop the normal bottle timer
    # when we detect a rune, start a timer, then start checking for normal bottle
    
    
    

def main(stdscr: curses._CursesWindow):
    history = {}
    tick = time.time()
    cooldowns = Respawn_Duration(Mode.DEBUG if args.debug else Mode.TURBO if args.turbo else Mode.NORMAL)
    curses.curs_set(0)
    check_interval = 1 # seconds
    refresh_interval_curses =  args.refresh_interval_curses or 100 # milliseconds
    curses.resize_term(70, 200) # lines, cols
    
    # stdscr.keypad(True)
    stdscr.nodelay(True)
    # stdscr.timeout(refresh_interval_curses)  # Refresh every 
    


    # Create windows
    GRID_X = 10
    GRID_Y = 10
    window_grid = SelfGrowingWindowGrid(stdscr, GRID_X, GRID_Y)
    timer_win = window_grid.addWindow(0, 0)
    conf_win = window_grid.addWindow(0, 6)
    if (cooldowns.currentMode() == Mode.DEBUG):
        conf_win.disabled = False
    else:
        conf_win.disabled = True
    
    history_win = window_grid.addWindow(8, 0)
    window_grid.growWindowsHeightFirst()
    
    
    
    # Bottle rune timer
    rune_timer = Dota2_Timer('Rune', cooldowns)
    rune_timer.trigger_images([os.path.join("bottle\\runes", img) for img in os.listdir("bottle\\runes")])
    rune_timer.timeout(cooldowns.rune_cooldown() - 15)  # warn 15 seconds before expiry
    rune_timer.search_area(*items_window)
    def rune_detected(self: Dota2_Timer):
        rune = self.detected_image_name.split("\\")[-1].split(".")[0]
        self.name = f"{rune} Rune"
        # timeout:
        self.timeout(cooldowns.rune_cooldown())
        reset_rune.started = False # start checking for normal bottle
    rune_timer.onDetected(rune_detected)
    rune_timer.audio_alert('./bottle/rune_expiring.mp3')
    def rune_finished(self: Dota2_Timer):
        reset_rune.started = True # stop checking for normal bottle
    rune_timer.onFinish(rune_finished)
    rune_timer.disabled = True # don't check for runes until we see bottle
    
    reset_rune = Dota2_Timer('Bottle', cooldowns)
    reset_rune.trigger_images([os.path.join("bottle\\normal", img) for img in os.listdir("bottle\\normal")])
    reset_rune.search_area(*items_window)
    def normal_bottle_detected(self: Dota2_Timer):
        if (rune_timer.disabled):
            rune_timer.disabled = False
        if (rune_timer.started):
            rune_timer.reset()
        reset_rune.started = 1 # start checking for normal bottle
        # TODO: make classes for all these timers
    # no duration, only the onFinish callback will run
    reset_rune.onFinish(normal_bottle_detected)

    tormentor_timer = TormentorTimer('Tormentor', cooldowns)
    roshan_timer = RoshanTimer('Roshan', cooldowns)
    game_time = "0:00"
    timers: list[Dota2_Timer] = [tormentor_timer, roshan_timer, rune_timer, reset_rune]
    queue = Queue()
    windows = [conf_win, timer_win, history_win]
        
    
    
    while True:
        lines, cols = stdscr.getmaxyx()
        if stdscr.getch() == curses.KEY_RESIZE:
            print(f"Resizing to {lines}x{cols}")
            curses.resize_term(lines, cols)
            window_grid.resize(lines, cols)
            continue
            

        lines, cols = history_win.getmaxyx()
        if time.time() - tick > check_interval:
            if (queue.empty()): # don't start a new thread if the previous one is still running
                queue.put((timers, conf_win, history, game_time, lines, cols))
                thread = RunImageRecognition(queue)
                thread.daemon = True
                thread.start()
            tick = time.time()
            
        
            
        timer_win.clear()
        timer_win.write(f"q=quit, r=reset, m=mode, i=+ d=-")
        timer_win.write(f"{cooldowns.currentMode()}, i={check_interval}")
        timer_win.write(f"Game Time: {global_game_timedelta}")
        timer_win.write(f"Timers:")
        longest_name = max([len(timer.name) for timer in timers])
        for timer in timers:
            if timer.started and timer.duration > 0:
                # timer.items is a map of timer_started_time -> timer
                for started_time, scheduledTimer in timer.timers.items():
                    time_remaining = timer.duration - (time.time() - started_time)
                    if (time_remaining > 0):
                        lines, cols = conf_win.getmaxyx()
                        progress_bar_length = cols - 2 * BORDER_WIDTH - 2 * X_OFFSET
                        message = f"{time_remaining:.0f}s {''.rjust(longest_name)}"
                        timer_win.writeProgressBar(1 - (time_remaining / timer.duration), message, lsep='┌', rsep='┐', fill='█')
                        
                        timer_win.write(progress_bar(1 - (time_remaining / timer.duration), message,                                                    progress_bar_length, lsep='┌', rsep='┐', fill='█'))
                        timer_win.write(progress_bar(1 - (time_remaining / timer.duration), message,                                                    progress_bar_length, lsep='|', rsep='|', fill='█'))
                        timer_win.write(progress_bar(1 - (time_remaining / timer.duration), f"{time_remaining:.0f}s {timer.name.rjust(longest_name)}",  progress_bar_length, lsep='|', rsep='|', fill='█'))
                        timer_win.write(progress_bar(1 - (time_remaining / timer.duration), message,                                                    progress_bar_length, lsep='|', rsep='|', fill='█'))
                        timer_win.write(progress_bar(1 - (time_remaining / timer.duration), message,                                                    progress_bar_length, lsep='└', rsep='┘', fill='█'))
        timer_win.finishWrite()
        
        
        # limit history window entries
        while history and len(history) > history_win.height - 2 * BORDER_WIDTH - 2 * Y_OFFSET - 2:
            # delete the entry with the oldest time
            oldest_time = sorted(history.keys())[0]
            del history[oldest_time]
        
        history_win.write("History:" + datetime.datetime.now().strftime("%H:%M:%S")) # .%f
        for timestamp, event in history.items():
            history_win.write(f"{event}")
        # TODO: game time is the ground truth, set off the timers based on OCR from game time
        # TODO: handle pauses
            
        

            
        history_win.finishWrite()
        
        

        try:
            key = stdscr.getkey()
            # Exit if 'q' is pressed
            if  key == 'q':
                break
            if key == 'r':
                history = {}
                for timer in timers:
                    timer.reset()
            if key == 'm':
                print('Changing mode')
                cooldowns.next()
                if cooldowns.currentMode() == Mode.DEBUG:
                    # height, width
                    # give 2/3 of the height to the timer window
                    window_grid.resizeWindow(timer_win, 0, 0, 8, 4)
                    conf_win.disabled = False
                else:
                    # give all the height to the timer window
                    window_grid.resizeWindow(timer_win, 0, 0, 8, 10)
                    conf_win.disabled = True
            if key == 'i':
                check_interval = min(10, check_interval + 1)
            if key == 'd':
                check_interval = max(0, check_interval - 1)
        except curses.error:
            pass
            
    curses.endwin()

        
        
from curses import wrapper
if __name__ == "__main__":
    wrapper(main)
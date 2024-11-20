from __future__ import annotations
import asyncio
from collections import deque
import datetime
import os
from typing import Optional
import pyautogui
import cv2 as cv
import numpy as np
import easyocr
import threading
import time
import curses
from queue import Queue
from timers.Bottle_Timer import Bottle_Timer
from timers.Dota2_Timer import Dota2_Timer
from timers.Rune_Timer import Rune_Timer
from timers.Tormentor_Timer import TormentorTimer
from timers.Roshan_Timer import RoshanTimer
from utils.screen_areas import area_time
from utils.terminal import TerminalWindow, SelfGrowingWindowGrid
from utils.history import TimestampedHistory
from utils.constants import GRID_X, GRID_Y
import pickle

from utils.settings import settings

global_game_timedelta = datetime.timedelta(hours=0, minutes=0, seconds=0)



async def process_timer(timer: Optional[Dota2_Timer], s: cv.typing.MatLike, global_game_timedelta: datetime.timedelta, history: TimestampedHistory):
    output = {}
    if not timer or timer.disabled:
        return output
    
    if global_game_timedelta.total_seconds() > 90:
        skipped = False
        for started_time, delayTimer in timer.timers.copy().items():
            # check if timer was started in the future
            if started_time > global_game_timedelta:
                if timer.started == 1: # can just reset the timer
                    timer.reset()
                else:
                    # remove the timer manually without any triggers, keep any other timers
                    delayTimer.cancel()
                    timer.timers.pop(started_time)
                    timer.started -= 1 if timer.started > 0 else 0
                skipped = True
        if skipped:
            return output
    
    if timer.started < timer.max_instances:
        found, output = await timer.detect_image(s)
        if found:
            started = timer.start_timer_timedelta(
                output,
                (
                    global_game_timedelta
                    if not settings.use_real_time
                    else datetime.timedelta(seconds=time.time())
                ),
            )
            if started and timer.history:
                expiration_time_ingame = (global_game_timedelta + datetime.timedelta(seconds=timer.duration()))
                timeouts = [expiration_time_ingame]
                if "Roshan" in timer.name:
                    # Roshan has a 3 minute window to respawn
                    window_end = expiration_time_ingame + datetime.timedelta(minutes=3)
                    timeouts.append(window_end)
                history.add_event(
                    timer.name,
                    global_game_timedelta,
                    timeouts
                )
    return output



c = threading.Condition()


class RunImageRecognition(threading.Thread):
    def __init__(self, queue: Queue[list, str, int], *args, **kwargs):
        super(RunImageRecognition, self).__init__(*args, **kwargs)
        self.queue = queue
        self.reader = easyocr.Reader(["en"])
        self.is_main_menu = False
        self.float = 1.0
        self.side = 0
        self.time_interval_history = [0, 0]
        self.flipflop = 0
        

    def run(self):
        # mutex
        while True:
            if not self.queue.empty():
                asyncio.run(self.run_async())
                
    async def run_async(self):
        beforescreenshot = time.time()
        s = pyautogui.screenshot()
        afterscreenshot = time.time()
        # TODO: stack warning at 50s
        
        s = cv.cvtColor(np.array(s), cv.COLOR_RGB2BGR)
        timers, windows, history = self.queue.get()
        
        conf_win, timer_win, history_win = windows
        
        
        conf_win.startWrite()
        # blink a square, use either solid line block or nothing in terms of ascii
        if self.flipflop:
            conf_win.write("▓")
            self.flipflop = 0
        else:
            conf_win.write(" ")
            self.flipflop = 1
            
        
        conf_win.write("Screenshot taken in {:.2f}s".format(afterscreenshot - beforescreenshot))
        jobs = [self.detect_game_time(s, timers, conf_win, history)]
        if not self.is_main_menu:
            jobs.append(self.run_image_detection(s, timers, windows, history))
        await asyncio.gather(*jobs)
        total = time.time() - beforescreenshot
        conf_win.write(f"Total: {total:.2f}s")
        conf_win.finishWrite()

    async def detect_game_time(self, screenshot: cv.typing.MatLike, timers: list[Dota2_Timer], conf_win: TerminalWindow, history: TimestampedHistory):
        before = time.time()        
        global global_game_timedelta
        game_time = "0:00"

        # get the game time
        screenshot = screenshot[
            area_time[1] : area_time[1] + area_time[3],
            area_time[0] : area_time[0] + area_time[2],
        ]
        result = self.reader.readtext(screenshot, detail=0)
        if len(result) > 0:
            result = result[0]
            game_time = result.replace(".", ":")
        self.is_main_menu = "LEAR" in game_time or "0:00" in game_time
        conf_win.write(f"Game Time (before parsing): {'No game visible, skipping detection...' if self.is_main_menu else game_time}")
        if self.is_main_menu:
            settings.image_detection_interval = min(0.2 + settings.image_detection_interval, 10.0)
            return {}
        # parse dota 2 timer (5:36:30 h:m:s or 6:30 h:m)
        actual_time = game_time.split(":")
        # check if length is 3 and all parts are numbers
        if all([part.isdigit() for part in actual_time]) and len(actual_time) > 1 and len(actual_time) < 4:
            if len(actual_time) == 3:
                actual_time = datetime.timedelta(
                    hours=int(actual_time[0]),
                    minutes=int(actual_time[1]),
                    seconds=int(actual_time[2]),
                )
            elif len(actual_time) == 2:
                actual_time = datetime.timedelta(
                    hours=0, minutes=int(actual_time[0]), seconds=int(actual_time[1])
                )
        else: 
            actual_time = None
            
        # Tune the timing of the image detection so that it doesn't run too often or too rarely
        if actual_time:
            elapsed_time = (actual_time - global_game_timedelta).total_seconds()
            # Convert to 1/n of a second
            if settings.image_detection_interval < 1 and settings.image_detection_interval > 0:
                n = 1 / settings.image_detection_interval
                conf_win.write(f"Approx {n:.1f} times a second")
            else:
                n = settings.image_detection_interval
                conf_win.write(f"Approx {n:.1f} seconds")
                
            if elapsed_time < 0:
                # could be at the start of a game, scrolling around the replayF
                elapsed_time = abs(elapsed_time)
                if global_game_timedelta.total_seconds() < 90 and not history.new_game: # game starts counting down from 1:30
                    # start a new game
                    timers = [timer.reset() for timer in timers]
                    history.start_new_game()
                    
                
                

            # Tune the image detection interval so that we roughly keep pace with the in-game time
            if  elapsed_time > 1 and settings.image_detection_interval > 0:
                # if the difference is more than 2 seconds, try to decrease image detection interval rapidly
                new_interval = (settings.image_detection_interval - self.float) if settings.image_detection_interval <= 2.0 else 0
                conf_win.write(f"Decreasing image detection interval to {new_interval:.3f}", 3)
                
                if (abs(sum(self.time_interval_history)) == 0 and self.float > 0.001):
                    self.float = abs(self.float / 2)
                self.side -= 1
                self.time_interval_history.append(-1)
                settings.image_detection_interval = max(0, new_interval)
            elif elapsed_time < 2 and settings.image_detection_interval < 4:
                new_interval = settings.image_detection_interval + self.float
                conf_win.write(f"Increasing image detection interval to {new_interval:.3f}", 2)
                if (abs(sum(self.time_interval_history)) == 0 and self.float > 0.001):
                    self.float = abs(self.float / 2)
                # if the difference is less than 1 second, try to increase image detection interval
                settings.image_detection_interval = min(4.0, new_interval)
                self.side += 1
                self.time_interval_history.append(1)
                
            # limit history to 2 elements
            if (len(self.time_interval_history) > 2):
                self.time_interval_history.pop(0)
            if abs(self.side) == 3:
                self.float = min(self.float * 10, 0.5) # move up a decimal place
                conf_win.write("Resetting image detection interval", 1)
                self.side = 0
            
            
        global_game_timedelta = actual_time if actual_time else global_game_timedelta
        conf_win.write(f"Game Time (after parsing): {global_game_timedelta}")
        after = time.time()
        conf_win.write(f"Game Time detection: {after - before:.2f}s")
        
        
        return {}


    async def run_image_detection(self, s, timers: list[Dota2_Timer], windows: list[TerminalWindow], history: TimestampedHistory):
        beforeImageDetection = time.time()
        global global_game_timedelta
        conf_win, timer_win, history_win = windows
        
        
        
        if (global_game_timedelta.total_seconds() < 5 and not history.new_game):
            # start a new game
            timers = [timer.reset() for timer in timers]
            history.start_new_game()

        # detect images for timer triggers
        tasks = [process_timer(timer, s, global_game_timedelta, history)
                 for timer in timers 
                    if 
                        timer and 
                        not timer.disabled
                        # and timer.started < timer.max_instances # moved, now done inside process_timer
                        and (timer.spawn_at() <= global_game_timedelta or settings.use_real_time)
                ]
        
        outputs = await asyncio.gather(*tasks)
        outputs = {k: v for output in outputs for k, v in output.items()}
        
        afterImageDetection = time.time()
        conf_win.write(f"Image detection: {afterImageDetection - beforeImageDetection:.2f}s")
        conf_win.writeLine("-")
        longest_image = max([len(image) for image in outputs]) if len(outputs) > 0 else 0
        for image, (confidence, time_taken) in outputs.items():
            padded_image = image.ljust(longest_image)
            padded_image += f" {time_taken:.2f}s"
            conf_win.writeProgressBar(confidence, padded_image, showPercentage=True)
        # TODO: extract some helper functions for state management, boilerplate messages. Make a debug window where we can print stuff.
        # TODO: fix window sizing, only take into account enabled windows




# TODO:
# class RuneTimer(Dota2_Timer):
# a bottle is in one of two states: a rune or a normal bottle
# when we detect a normal bottle, always cancel the rune timer and start checking for a rune. stop the normal bottle timer
# when we detect a rune, start a timer, then start checking for normal bottle
def fstr(template):
    return eval(f'f"""{template}"""')

def displayTimers(timer_win: TerminalWindow,timers: list[Dota2_Timer]):
    global global_game_timedelta
    timer_win.startWrite()

    longest_name = max([len(timer.name) for timer in timers])
    for timer in timers:
        if (not timer):
            continue
        if timer.started and timer.duration() > 0:
            finished_accum = 0
            for started_time, scheduledTimer in timer.timers.items():
                time_remaining = 0
                if not settings.use_real_time:
                    # alternative handling, use timedelta
                    time_remaining = timer.duration() - (
                        global_game_timedelta.total_seconds()
                        - started_time.total_seconds()
                    )
                    if time_remaining > timer.duration():
                        continue # TODO: reset timer, but without breaking the dictionary
                    # THICC PROGRESS BAR
                    timer.writeProgressBar(timer_win, time_remaining, longest_name)
                    if time_remaining <= 0:
                        finished_accum += 1
                else:
                    time_remaining = timer.duration() - (time.time() - started_time.total_seconds())
                    if time_remaining > timer.duration():
                        continue # TODO: reset timer, but without breaking the dictionary
                    if time_remaining > 0:
                        # THICC PROGRESS BAR
                        timer.writeProgressBar(timer_win, time_remaining, longest_name)
            if finished_accum:
                timer.finished()
    timer_win.finishWrite()


def main(stdscr: curses._CursesWindow):
    curses.start_color()
    curses.curs_set(0)
    
    # curses.resize_term(60, 165)  # lines, cols
    # curses.use_default_colors()
    # curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    # curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    # curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    # curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    # curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    # curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
    # curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
    # curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)
    
    # init all color pairs from 0 to 255
    for i in range(1, 256):
        curses.init_pair(i, i, curses.COLOR_BLACK)
        
    
    
    tick = time.time() - settings.image_detection_interval # start immediately

    # stdscr.keypad(True)
    # stdscr.nodelay(True)
    stdscr.timeout(settings.refresh_interval_curses)  # Refresh every

    # Create windows
    window_grid = SelfGrowingWindowGrid(stdscr, GRID_X, GRID_Y)
    timer_win = window_grid.addWindow(0, 0)
    
    # color pair testing:
    # window_grid.useGridAndGrow()
    # timer_win.startWrite()
    # for i in range(1, 256):
    #     timer_win.write(f"Color pair {i} ", i)
    #     if i % 42 == 0:
    #         timer_win.x_offset += 20
    #         timer_win.y_offset = 2
    # timer_win.finishWrite()
    # while True:
    #     continue
    
    
    timer_win.header = [
        "q=quit, r=reset, m=mode, i/d=adjust image recognition o/k=adjust UI refresh rate",
        "t=toggle real time, c=toggle confidence window. l=load history",
        "Using {'real time' if settings.use_real_time else 'game time'}",
        "{settings.cooldowns.currentMode()}, image recognition every {settings.image_detection_interval} seconds, UI refresh every {settings.refresh_interval_curses}ms",
        "Timers:",
    ]
    
    conf_win = window_grid.addWindow(0, 6)
    conf_win.header = [
        "Timestamp: {datetime.datetime.now().strftime('%H:%M:%S')}",
    ]
    if settings.show_confidence:
        conf_win.disabled = False
    else:
        conf_win.disabled = True

    history_win = window_grid.addWindow(6, 0)
    history_win.header = [
        "History:",
    ]
    

    
    # window_grid.growWindowsHeightFirst()
    window_grid.useGridAndGrow()


    writable_height = history_win.height - len(history_win.header) - history_win.y_offset * 2
    history = TimestampedHistory(history_win, writable_height)
    


    roshan_timer = RoshanTimer("Roshan")
    tormentor_timer = TormentorTimer("Tormentor")
    rune_timer = Rune_Timer("Rune")
    def rune_detected(self: Dota2_Timer):
        rune = self.detected_image_name.split("\\")[-1].split(".")[0]
        self.name = f"{rune} Rune"
        reset_rune.started = False  # start checking for normal bottle
    def rune_finished(self: Dota2_Timer):
        reset_rune.started = True  # stop checking for normal bottle

    rune_timer.onDetected(rune_detected)
    rune_timer.onFinish(rune_finished)
    
    reset_rune = Bottle_Timer("Bottle")
    def normal_bottle_detected(self: Dota2_Timer):
        if rune_timer.disabled:
            rune_timer.disabled = False
        if rune_timer.started:
            rune_timer.reset()
        reset_rune.started = 1  # start checking for normal bottle
    # no duration, only the onFinish callback will run
    reset_rune.onFinish(normal_bottle_detected)
    
    
    # colors
    roshan_timer.color_pair = 166
    rune_timer.color_pair = 11
    reset_rune.color_pair = 11

    timers: list[Dota2_Timer] = [tormentor_timer, roshan_timer, ]
    
    if settings.rune_timer:
        timers.append(rune_timer)
        timers.append(reset_rune)
    queue = Queue(maxsize=1)
    windows = [conf_win, timer_win, history_win]
    thread = RunImageRecognition(queue)
    thread.daemon = True # kill the thread when the main thread dies
    thread.start()
    

    while True:
        history.writeToWindow(global_game_timedelta)
        # TODO: clear all windows, fix resizing leaving borders inside window
        ch = stdscr.getch()
        if  ch == curses.KEY_RESIZE:
            lines, cols = stdscr.getmaxyx()
            print(f"Resizing to {lines}x{cols}")
            curses.resize_term(lines, cols)
            time.sleep(1) # wait for the terminal to resize, yes it's stupid
            window_grid.resize(lines, cols)
            continue
        if ch == curses.KEY_MOUSE:
            id, x, y, z, bstate = curses.getmouse()
            print(f"Mouse event: {id}, {x}, {y}, {z}, {bstate}")
            

        if time.time() - tick > settings.image_detection_interval:
            try:
                queue.put((timers, windows, history), timeout=0)
            except:
                pass
            tick = time.time()

        displayTimers(timer_win,timers)
        
        try:
            # TODO: 1,2,3: enable/disable timers
            # TODO: 
            key = stdscr.getkey()
            if key == "q":
                if history:
                    # pickle history to file
                    
                    # Load existing history if it exists
                    if os.path.exists("history.pkl"):
                        with open("history.pkl", "rb") as f:
                            previous_history, _  = pickle.load(f)
                            previous_history = deque(previous_history, maxlen=history.max_history)
                    else:
                        previous_history = deque(maxlen=history.max_history)
                    # Merge the current history with the previous history
                    previous_history.extend(history._history)
                    with open("history.pkl", "wb") as f:
                        pickle.dump((previous_history, history.new_game), f)                
                break
            if key == "l":
                if os.path.exists("history.pkl"):
                    # load history from file
                    with open("history.pkl", "rb") as f:
                        history._history, history.new_game = pickle.load(f)
            if key == "r":
                history.clear_history()
                for timer in timers:
                    timer.reset()
            if key == "m":
                # TODO: confidence should only be dependent on settings.show_confidence
                settings.cooldowns.next()
            if key == "c":
                # TODO: handle this by adding/removing window from the grid
                settings.show_confidence = not settings.show_confidence
                conf_win.disabled = not settings.show_confidence
                if settings.show_confidence:
                    # give 4/10 of the height to the timer window
                    window_grid.resizeWindow(timer_win, 0, 0, 6, 6)
                else:
                    # give all the height to the timer window
                    window_grid.resizeWindow(timer_win, 0, 0, 6, 10)
                window_grid.useGridAndGrow()
            if key == "t":
                settings.use_real_time = not settings.use_real_time
            if key == "i":
                settings.image_detection_interval = min(10.0, settings.image_detection_interval + 1)
            if key == "d":
                settings.image_detection_interval = max(0.0, settings.image_detection_interval - 1)
            if key == "o":
                settings.refresh_interval_curses = min(1000, settings.refresh_interval_curses + 10)
            if key == "k":
                settings.refresh_interval_curses = max(10, settings.refresh_interval_curses - 10)
        except curses.error:
            pass
        # curses.napms(1) # will fuck performance of OCR

    curses.endwin()


from curses import wrapper

if __name__ == "__main__":
    wrapper(main)

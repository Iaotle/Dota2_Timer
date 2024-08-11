from __future__ import annotations
import asyncio
import datetime
from typing import Optional
import pyautogui
import cv2 as cv
import numpy as np
import threading
import os
import time
import curses
from queue import Queue
from playsound import playsound
import easyocr
from Dota2_Timer import Dota2_Timer
from Tormentor_Timer import TormentorTimer
from Roshan_Timer import RoshanTimer
from utils.cooldown import Respawn_Duration, Mode
from utils.screen_areas import area_items, area_time
from utils.terminal import TerminalWindow, SelfGrowingWindowGrid
from utils.history import TimestampedHistory
from utils.constants import GRID_X, GRID_Y

from utils.settings import settings

reader = easyocr.Reader(["en"])
global_game_timedelta = datetime.timedelta(hours=0, minutes=0, seconds=0)



async def process_timer(timer: Optional[Dota2_Timer], s: cv.typing.MatLike, global_game_timedelta: datetime.timedelta, history: TimestampedHistory):
    output = {}
    if timer.started < timer.max_instances:
        found, output = await timer.detect_image(s)
        if found:
            started = timer.start_timer_timedelta(
                output,
                (
                    global_game_timedelta
                    if not timer.use_real_time
                    else datetime.timedelta(seconds=time.time())
                ),
            )
            if started and timer.history:
                expiration_time_ingame = (global_game_timedelta + datetime.timedelta(seconds=timer.duration))
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

    def run(self):
        # mutex
        # c.acquire()
        asyncio.run(self.run_image_detection(*self.queue.get()))
        # c.notify()
        # c.release()

    # def detect_game_time(self, screenshot: cv.typing.MatLike, conf_win: TerminalWindow):

    async def run_image_detection(self, timers: list[Dota2_Timer], windows: list[TerminalWindow], history: TimestampedHistory):
        beforetext = time.time()
        conf_win, timer_win, history_win = windows

        s = pyautogui.screenshot()
        s = cv.cvtColor(np.array(s), cv.COLOR_RGB2BGR)
        # time everything

        global global_game_timedelta
        game_time = "0:00"

        # get the game time
        screenshot = s[
            area_time[1] : area_time[1] + area_time[3],
            area_time[0] : area_time[0] + area_time[2],
        ]
        result = reader.readtext(screenshot)
        aftertext = time.time()
        
        if len(result) > 0:
            result = result[0]
            # result is [bbox, text, confidence]
            game_time = result[1].replace(".", ":")
        conf_win.startWrite()
        conf_win.write(f"OCR Time: {game_time}")
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
        
        global_game_timedelta = actual_time if actual_time else global_game_timedelta
        
        if (global_game_timedelta.total_seconds() < 5 and not history.new_game):
            # start a new game
            timers = [timer.reset() for timer in timers]
            history.add_event("New Game", global_game_timedelta)

        afterTimeDetection = time.time()
        # detect images for timer triggers
        tasks = [process_timer(timer, s, global_game_timedelta, history) for timer in timers]
        outputs = await asyncio.gather(*tasks)
        outputs = {k: v for output in outputs for k, v in output.items()}
        
        afterImageDetection = time.time()
        longest_image = max([len(image) for image in outputs]) if len(outputs) > 0 else 0
        for image, (confidence, time_taken) in outputs.items():
            padded_image = image.ljust(longest_image)
            padded_image += f" {time_taken:.2f}s"
            conf_win.writeProgressBar(confidence, padded_image, showPercentage=True)
        conf_win.write(f"Time taken:")
        conf_win.write(f"OCR: {aftertext - beforetext:.2f}s")
        conf_win.write(f"Timestamp creation: {afterTimeDetection - aftertext:.2f}s")
        conf_win.write(f"Image detection: {afterImageDetection - afterTimeDetection:.2f}s")
        conf_win.write(f"Total: {afterImageDetection - beforetext:.2f}s")


        # TODO: extract some helper functions for state management, boilerplate messages. Make a debug window where we can print stuff.

        conf_win.finishWrite()

        return game_time





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
        if timer.started and timer.duration > 0:
            finished_accum = 0
            for started_time, scheduledTimer in timer.timers.items():
                time_remaining = 0
                if not timer.use_real_time:
                    # alternative handling, use timedelta
                    time_remaining = timer.duration - (
                        global_game_timedelta.total_seconds()
                        - started_time.total_seconds()
                    )
                    if time_remaining > timer.duration:
                        continue # TODO: reset timer, but without breaking the dictionary
                    # THICC PROGRESS BAR
                    percentage = 1 - (time_remaining / timer.duration)
                    message = f"{time_remaining:.0f}ings {timer.name.rjust(longest_name)}"
                    timer_win.bigProgressBar(percentage, message, True)
                    if time_remaining <= 0:
                        finished_accum += 1
                else:
                    time_remaining = timer.duration - (time.time() - started_time.total_seconds())
                    if time_remaining > timer.duration:
                        continue # TODO: reset timer, but without breaking the dictionary
                    if time_remaining > 0:
                        # THICC PROGRESS BAR
                        percentage = 1 - (time_remaining / timer.duration)
                        message = f"{time_remaining:.0f}s {timer.name.rjust(longest_name)}"
                        timer_win.bigProgressBar(percentage, message, True)
            if finished_accum:
                timer.finished()
    timer_win.finishWrite()


def main(stdscr: curses._CursesWindow):
    cooldowns = settings.cooldowns
    curses.curs_set(0)
    curses.resize_term(60, 165)  # lines, cols
    check_interval = settings.image_detection_interval  # seconds
    refresh_interval_curses = settings.refresh_interval_curses  # milliseconds
    
    tick = time.time() - check_interval # start immediately

    # stdscr.keypad(True)
    # stdscr.nodelay(True)
    stdscr.timeout(refresh_interval_curses)  # Refresh every

    # Create windows
    window_grid = SelfGrowingWindowGrid(stdscr, GRID_X, GRID_Y)
    timer_win = window_grid.addWindow(0, 0)
    timer_win.header = [
        "q=quit, r=reset, m=mode, i/d=adjust image recognition o/k=adjust UI refresh",
        "Using" + (" real" if settings.use_real_time else " game") + " time",
        # "{cooldowns.currentMode()}, image recognition every {check_interval} seconds, UI refresh every {refresh_interval_curses}ms",
        " Real Time: {datetime.datetime.now()}",
        "Timers:",
    ]
    
    conf_win = window_grid.addWindow(0, 6)
    conf_win.header = [
        "Timestamp: {datetime.datetime.now()}",
        "Confidences:"
    ]
    if settings.show_confidence:
        conf_win.disabled = False
    else:
        conf_win.disabled = True

    history_win = window_grid.addWindow(6, 0)
    history_win.header = ["History:"]
    history = TimestampedHistory(history_win)
    
    window_grid.growWindowsHeightFirst()

    # Bottle rune timer
    rune_timer = Dota2_Timer("Rune", cooldowns, settings.use_real_time)
    rune_timer.trigger_images(
        [os.path.join("bottle\\runes", img) for img in os.listdir("bottle\\runes")]
    )
    rune_timer.timeout(cooldowns.rune_cooldown() - 15)  # warn 15 seconds before expiry
    rune_timer.search_area(*area_items)

    def rune_detected(self: Dota2_Timer):
        rune = self.detected_image_name.split("\\")[-1].split(".")[0]
        self.name = f"{rune} Rune"
        # timeout:
        self.timeout(cooldowns.rune_cooldown())
        reset_rune.started = False  # start checking for normal bottle

    rune_timer.onDetected(rune_detected)
    rune_timer.audio_alert("./bottle/rune_expiring.mp3")

    def rune_finished(self: Dota2_Timer):
        reset_rune.started = True  # stop checking for normal bottle

    rune_timer.onFinish(rune_finished)
    rune_timer.disabled = True  # don't check for runes until we see bottle

    reset_rune = Dota2_Timer("Bottle", cooldowns, settings.use_real_time)
    reset_rune.trigger_images(
        [os.path.join("bottle\\normal", img) for img in os.listdir("bottle\\normal")]
    )
    reset_rune.search_area(*area_items)

    def normal_bottle_detected(self: Dota2_Timer):
        if rune_timer.disabled:
            rune_timer.disabled = False
        if rune_timer.started:
            rune_timer.reset()
        reset_rune.started = 1  # start checking for normal bottle
        # TODO: make classes for all these timers

    # no duration, only the onFinish callback will run
    reset_rune.onFinish(normal_bottle_detected)

    tormentor_timer = TormentorTimer("Tormentor", cooldowns, settings.use_real_time)
    roshan_timer = RoshanTimer("Roshan", cooldowns, settings.use_real_time)
    timers: list[Dota2_Timer] = [tormentor_timer, roshan_timer, rune_timer, reset_rune]
    queue = Queue()
    windows = [conf_win, timer_win, history_win]

    while True:
        history.writeToWindow()
        # TODO: clear all windows, fix resizing leaving borders inside window
        lines, cols = stdscr.getmaxyx()
        if stdscr.getch() == curses.KEY_RESIZE:
            print(f"Resizing to {lines}x{cols}")
            curses.resize_term(lines, cols)
            window_grid.resize(lines, cols)
            continue

        if time.time() - tick > check_interval:
            # if queue.empty():  # don't start a new thread if the previous one is still running
            queue.put((timers, windows, history))
            thread = RunImageRecognition(queue)
            thread.daemon = True # kill the thread when the main thread dies
            thread.start()
            tick = time.time()

        displayTimers(timer_win,timers)
        
        try:
            key = stdscr.getkey()
            if key == "q":
                break
            if key == "r":
                history.clear_history()
                for timer in timers:
                    timer.reset()
            if key == "m":
                print("Changing mode")
                cooldowns.next()
                if cooldowns.currentMode() == Mode.DEBUG:
                    # TODO: handle this by adding/removing window from the grid
                    # window_grid.removeWindow(conf_win)
                    # give 4/10 of the height to the timer window
                    window_grid.resizeWindow(timer_win, 0, 0, 8, 4)
                    conf_win.disabled = False
                else:
                    # give all the height to the timer window
                    window_grid.resizeWindow(timer_win, 0, 0, 8, 10)
                    conf_win.disabled = True
            if key == "i":
                check_interval = min(10, check_interval + 1)
            if key == "d":
                check_interval = max(0, check_interval - 1)
            if key == "o":
                refresh_interval_curses = min(1000, refresh_interval_curses + 10)
            if key == "k":
                refresh_interval_curses = max(10, refresh_interval_curses - 10)
        except curses.error:
            pass
        # curses.napms(refresh_interval_curses) # will fuck performance for some reason

    curses.endwin()


from curses import wrapper

if __name__ == "__main__":
    wrapper(main)

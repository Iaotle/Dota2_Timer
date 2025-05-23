import datetime
import threading
import numpy as np
import pyautogui
import asyncio
import cv2 as cv
import time
from threading import Timer
from playsound import playsound
from utils.cooldown import Mode, Respawn_Duration
from utils.settings import settings
from utils.terminal import TerminalWindow



class Dota2_Timer:
    def __init__(self, name: str):
        self.name = name
        self.images = []
        self.image_files = {}
        self.duration = lambda: 0
        self.search_region = (0, 0, *pyautogui.size())
        self.onFinishedCallback = None
        self.onDetectedCallback = None
        self.started = 0
        self.disabled = False
        self.detected_image_name = None
        self.sound_file = None
        self.confidence = 0.99
        self.timers = dict[datetime.timedelta, Timer]()
        self.history = False
        self.max_instances = 1
        self.found = False
        self.color_pair = 0
        self.spawn_at = lambda: datetime.timedelta(seconds=0)
    
    def writeProgressBar(self, window: TerminalWindow, time_remaining: float, longest_name: int, scheduledTimer: Timer):
        percentage = 1 - (time_remaining / self.duration())
        seconds = "s   " if settings.use_real_time else "ings"
        time_remaining_string = f"{time_remaining:.0f}{seconds}".ljust(9)
        message = f"{time_remaining_string} {self.name.rjust(longest_name)}"        
        window.bigProgressBar(percentage, message, self.color_pair)
        
    def reset(self):
        """Reset the timer to its initial state."""
        self.started = 0
        for timer in self.timers.values():
            timer.cancel()
        self.timers.clear()
        self.disabled = False
        return self

    def trigger_images(self, images):
        """Set the images to trigger the timer on."""
        self.images = images
        for image in images: # preload images
            self.image_files[image] = cv.imread(image, cv.IMREAD_COLOR)

    def timeout(self, timeout):
        """Set the timeout duration function."""
        self.duration = timeout

    def search_area(self, x, y, width, height):
        """Set the search area in the screen."""
        self.search_region = (x, y, width, height)

    def onFinish(self, callback):
        """Set the action to perform after the timer is done."""
        self.onFinishedCallback = callback
    
    def onDetected(self, callback):
        """Set the action to perform when the image is detected."""
        self.onDetectedCallback = callback
        
    def audio_alert(self, file):
        """Set the audio alert to play when the image is detected."""
        self.sound_file = file

    async def detect_image_task(self, image, screenshot):
        output = {}
        start = time.time()
        template = self.image_files[image]
        result = cv.matchTemplate(screenshot, template, cv.TM_CCOEFF_NORMED)
        _, max_conf, _, _ = cv.minMaxLoc(result)
        if max_conf >= self.confidence or settings.cooldowns.currentMode() == Mode.DEBUG :  # Confidence threshold
            self.found = True
            self.detected_image_name = image
        output[image] = (max_conf, time.time() - start)
        return output

    async def detect_image(self, screenshot):
        """Detect an image on the screen within the search area."""
        self.found = False
        outputs = {}
        if self.disabled:
            return self.found, outputs
        x, y, width, height = self.search_region
        screenshot = screenshot[y:y+height, x:x+width]
        tasks = [self.detect_image_task(image, screenshot) for image in self.images]
        outputs = await asyncio.gather(*tasks)
        outputs = {k: v for output in outputs for k, v in output.items()}
        return self.found, outputs
    
    def start_timer_timedelta(self, output, timedelta: datetime.timedelta) -> bool:
        if self.disabled:
            return False
        if self.started < self.max_instances:
            self.started += 1
            if (self.onDetectedCallback):
                self.onDetectedCallback(self)
            # TODO: wrap the Timer in a class, add Name, add Color, add Sound (so each timer can have its own)
            new_timer = Timer(self.duration(), self.finished)
            new_timer.daemon = True
            self.timers[timedelta] = new_timer
            if (settings.use_real_time): # if not using in-game time, use real time
                new_timer.start()
            return True
        return False

    def finished(self):
        """Execute the specified action after the timeout."""
        self.started -= 1 if self.started > 0 else 0
        if self.onFinishedCallback:
            self.onFinishedCallback(self)
        if self.sound_file:
            threading.Thread(target=lambda: playsound(self.sound_file)).start()
        self.timers.pop(min(self.timers.keys()))

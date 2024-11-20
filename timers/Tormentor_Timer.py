from collections import deque
from timers.Dota2_Timer import Dota2_Timer
import os
import time
import datetime
from threading import Timer
from utils.cooldown import Mode
from utils.screen_areas import area_events_truncated
from utils.settings import settings
from utils.terminal import TerminalWindow
import easyocr
import cv2 as cv
import threading
from playsound import playsound

class TormentorTimer(Dota2_Timer):
    # 2 concurrent timers, one for each tormentor. The radiant/dire tormentor respawns every 10 minutes.
    def __init__(self, name: str):
        super().__init__(name)
        self.trigger_images([os.path.join("images\\tormentor", img) for img in os.listdir("images\\tormentor")])
        self.search_area(*area_events_truncated)
        self.timeout(settings.cooldowns.tormentor_cooldown)
        self.history = True
        self.confidence = 0.85
        self.max_instances = 2
        self.spawn_at = settings.cooldowns.tormentor_spawn_at
        self.reader = easyocr.Reader(["en"])
        self.side_history = deque(maxlen=2)
    
        
    
    # modified to OCR the image and detect which team killed the tormentor
    async def detect_image_task(self, image, screenshot):
        output = {}
        start = time.time()
        template = self.image_files[image]
        result = cv.matchTemplate(screenshot, template, cv.TM_CCOEFF_NORMED)
        _, max_conf, _, maxLoc = cv.minMaxLoc(result)
        
        
               
        
        if max_conf >= self.confidence or settings.cooldowns.currentMode() == Mode.DEBUG :  # Confidence threshold
            self.found = True
            # OCR the best match to determine which team killed the tormentor
            detected_image = screenshot[maxLoc[1]:maxLoc[1] + template.shape[0], maxLoc[0]:maxLoc[0] + template.shape[1]]
            result = self.reader.readtext(detected_image, detail=0)
            if len(result) > 0:
                print(result)
                if "dire" in result[0].lower():
                    self.detected_image_name = "Dire Tormentor"    
                else:
                    self.detected_image_name = "Radiant Tormentor"
            output[image] = (max_conf, time.time() - start)
        return output
    
    # TODO: modify to color the tormentor timer based on the team that killed it, and name it accordingly
    def writeProgressBar(self, window: TerminalWindow, time_remaining: float, longest_name: int):
        percentage = 1 - (time_remaining / self.duration())
        seconds = "s   " if settings.use_real_time else "ings"
        time_remaining_string = f"{time_remaining:.0f}".rjust(3)
        
        # fix name and color based on which team killed the tormentor
        name = self.side_history.popleft()
        self.side_history.append(name)
        
        color = 47 if name == "Radiant Tormentor" else 160
        message = f"{time_remaining_string}{seconds} {name.rjust(longest_name)}"        
        window.bigProgressBar(percentage, message, color)
    
    # TODO: fix this to detect both properly
    def start_timer_timedelta(self, output, timedelta: datetime.timedelta) -> bool:
        if self.disabled:
            return False
        if self.started < self.max_instances:
            self.started += 1
            if "Radiant Tormentor" in self.detected_image_name and not "Radiant Tormentor" in self.name:
                self.name = f"Radiant Tormentor"
                self.side_history.append("radiant")
            elif "Dire Tormentor" in self.detected_image_name and not "Radiant Tormentor" in self.name:
                self.name = f"Dire Tormentor"
                self.side_history.append("dire")
            elif len(self.timers) > 0:
                for image, (confidence, time_taken) in output.items():
                    if confidence > self.confidence:
                        if "Radiant Tormentor" in image and not "Radiant Tormentor" in self.name:
                            self.name = f"Radiant Tormentor"
                            self.side_history.append("radiant")
                        elif "Dire Tormentor" in image and not "Dire Tormentor" in self.name:
                            self.name = f"Dire Tormentor"
                            self.side_history.append("dire")
                last_started_time = sorted(self.timers.keys())[-1]
                since_last = timedelta.total_seconds() - last_started_time.total_seconds()
                if since_last > 60:
                    new_timer = Timer(self.duration() - since_last, self.finished)
                    new_timer.daemon = True
                    self.timers[timedelta] = new_timer
                    if (settings.use_real_time):
                        new_timer.start()
                    return True
                else:
                    self.started -= 1     
                    return False
        new_timer = Timer(self.duration(), self.finished)
        new_timer.daemon = True
        self.timers[timedelta] = new_timer
        if (settings.use_real_time):
            new_timer.start()
        return True
    
    def finished(self):
        """Execute the specified action after the timeout."""
        self.started -= 1 if self.started > 0 else 0
        if self.onFinishedCallback:
            self.onFinishedCallback(self)
        side = self.side_history.popleft()
        if side == "radiant":
            self.audio_alert('./audio/tormentor/radiant_tormentor_respawn.mp3')
        else:
            self.audio_alert('./audio/tormentor/dire_tormentor_respawn.mp3')
        if self.sound_file:
            playsound(self.sound_file)
        self.timers.pop(min(self.timers.keys()))
        
    
    def reset(self):
        super().reset()
    # def finished(self):
    #     super().finished()
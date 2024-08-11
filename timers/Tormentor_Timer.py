from Dota2_Timer import Dota2_Timer
import os
import time
import datetime
from threading import Timer
from utils.cooldown import Respawn_Duration, Mode
from utils.screen_areas import area_events
from utils.settings import settings

class TormentorTimer(Dota2_Timer):
    # 2 concurrent timers, one for each tormentor. The radiant/dire tormentor respawns every 10 minutes.
    def __init__(self, name: str):
        super().__init__(name)
        self.trigger_images([os.path.join("images\\tormentor", img) for img in os.listdir("images\\tormentor")])
        self.search_area(*area_events)
        self.duration = settings.cooldowns.tormentor_cooldown
        self.history = True
        self.confidence = 0.85
        self.max_instances = 2
    
    # TODO: fix this to detect both properly
    def start_timer_timedelta(self, output, timedelta: datetime.timedelta) -> bool:
        if self.disabled:
            return False
        if self.started < self.max_instances:
            self.started += 1
            if "radiant" in self.detected_image_name and not "radiant" in self.name.lower():
                self.name = f"Radiant Tormentor"
                self.audio_alert('./audio/tormentor/radiant_tormentor_respawn.mp3')
            elif "dire" in self.detected_image_name and not "dire" in self.name.lower():
                self.name = f"Dire Tormentor"
                self.audio_alert('./audio/tormentor/dire_tormentor_respawn.mp3')
            elif len(self.timers) > 0:
                for image, (confidence, time_taken) in output.items():
                    if confidence > self.confidence:
                        if "radiant" in image and not "radiant" in self.name.lower():
                            self.name = f"Radiant Tormentor"
                            self.audio_alert('./audio/tormentor/radiant_tormentor_respawn.mp3')
                        elif "dire" in image and not "dire" in self.name.lower():
                            self.name = f"Dire Tormentor"
                            self.audio_alert('./audio/tormentor/dire_tormentor_respawn.mp3')
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
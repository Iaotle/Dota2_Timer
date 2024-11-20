import time
from timers.Dota2_Timer import Dota2_Timer
from utils.cooldown import Respawn_Duration
from utils.screen_areas import area_events
from utils.settings import settings
from utils.terminal import TerminalWindow
from playsound import playsound
def _onDetected(self):
    if self.max_instances > 1:
        self.reset()
        self.started = 1
class RoshanTimer(Dota2_Timer):
    def __init__(self, name: str):
        super().__init__(name)
        self.trigger_images(["images\\roshan\\roshan.png"])
        self.search_area(*area_events)
        self.audio_alert(["./audio/roshan/roshan_respawn_3min.mp3", "./audio/roshan/roshan_respawn.mp3"])
        self.history = True
        self.confidence = 0.95
        self.timeout(settings.cooldowns.roshan_cooldown)
        self.played_audio_alert = False
        

            
        self.onDetected(_onDetected)


   
    def writeProgressBar(self, window: TerminalWindow, time_remaining: float, longest_name: int):
        # roshan timer is 8-11 minutes, so we need to calculate progress
        
        
        # percentage_1 = range from 0 to self.duration - 180
        # count up from 0 to 8 minutes
        # 0 minutes = 0%
        # 8 minutes = 100%
        if time_remaining > 180:
            percentage_1 = 1 - (time_remaining - 180) / (self.duration() - 180)
        else:
            percentage_1 = 1 
        
        # should start counting up from 8 to 11 minutes
        # 8 minutes = 0%
        # 11 minutes = 100%
        if time_remaining < 180:
            if not self.played_audio_alert:
                self.played_audio_alert = True
                playsound(self.sound_file[0]) # sound that roshan will respawn within 3 minutes
                self.max_instances = 2 # allow for a second instance of the timer, since roshan might have spawned in this 3 min window
            percentage_2 = 1 - time_remaining / 180
        else:
            self.max_instances = 1
            percentage_2 = 0
        
        # first timer is 8 minutes
        seconds = "s   " if settings.use_real_time else "ings"
        message = f"{time_remaining:.0f}{seconds} {self.name.rjust(longest_name)}"
        # ░	▒	▓	
        window.writeRangeProgressBar(percentage_1, percentage_2, message, False,                                   False, lsep="┌",rsep="┐",fill1="▄", fill2="▄", color_pair1=self.color_pair, color_pair2=self.color_pair)
        window.writeRangeProgressBar(percentage_1, percentage_2, message, False,                                   False, lsep="│",rsep="│",fill1="█", fill2="▒", color_pair1=self.color_pair, color_pair2=self.color_pair)
        window.writeRangeProgressBar(percentage_1, percentage_2, message, False, True if time_remaining < 180 else False, lsep="│",rsep="│",fill1="█", fill2="░", color_pair1=self.color_pair, color_pair2=self.color_pair)
        window.writeRangeProgressBar(percentage_1, percentage_2, message, False,                                   False, lsep="│",rsep="│",fill1="█", fill2="▓", color_pair1=self.color_pair, color_pair2=self.color_pair)
        window.writeRangeProgressBar(percentage_1, percentage_2, message, False,                                   False, lsep="└",rsep="┘",fill1="▀", fill2="▀", color_pair1=self.color_pair, color_pair2=self.color_pair)
        
             
        # TODO: write two segments of the progress bar, one for the time left and one for t+3min
        # the second part needs to be a shaded symbol and not a block: "░"
        
    def finished(self):
        """Execute the specified action after the timeout."""
        self.started -= 1 if self.started > 0 else 0
        if self.onFinishedCallback:
            self.onFinishedCallback(self)
        if self.sound_file:
            playsound(self.sound_file[1]) # ending sound
        self.played_audio_alert = False
        
    def reset(self):
        super().reset()
        self.max_instances = 1
        self.played_audio_alert = False

        
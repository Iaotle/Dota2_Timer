from timers.Dota2_Timer import Dota2_Timer
from utils.cooldown import Respawn_Duration
from utils.screen_areas import area_events
from utils.settings import settings


class RoshanTimer(Dota2_Timer):
    def __init__(self, name: str):
        super().__init__(name)
        self.trigger_images(["images\\roshan\\roshan.png"])
        self.search_area(*area_events)
        self.audio_alert("./audio/roshan/roshan_respawn.mp3")
        self.history = True
        self.confidence = 0.95
        self.timeout(settings.cooldowns.roshan_cooldown)
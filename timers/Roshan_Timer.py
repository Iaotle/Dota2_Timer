from Dota2_Timer import Dota2_Timer
from utils.cooldown import Respawn_Duration
from utils.screen_areas import area_events
from utils.settings import Settings


class RoshanTimer(Dota2_Timer):
    def __init__(self, name: str, settings: Settings):
        super().__init__(name, settings)
        self.trigger_images(["images\\roshan\\roshan.png"])
        self.search_area(*area_events)
        self.audio_alert("./audio/roshan/roshan_respawn.mp3")
        self.history = True
        self.confidence = 0.95
        self.duration = settings.cooldowns.roshan_cooldown
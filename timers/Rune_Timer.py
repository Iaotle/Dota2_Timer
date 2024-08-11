from timers.Dota2_Timer import Dota2_Timer
from utils.settings import settings
import os
from utils.screen_areas import area_items

# rune_timer = Dota2_Timer("Rune", settings)
# rune_timer.trigger_images(
# 	[os.path.join("bottle\\runes", img) for img in os.listdir("bottle\\runes")]
# )
# rune_timer.timeout(cooldowns.rune_cooldown() - 15)  # warn 15 seconds before expiry
# rune_timer.search_area(*area_items)

# def rune_detected(self: Dota2_Timer):
# 	rune = self.detected_image_name.split("\\")[-1].split(".")[0]
# 	self.name = f"{rune} Rune"
# 	# timeout:
# 	self.timeout(cooldowns.rune_cooldown())
# 	reset_rune.started = False  # start checking for normal bottle

# rune_timer.onDetected(rune_detected)
# rune_timer.audio_alert("./bottle/rune_expiring.mp3")

# def rune_finished(self: Dota2_Timer):
# 	reset_rune.started = True  # stop checking for normal bottle

# rune_timer.onFinish(rune_finished)


class Rune_Timer(Dota2_Timer):
    def __init__(self, name: str):
        super().__init__(name)
        self.trigger_images(
            [os.path.join("images\\bottle\\runes", img) for img in os.listdir("images\\bottle\\runes")]
        )
        self.timeout(settings.cooldowns.rune_cooldown() - 15)
        self.search_area(*area_items)
        self.audio_alert("./audio/bottle/rune_expiring.mp3")
        self.disabled = True
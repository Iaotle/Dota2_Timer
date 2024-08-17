from timers.Dota2_Timer import Dota2_Timer
from utils.settings import settings
import os
from utils.screen_areas import area_items

# reset_rune = Dota2_Timer("Bottle")
# reset_rune.trigger_images(
# 	[os.path.join("images\\bottle\\normal", img) for img in os.listdir("images\\bottle\\normal")]
# )
# reset_rune.search_area(*area_items)

# def normal_bottle_detected(self: Dota2_Timer):
# 	if rune_timer.disabled:
# 		rune_timer.disabled = False
# 	if rune_timer.started:
# 		rune_timer.reset()
# 	reset_rune.started = 1  # start checking for normal bottle
# 	# TODO: make classes for all these timers

# # no duration, only the onFinish callback will run
# reset_rune.onFinish(normal_bottle_detected)

class Bottle_Timer(Dota2_Timer):
    def __init__(self, name: str):
        super().__init__(name)
        self.trigger_images(
            [os.path.join("images\\bottle\\normal", img) for img in os.listdir("images\\bottle\\normal")]
        )
        self.search_area(*area_items)


# Bottle rune timer
rune_timer = Dota2_Timer('Rune')
rune_timer.trigger_images([os.path.join("bottle\\runes", img) for img in os.listdir("bottle\\runes")])
rune_timer.timeout(bottle_cooldown - 15)  # warn 15 seconds before expiry
rune_timer.search_area(*items_window)
def rune_detected(self: Dota2_Timer):
	rune = self.detected_image_name.split("\\")[-1].split(".")[0]
	self.name = f"{rune} Rune"
	reset_rune.started = False # start checking for normal bottle
rune_timer.onDetected(rune_detected)
rune_timer.audio_alert('./bottle/rune_expiring.mp3')
def rune_finished(self: Dota2_Timer):
	reset_rune.started = True # stop checking for normal bottle
rune_timer.onFinish(rune_finished)
rune_timer.disabled = True # don't check for runes until we see bottle

reset_rune = Dota2_Timer('Bottle')
reset_rune.trigger_images([os.path.join("bottle\\normal", img) for img in os.listdir("bottle\\normal")])
reset_rune.search_area(*items_window)
def normal_bottle_detected(self: Dota2_Timer):
	if (rune_timer.disabled):
		rune_timer.disabled = False
	if (rune_timer.started):
		rune_timer.timer.cancel()
		rune_timer.started = False
	reset_rune.started = True # start checking for normal bottle
	# TODO: make classes for all these timers
# no duration, only the onFinish callback will run
reset_rune.onFinish(normal_bottle_detected)
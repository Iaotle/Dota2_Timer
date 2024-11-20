import argparse
from utils.cooldown import Mode, Respawn_Duration


class Settings:
    def __init__(self, args):
        self.mode =  Mode.TURBO if args.turbo else Mode.DEBUG if args.debug else Mode.NORMAL
        self.cooldowns = Respawn_Duration(self.mode)
        self.show_confidence = args.show_confidence
        self.image_detection_interval: float = args.image_detection_interval
        self.refresh_interval_curses = args.refresh_interval_curses
        self.use_real_time = args.use_real_time
        self.history_window = None
        self.rune_timer = not args.no_rune_timer

parser = argparse.ArgumentParser(description="Dota 2 Timer")
parser.add_argument("--turbo", action="store_true", help="Turbo mode", default=False)
parser.add_argument(
    "--debug",
    action="store_true",
    help="Debug mode (sets all timers to 20 seconds)",
    default=False,
)
parser.add_argument(
    "--debug_triggers",
    action="store_true",
    help="Debug triggers (fires all triggers)",
)
parser.add_argument(
    "--show_confidence", action="store_true", help="Show model confidence", default=False
)
parser.add_argument(
    "--image_detection_interval", type=int, help="How often to run the image detection (seconds)", default=1
)
parser.add_argument(
    "--refresh_interval_curses",
    type=int,
    help="Refresh interval for the frontend (ms)",
    default=100,
)
parser.add_argument(
    "--use_real_time",
    action="store_true",
    help="Use real time instead of game time",
    default=False,
)

parser.add_argument(
    "--no_rune_timer",
    action="store_true",
    help="Disable rune timer",
    default=False,
)


args = parser.parse_args()
settings = Settings(args)

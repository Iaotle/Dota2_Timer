# Dota 2 Objectives Timer
This was my attempt at fusing together OCR, image recognition, and real-time asynchronous processing in Python to keep track of events in Dota 2.

The events it keeps track of are:
- Bottle runes
- Tormentor kills
- Roshan

I use CV2 library to compare screenshots of Dota 2 to images, and OCR to detect game time. When no game time is detected the app starts to sleep.
The tickrate dynamically adjusts based on the time gap between screenshots, which means you can use it when watching 16x replays and it will accurately
count down the time based on the in-game clock. It also means you can pause, fast-forward, or go backwards in time with no issues!

I use async and perform many optimizations under the hood to make everything efficient, but Python is still Python, so one tick of processing still takes
around 0.2 seconds. Five times a second is plenty for 16x replays. Generally the tool will try to take a screenshot every in-game second. There is a history
window.

Recently, Valve has integrated this functionality into the game along with lots more stats (rune spawns, et cetera) if you purchase Dota Plus.

# Running
Download python, install `curses` and all packages from `requirements.txt`

from __future__ import annotations
import curses
import datetime

import numpy as np # needed for lazy f-string evaluation
from utils.settings import settings  # needed for lazy f-string evaluation


BORDER_WIDTH = 1
X_OFFSET = 4
Y_OFFSET = 2




class TerminalWindow:
    def __getattr__(self, item):
        return self.window.__getattribute__(item)

    def __init__(self, nlines, ncols, begin_y, begin_x):
        self.disabled = False
        self.window = curses.newwin(nlines, ncols, begin_y, begin_x)
        self.height, self.width = self.window.getmaxyx()
        self.x_offset = X_OFFSET
        self.y_offset = Y_OFFSET
        self.border_width = BORDER_WIDTH
        self.header = []
        # TODO: writeable area is   x[BORDER_WIDTH + X_OFFSET] to x[ncols - BORDER_WIDTH - X_OFFSET]
        #                           y[BORDER_WIDTH + Y_OFFSET] to y[nlines - BORDER_WIDTH - Y_OFFSET]
  
  
    def fstr(self, template):
        return eval(f'f"""{template}"""')
    def startWrite(self):
        if not self.disabled:
            self.window.clear()
            for line in self.header:
                self.write(self.fstr(line))
            
    # TODO: add header
    def resize(self, nlines, ncols):
        self.window.resize(nlines, ncols)
        self.height, self.width = nlines, ncols  # bookkeeping

    def write(self, text, color_pair=0):
        if not self.disabled:
            # split text into lines of correct length and write them
            length = self.width - self.x_offset * 2 - self.border_width * 2
            if length:
                lines = [text[i : i + length] for i in range(0, len(text), length)]
                # print(lines)
                for line in lines:
                    self._write(line, color_pair)

    def writeProgressBar(
        self,
        progress: float,
        message: str,
        showPercentage: bool = False,
        lsep="[",
        rsep="]",
        fill="■",
        color_pair=0,
    ):
        """
        Create a progress bar with a message and a percentage.
        Will write a progress bar to the full width of the window."""
        if not self.disabled:
            percent = f"{progress:.2%}"
            percent = percent.rjust(7)

            max_size = self.width - self.x_offset * 2 - self.border_width * 2

            current_message_size = (
                len(message) + len(lsep) + len(rsep) + len(fill) + 1
            )  # +1 for the space

            if showPercentage:
                current_message_size += len(percent) + 1  # +1 for the space
            progress_bar_size = max_size - current_message_size
            progress = int(progress * progress_bar_size)
            ret = f"{lsep}{fill * progress}{' ' * (progress_bar_size - progress)}{rsep}"

            if showPercentage:
                ret += f" {percent}"
            ret += f" {message}"
            self.write(ret, color_pair)
            
    def writeRangeProgressBar(
        self,
        progress1: float,
        progress2: float,
        message: str,
        showPercentage1: bool = False,
        showpercentage2: bool = False,
        lsep="[",
        rsep="]",
        fill1="■",
        fill2="□",
        color_pair1=0,
        color_pair2=0,
    ):
        """
        Create a 2-segment progress bar with a message and a percentage.
        Will write a progress bar to the full width of the window."""
        if not self.disabled:
            percent1 = f"{progress1:.2%}".ljust(7)
            percent2 = f"{progress2:.2%}".ljust(7)
            max_size = self.width - self.x_offset * 2 - self.border_width * 2

            current_message_size = (
                len(message) + len(lsep) + len(rsep) + len(fill1) + len(fill2) + 2
            )  # +2 for the spaces

            if showPercentage1:
                current_message_size += len(percent1) + 1 # +1 for the space
                
            # not done for the second percentage, since I show it instead of part of the bar
            progress_bar_size = max_size - current_message_size

            # Determine the size of each segment
            segment1_size = int(progress1 * (progress_bar_size / 2))
            segment2_size = int(progress2 * (progress_bar_size / 2))

            # Generate the progress bar string
            ret = f"{lsep}{fill1 * segment1_size}{fill2 * segment2_size}{' ' * (progress_bar_size - segment1_size - segment2_size)}{rsep}"
            
            
            # Add percentages if required
            
            if showpercentage2:
                go_back = len(rsep) + len(percent2) + 1
                ret = ret[:-go_back]
                ret += f" {percent2}{rsep}"
                
            if showPercentage1:
                ret += f" {percent1}"
            
            ret += f" {message}"

            # TODO: Write each segment with its respective color pair
            self.write(ret, color_pair1)

    def bigProgressBar(self, progress: float, message: str, color_pair=0):
        blanks = "".rjust(len(message))
        self.writeProgressBar(progress,blanks,	lsep="┌",rsep="┐",fill="▄", color_pair=color_pair)
        self.writeProgressBar(progress,blanks,	lsep="│",rsep="│",fill="█", color_pair=color_pair)
        self.writeProgressBar(progress,message,	lsep="│",rsep="│",fill="█", color_pair=color_pair)
        self.writeProgressBar(progress,blanks,	lsep="│",rsep="│",fill="█", color_pair=color_pair)
        self.writeProgressBar(progress,blanks,	lsep="└",rsep="┘",fill="▀", color_pair=color_pair)

    def writeLine(self, character, color_pair=0):
        if not self.disabled:
            self._write(
                character * (self.width - self.x_offset * 2 - self.border_width * 2),
                color_pair=color_pair,
            )

    def _write(self, text, color_pair=0):
        # strip out newlines
        text = text.replace("\n", "")
        if not self.disabled and text:
            if len(text) > self.width - self.x_offset * 2 - self.border_width * 2:
                raise Exception("Text too long for line")
            self.y_offset += 1
            if self.y_offset > self.height - self.border_width:  #
                self.y_offset = Y_OFFSET
            self.window.addstr(self.y_offset, self.x_offset, f"{text}", curses.color_pair(color_pair))
            
    def finishWrite(self, reset: bool = True):
        if not self.disabled:
            if reset:
                self.y_offset = Y_OFFSET
            self.window.border()
            self.window.refresh()


class WindowGrid:
    def __init__(self, stdscr: curses._CursesWindow, x, y):
        """
        Create a grid of windows x by y, with the main window being stdscr. Rescale windows to fit the screen when resized.
        """
        self.windows = list[TerminalWindow]()
        self.stdscr = stdscr
        self.lines, self.cols = self.stdscr.getmaxyx()
        self.x = x
        self.y = y
        self.windowWidth = self.cols // x
        self.windowHeight = self.lines // y
        self.windowBounds = dict()

    def resize(self, lines, cols):
        self.lines, self.cols = lines, cols
        self.windowWidth = self.cols // self.x
        self.windowHeight = self.lines // self.y
        self.stdscr.clear()
        for window in self.windows:
            self._resizeWindow(window)

    def _resizeWindow(self, window: TerminalWindow):
        bounds = self.windowBounds[window]
        grid_x, grid_y, cell_width, cell_height = bounds
        nlines = self.windowHeight * cell_height
        ncols = self.windowWidth * cell_width
        begin_y = self.windowHeight * grid_y
        begin_x = self.windowWidth * grid_x
        
        lines, cols = self.stdscr.getmaxyx()

        if cell_width > 1 and grid_x + cell_width == self.x:
            # last window in row, take up remaining space
            
            # calculate total cols:
            left = cols - ncols - begin_x
            ncols += left
            
        if cell_height > 1 and grid_y + cell_height == self.y:
            # last window in column, take up remaining space
            
            # calculate total lines:
            left = lines - nlines - begin_y
            nlines += left

        window.clear()
        window.resize(int(nlines), int(ncols))
        window.mvwin(int(begin_y), int(begin_x))

    def resizeWindow(
        self, window: TerminalWindow, grid_x, grid_y, cell_width=1, cell_height=1
    ):
        if grid_x and grid_y:
            self.windowBounds[window] = (grid_x, grid_y, cell_width, cell_height)
        else:
            grid_x, grid_y, _, _ = self.windowBounds[window]
            self.windowBounds[window] = (grid_x, grid_y, cell_width, cell_height)
        self._resizeWindow(window)

    def addWindow(
        self, grid_x=0, grid_y=0, cell_width=1, cell_height=1
    ) -> TerminalWindow:
        """
        Add a window to the grid at position x, y with width and height in grid cells.
        In a 3x3 grid, the top left window would be at 0, 0 with width 1 and height 1.
        A window that takes the top row is at 0, 0 with width 3 and height 1.
        """
        if len(self.windows) > self.x * self.y:
            raise Exception("Too many windows")
        # if (grid_x + cell_width > self.x or grid_y + cell_height > self.y):
        #     raise Exception("Window out of bounds", grid_x, grid_y, cell_width, cell_height)
        if cell_width < 1 or cell_height < 1:
            raise Exception("Window too small")
        if cell_width > self.x or cell_height > self.y:
            raise Exception("Window too large")

        nlines = self.windowHeight * cell_height
        ncols = self.windowWidth * cell_width

        begin_y = self.windowHeight * grid_y
        begin_x = self.windowWidth * grid_x

        window = TerminalWindow(int(nlines), int(ncols), int(begin_y), int(begin_x))
        self.windows.append(window)
        self.windowBounds[window] = (grid_x, grid_y, cell_width, cell_height)
        return window

# TODO: add/remove windows from grid, rescale them when windows are added/removed

class SelfGrowingWindowGrid(WindowGrid):
    """
    Grid that only takes anchor points and grows windows to fill the screen.
    """

    def useGridAndGrow(self):
        # sort windows by y, then x
        self.windows.sort(
            key=lambda x: (self.windowBounds[x][0], self.windowBounds[x][1]),
            reverse=True,
        )

        grid = np.array([[0 for _ in range(self.x)] for _ in range(self.y)])
        # grid will be 0 for empty, i for taken
        i = 1
        for window in [window for window in self.windows if not window.disabled]:
            grid_x, grid_y, cell_width, cell_height = self.windowBounds[window]
            for x in range(grid_x, grid_x + cell_width):
                for y in range(grid_y, grid_y + cell_height):
                    grid[y][x] = i
            i += 1
        
        # now expand windows in y direction
        for window in [window for window in self.windows if not window.disabled]:
            grid_x, grid_y, cell_width, cell_height = self.windowBounds[window]
            # expand downwards
            while grid_y + cell_height < self.y:
                # a cell is taken if the cell is not 0 and not i
                taken = False
                for x in range(grid_x, grid_x + cell_width):
                    if grid[grid_y + cell_height][x] != 0 and grid[grid_y + cell_height][x] != i:
                        taken = True
                        break
                if taken:
                    break
                cell_height += 1
            # expand rightwards
            while grid_x + cell_width < self.x:
                # a cell is taken if the cell is not 0 and not i
                taken = False
                for y in range(grid_y, grid_y + cell_height):
                    if grid[y][grid_x + cell_width] != 0 and grid[y][grid_x + cell_width] != i:
                        taken = True
                        break
                if taken:
                    break
                cell_width += 1
            self.windowBounds[window] = grid_x, grid_y, cell_width, cell_height
            # TODO: recalc grid here
        
            win_i = 1
            for window in [window for window in self.windows if not window.disabled]:
                grid_x, grid_y, cell_width, cell_height = self.windowBounds[window]
                for x in range(grid_x, grid_x + cell_width):
                    for y in range(grid_y, grid_y + cell_height):
                        grid[y][x] = win_i
                win_i += 1
        print(grid)
        
        for window in [window for window in self.windows if not window.disabled]:
            self._resizeWindow(window)

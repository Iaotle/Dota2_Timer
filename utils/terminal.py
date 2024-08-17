from __future__ import annotations
import curses
import datetime # needed for lazy f-string evaluation
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

    def write(self, text):
        if not self.disabled:
            # split text into lines of correct length and write them
            length = self.width - self.x_offset * 2 - self.border_width * 2
            if length:
                lines = [text[i : i + length] for i in range(0, len(text), length)]
                # print(lines)
                for line in lines:
                    self._write(line)

    def writeProgressBar(
        self,
        progress: float,
        message: str,
        showPercentage: bool = False,
        lsep="[",
        rsep="]",
        fill="■",
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
            self.write(ret)

    def bigProgressBar(self, progress: float, message: str, showPercentage: bool = False):
        blanks = " ".rjust(len(message))
        self.writeProgressBar(progress,blanks,	lsep="┌",rsep="┐",fill="▄")
        self.writeProgressBar(progress,blanks,	lsep="│",rsep="│",fill="█")
        self.writeProgressBar(progress,message,	lsep="│",rsep="│",fill="█")
        self.writeProgressBar(progress,blanks,	lsep="│",rsep="│",fill="█")
        self.writeProgressBar(progress,blanks,	lsep="└",rsep="┘",fill="▀")

    def writeLine(self, character):
        if not self.disabled:
            self._write(
                character * (self.width - self.x_offset * 2 - self.border_width * 2)
            )

    def _write(self, text):
        # strip out newlines
        text = text.replace("\n", "")
        if not self.disabled and text:
            if len(text) > self.width - self.x_offset * 2 - self.border_width * 2:
                raise Exception("Text too long for line")
            self.y_offset += 1
            if self.y_offset > self.height - self.border_width:  #
                self.y_offset = Y_OFFSET
            self.window.addstr(self.y_offset, self.x_offset, f"{text}")

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
        self.windows = list()
        self.stdscr = stdscr
        self.lines, self.cols = self.stdscr.getmaxyx()
        self.x = x
        self.y = y
        self.windowWidth = self.cols / x
        self.windowHeight = self.lines / y
        self.windowBounds = dict()

    def resize(self, lines, cols):
        self.lines, self.cols = lines, cols
        self.windowWidth = self.cols / self.x
        self.windowHeight = self.lines / self.y
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

        window.clear()
        window.mvwin(int(begin_y), int(begin_x))
        window.resize(int(nlines), int(ncols))

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
        # TODO: check for overlap

        nlines = self.windowHeight * cell_height
        ncols = self.windowWidth * cell_width

        begin_y = self.windowHeight * grid_y
        begin_x = self.windowWidth * grid_x
        # TODO: also do this when resizing
        if cell_width > 1 and grid_x + cell_width == self.x:
            # last window in row, take up remaining space
            ncols += self.cols % self.x
        if cell_height > 1 and grid_y + cell_height == self.y:
            # last window in column, take up remaining space
            nlines += self.lines % self.y

        window = TerminalWindow(int(nlines), int(ncols), int(begin_y), int(begin_x))
        self.windows.append(window)
        self.windowBounds[window] = (grid_x, grid_y, cell_width, cell_height)
        return window

# TODO: add/remove windows from grid, rescale them when windows are added/removed

class SelfGrowingWindowGrid(WindowGrid):
    """
    Grid that only takes anchor points and grows windows to fill the screen.
    """

    def growWindows(self):
        # sort windows by y, then x
        self.windows.sort(
            key=lambda x: (self.windowBounds[x][1], self.windowBounds[x][0]),
            reverse=True,
        )

        lines, cols = self.stdscr.getmaxyx()
        for window in self.windows:
            bounds = self.windowBounds[window]
            grid_x, grid_y, cell_width, cell_height = bounds
            anchor_x = self.windowWidth * grid_x
            anchor_y = self.windowHeight * grid_y

            # reset cell width and height
            cell_width = 1
            cell_height = 1

            # grow until we hit lines
            while anchor_y + self.windowHeight * cell_height < lines:
                cell_height += 1
            # grow until we hit cols
            while anchor_x + self.windowWidth * cell_width < cols:
                cell_width += 1

            # update window bounds
            self.windowBounds[window] = grid_x, grid_y, cell_width, cell_height

            lines, cols = min(anchor_y, lines), max(anchor_x, cols)

        # resize all windows
        for window in self.windows:
            self._resizeWindow(window)

    def _checkOverlap(self, window: TerminalWindow, max_x, max_y):

        anchor_y, anchor_x = window.getbegyx()

        for other_window in self.windows:
            if other_window == window:
                continue
            other_bounds = self.windowBounds[other_window]
            other_grid_x, other_grid_y, other_cell_width, other_cell_height = (
                other_bounds
            )
            other_anchor_x = self.windowWidth * other_grid_x
            other_anchor_y = self.windowHeight * other_grid_y

            other_max_x = other_anchor_x + self.windowWidth * other_cell_width
            other_max_y = other_anchor_y + self.windowHeight * other_cell_height

            if (
                anchor_x < other_max_x
                and anchor_y < other_max_y
                and max_x > other_anchor_x
                and max_y > other_anchor_y
            ):
                return True
        return False

    def growWindowsWidthFirst(self):
        self.windows.sort(
            key=lambda x: (self.windowBounds[x][0], self.windowBounds[x][1])
        )  # sort by x, then y
        lines, cols = self.stdscr.getmaxyx()
        for window in self.windows:
            anchor_y, anchor_x = window.getbegyx()
            grid_x, grid_y, cell_width, cell_height = self.windowBounds[window]

            # Grow width we hit cols or overlap with another window
            while anchor_x + self.windowWidth * cell_width < cols:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width

                max_x += self.windowWidth

                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_width += 1

            # Grow height we hit lines or overlap with another window
            while anchor_y + self.windowHeight * cell_height < lines:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width

                max_y += self.windowHeight

                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_height += 1

            # Update window bounds
            self.windowBounds[window] = grid_x, grid_y, cell_width, cell_height
        # resize all windows
        for window in self.windows:
            self._resizeWindow(window)

    def growWindowsHeightFirst(self):
        self.windows.sort(
            key=lambda x: (self.windowBounds[x][1], self.windowBounds[x][0])
        )  # sort by y, then x
        lines, cols = self.stdscr.getmaxyx()
        for window in self.windows:
            anchor_y, anchor_x = window.getbegyx()
            grid_x, grid_y, cell_width, cell_height = self.windowBounds[window]

            # Grow height we hit lines or overlap with another window
            while anchor_y + self.windowHeight * cell_height < lines:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width

                max_y += self.windowHeight

                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_height += 1

            # Grow width we hit cols or overlap with another window
            while anchor_x + self.windowWidth * cell_width < cols:
                max_y = anchor_y + self.windowHeight * cell_height
                max_x = anchor_x + self.windowWidth * cell_width

                max_x += self.windowWidth

                if self._checkOverlap(window, max_x, max_y):
                    break
                cell_width += 1

            # Update window bounds
            self.windowBounds[window] = grid_x, grid_y, cell_width, cell_height
        # resize all windows
        for window in self.windows:
            self._resizeWindow(window)

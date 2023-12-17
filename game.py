# Original code from the TFT_OCR_BOT repository on GitHub:
# Repository URL: https://github.com/jfd02/TFT-OCR-BOT
# Original authors:
# - @jfd02
# - @Squarific
# - @danparizher
# - @Cr4zZyBipBiip
# - @Rexblane
# - @stardust136
# - @anthony5301
# Modified by the-user-created
#

"""
Handles tasks that happen each game round
"""

from time import sleep, perf_counter
import random
import multiprocessing
import settings
import arena_functions
import game_assets
import game_functions
from arena import Arena
from vec4 import Vec4
from vec2 import Vec2

try:
    import win32gui
    platform = "Windows"
except ModuleNotFoundError:
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    platform = "macOS"


class Game:
    """Game class that handles game logic such as round tasks"""

    def __init__(self, message_queue: multiprocessing.Queue) -> None:
        self.message_queue = message_queue
        self.arena = Arena(self.message_queue)
        self.round = "0-0"
        self.time: None = None
        self.forfeit_time: int = settings.FORFEIT_TIME + random.randint(50, 150)
        self.found_window = False

        print("\n[!] Searching for game window")
        while not self.found_window:
            print("  Did not find window, trying again...")
            if platform == "Windows":
                win32gui.EnumWindows(self.callback, None)
            else:
                self.callback_macos()
            sleep(1)

        self.loading_screen()

    def callback(self, hwnd, extra) -> None:  # pylint: disable=unused-argument
        """Function used to find the game window and get its size"""
        if "League of Legends (TM) Client" not in win32gui.GetWindowText(hwnd):
            return

        rect = win32gui.GetWindowRect(hwnd)

        x_pos = rect[0]
        y_pos = rect[1]
        width = rect[2] - x_pos
        height = rect[3] - y_pos

        if width < 200 or height < 200:
            return

        print(f"  Window {win32gui.GetWindowText(hwnd)} found")
        print(f"    Location: ({x_pos}, {y_pos})")
        print(f"    Size:     ({width}, {height})")
        Vec4.setup_screen(x_pos, y_pos, width, height)
        Vec2.setup_screen(x_pos, y_pos, width, height)
        self.found_window = True

    def callback_macos(self) -> None:
        """Function used to find the game window and get its size"""
        desired_window_title = "League Of Legends"

        for window in CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID):
            if window.get("kCGWindowOwnerName") == desired_window_title:
                print(f"Found desired window: {desired_window_title}")
                x_pos = window["kCGWindowBounds"]["X"]
                y_pos = window["kCGWindowBounds"]["Y"]
                width = window["kCGWindowBounds"]["Width"]
                height = window["kCGWindowBounds"]["Height"]
                # TODO: Add borderless and windowed mode support to all ocr functions
                #  - currently only works in borderless

                print(f"Location:   ({x_pos}, {y_pos})")
                print(f"Size:       ({width}, {height})")

                Vec4.setup_screen(x_pos, y_pos, width, height)
                Vec2.setup_screen(x_pos, y_pos, width, height)
                self.found_window = True
                break

    def loading_screen(self) -> None:
        """Loop that runs while the game is in the loading screen"""
        game_functions.default_pos()
        while game_functions.get_round() != "1-1":
            sleep(1)
        self.start_time: float = perf_counter()
        self.game_loop()

    def game_loop(self) -> None:
        """Loop that runs while the game is active; handles calling the correct tasks for round and exiting game"""
        ran_round: str = None
        last_game_health: int = 100

        while True:
            game_health: int = arena_functions.get_health()
            if game_health == 0 and last_game_health > 0:
                count: int = 15
                while count > 0:
                    if not game_functions.check_alive():
                        self.message_queue.put("CLEAR")
                        game_functions.exit_game()
                        break
                    sleep(1)
                    count -= 1
                break
            if game_health == -1 and last_game_health > 0:
                self.message_queue.put("CLEAR")
                break
            last_game_health = game_health

            self.round: str = game_functions.get_round()

            if settings.FORFEIT and perf_counter() - self.start_time > self.forfeit_time:
                game_functions.forfeit()
                return

            if self.round != ran_round:
                # TODO: Check that game_assets still considers 1-1 to be protal and SECOND ROUND
                if self.round in game_assets.PVP_ROUND:
                    game_functions.default_pos()
                    self.pvp_round()
                elif self.round in game_assets.PORTAL_ROUND:
                    self.portal_round()
                    ran_round: str = self.round
                elif self.round in game_assets.SECOND_ROUND:
                    self.second_round()
                    ran_round: str = self.round
                elif self.round in game_assets.CAROUSEL_ROUND:
                    self.carousel_round()
                    ran_round: str = self.round
                elif self.round in game_assets.PVE_ROUND:
                    game_functions.default_pos()
                    self.pve_round()
                    ran_round: str = self.round
                elif self.round in game_assets.CAROUSEL_ROUND:
                    self.carousel_round()
                    ran_round: str = self.round
                elif self.round in game_assets.SECOND_ROUND:
                    self.second_round()
                    ran_round: str = self.round
            sleep(0.5)

    def portal_round(self) -> None:
        """Handles tasks for portal rounds"""
        print(f"\n\n[Portal Round] {self.round}")
        sleep(2.0)  # Sleep to avoid flashes on screen
        self.arena.pick_portal()
        # self.message_queue.put("CLEAR")

    def second_round(self) -> None:
        """Move unknown champion to board after the first carousel"""
        print(f"\n[Second Round] {self.round}")
        self.message_queue.put("CLEAR")
        while True:
            result = arena_functions.bench_occupied_check()
            if any(result):
                break
        self.arena.bench[result.index(True)] = "?"
        self.arena.move_unknown()
        sleep(2.5)  # Sleep for a short period to allow the arena info button to appear
        self.arena.confirm_portal()
        self.end_round_tasks()

    def carousel_round(self) -> None:
        """Handles tasks for carousel rounds"""
        print(f"\n[Carousel Round] {self.round}")
        self.message_queue.put("CLEAR")
        if self.round == "3-4":
            self.arena.final_comp = True
        self.arena.check_health()
        print("  Getting a champ from the carousel")
        game_functions.get_champ_carousel(self.round)
        # TODO: Should we move the tactician back to the default position here?

    def pve_round(self) -> None:
        """Handles tasks for PVE rounds"""
        print(f"\n[PvE Round] {self.round}")
        self.message_queue.put("CLEAR")
        game_functions.default_tactician_pos()
        sleep(0.5)
        if self.round in game_assets.AUGMENT_ROUNDS:
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            # Can't purchase champions for a short period after choosing augment, so sleep for a short period
            sleep(2.5)
        if self.round == "1-3":
            # Check if the active portal is an anvil portal and clear the anvils it if it is
            if self.arena.active_portal in game_assets.ANVIL_PORTALS:
                self.arena.clear_anvil()
            sleep(1.5)
            self.arena.fix_unknown()
            self.arena.anvil_free[1:] = [True] * 8
            self.arena.clear_anvil()
            self.arena.anvil_free[:2] = [True, False]
            self.arena.clear_anvil()
            # self.arena.tacticians_crown_check() #not getting any item in set9 round 1-3, skipped

        self.arena.fix_bench_state()
        self.arena.spend_gold()
        self.arena.move_champions()
        self.arena.replace_unknown()
        if self.arena.final_comp:
            self.arena.final_comp_check()
        self.arena.bench_cleanup()
        self.end_round_tasks()

    def pvp_round(self) -> None:
        """Handles tasks for PVP rounds"""
        print(f"\n[PvP Round] {self.round}")
        self.message_queue.put("CLEAR")
        game_functions.default_tactician_pos()
        sleep(0.5)

        if self.round in game_assets.AUGMENT_ROUNDS:
            sleep(1)
            self.arena.augment_roll = True
            self.arena.pick_augment()
            sleep(2.5)

        if self.round in ("2-1", "2-5"):
            self.arena.buy_xp_round()

        if self.round in game_assets.PICKUP_ROUNDS:
            print("  Picking up items")
            sleep(2.5)  # Sleep to avoid flashes on screen affecting the image processing
            self.arena.pickup_items()

        self.arena.fix_bench_state()
        self.arena.bench_cleanup()
        if self.round in game_assets.ANVIL_ROUNDS:
            self.arena.clear_anvil()
        if self.round in game_assets.PICKUP_ROUNDS:
            self.arena.spend_gold(speedy=True)
        else:
            self.arena.spend_gold()
        self.arena.move_champions()
        self.arena.replace_unknown()
        if self.arena.final_comp:
            self.arena.final_comp_check()
        self.arena.bench_cleanup()

        if self.round in game_assets.ITEM_PLACEMENT_ROUNDS:
            sleep(1)
            self.arena.place_items()
        self.end_round_tasks()

    def end_round_tasks(self) -> None:
        """Common tasks across rounds that happen at the end"""
        self.arena.check_health()
        self.arena.get_label()
        game_functions.default_tactician_pos()
        game_functions.default_pos()

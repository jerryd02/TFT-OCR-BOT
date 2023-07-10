"""
Handles the board / bench state inside of the game and
other variables used by the bot to make decisions
"""
import json
from time import sleep
import game_assets
import mk_functions
import screen_coords
from champion import Champion
import ocr
import game_functions
import arena_functions
from comps import CompsManager
import comps

class Arena:
    """Arena class that handles game logic such as board and bench state"""

    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    def __init__(self, message_queue, comps_manager : CompsManager) -> None:
        self.comps_manager = comps_manager
        self.comps_manager.SelectNextComp()
        self.message_queue = message_queue
        self.board_size = 0
        self.bench: list[None] = [None, None, None, None, None, None, None, None, None]
        self.board: list = []
        self.board_unknown: list = []
        self.unknown_slots: list = comps_manager.get_unknown_slots()
        self.champs_to_buy: list = comps_manager.champions_to_buy()
        self.board_names: list = []
        self.items: list = []
        self.final_comp = False
        self.level = 0
        self.augment_roll = True
        self.marus_omegnum = False
        self.tacticians_crown = True
        self.spam_roll = False


    def portal_vote(self) -> None:
        """Votes for portal from user defined portal priority list or defaults to first portal"""
        portals: list = []
        for coords in screen_coords.PORTALS_POS:
            portal: str = ocr.get_text(screenxy=coords.get_coords(), scale=3, psm=7)
            portals.append(portal)

        for portal in portals:
            for potential in game_assets.PORTALS:
                if potential in portal:
                    print(f"  Voted for: {portal}")
                    mk_functions.left_click(screen_coords.PORTALS_LOC[portals.index(portal)].get_coords())
                    sleep(0.7)
                    mk_functions.left_click(screen_coords.PORTALS_VOTES[portals.index(portal)].get_coords())
                    return

        print(f"  [!] No priority or backup region found, choosing first portal")
        mk_functions.left_click(screen_coords.PORTALS_LOC[0].get_coords())
        sleep(0.7)
        mk_functions.left_click(screen_coords.PORTALS_VOTES[0].get_coords())
                
    def region_augment(self) -> None:
        """Checks if region augment is Marus Omegnum (tacticians crown)"""
        mk_functions.right_click(screen_coords.REGION_AUGMENT_LOC.get_coords())
        sleep(1)
        region: str = ocr.get_text(screenxy=screen_coords.REGION_AUGMENT_POS.get_coords(), scale=3, psm=7)
        try:
            if "Marus Omegnum" in region:
                print(f"  Region Augment: {region}. Picking up Tacticians Crown at round 2-5 or 4-5")
                self.marus_omegnum = True
            else:
                print(f"  Region Augment: {region}")
        except TypeError:
            print("  Region Augment could not be read")

    
    def fix_bench_state(self) -> None:
        """Iterates through bench and fixes invalid slots"""
        bench_occupied: list = arena_functions.bench_occupied_check()
        for index, slot in enumerate(self.bench):
            if slot is None and bench_occupied[index]:
                self.bench[index] = "?"
            if isinstance(slot, str) and not bench_occupied[index]:
                self.bench[index] = None
            if isinstance(slot, Champion) and not bench_occupied[index]:
                self.bench[index] = None

    def bought_champion(self, name: str, slot: int) -> None:
        """Purchase champion and creates champion instance"""
        self.bench[slot] = Champion(name=name,
                                    coords=screen_coords.BENCH_LOC[slot].get_coords(
                                    ),
                                    build=self.comps_manager.CURRENT_COMP()[1][name]["items"].copy(),
                                    slot=slot,
                                    size=self.comps_manager.champions[name]["Board Size"],
                                    final_comp=self.comps_manager.CURRENT_COMP()[1][name]["final_comp"])
        mk_functions.move_mouse(screen_coords.DEFAULT_LOC.get_coords())
        sleep(0.5)
        self.fix_bench_state()

    def have_champion(self) -> Champion | None:
        """Checks the bench to see if champion exists"""
        return next(
            (
                champion
                for champion in self.bench
                if isinstance(champion, Champion)
                and champion.name not in self.board_names
            ),
            None,
        )

    def move_known(self, champion: Champion) -> None:
        """Moves champion to the board"""
        print(f"  Moving {champion.name} to board")
        destination: tuple = screen_coords.BOARD_LOC[self.comps_manager.CURRENT_COMP()[1][champion.name]["board_position"]].get_coords()
        mk_functions.left_click(champion.coords)
        sleep(0.18)
        mk_functions.left_click(destination)
        champion.coords = destination
        self.board.append(champion)
        self.board_names.append(champion.name)
        self.bench[champion.index] = None
        champion.index = self.comps_manager.CURRENT_COMP()[1][champion.name]["board_position"]
        self.board_size += champion.size

    def move_unknown(self) -> None:
        """Moves unknown champion to the board"""
        for index, champion in enumerate(self.bench):
            if isinstance(champion, str):
                print(f"  Moving {champion} to board")
                mk_functions.left_click(screen_coords.BENCH_LOC[index].get_coords())
                sleep(0.18)
                mk_functions.left_click(
                    screen_coords.BOARD_LOC[self.unknown_slots[len(self.board_unknown)]].get_coords())
                self.bench[index] = None
                self.board_unknown.append(champion)
                self.board_size += 1
                return

    def sell_bench(self) -> None:
        """Sells all of the champions on the bench"""
        for index, _ in enumerate(self.bench):
            mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
            self.bench[index] = None

    def unknown_in_bench(self) -> bool:
        """Sells all of the champions on the bench"""
        return any(isinstance(slot, str) for slot in self.bench)

    def move_champions(self) -> None:
        """Moves champions to the board"""
        self.level: int = arena_functions.get_level()
        while self.level > self.board_size:
            champion: Champion | None = self.have_champion()
            if champion is not None:
                self.move_known(champion)
            elif self.unknown_in_bench():
                self.move_unknown()
            else:
                bought_unknown = False
                shop: list = arena_functions.get_shop(self.comps_manager)
                for champion in shop:
                    gold: int = arena_functions.get_gold()
                    valid_champ: bool = (
                        champion[1] in self.comps_manager.champions and
                        self.comps_manager.champion_gold_cost(champion[1]) <= gold and
                        self.comps_manager.champion_board_size(champion[1]) == 1 and
                        champion[1] not in self.champs_to_buy and
                        champion[1] not in self.board_unknown
                    )
                    if valid_champ:
                        none_slot: int = arena_functions.empty_slot()
                        mk_functions.left_click(screen_coords.BUY_LOC[champion[0]].get_coords())
                        sleep(0.2)
                        self.bench[none_slot] = f"{champion[1]}"
                        self.move_unknown()
                        bought_unknown = True
                        break

                if not bought_unknown:
                    print("  Need to sell entire bench to keep track of board")
                    self.sell_bench()
                    return

    def replace_unknown(self) -> None:
        """Replaces unknown champion"""
        champion: Champion | None = self.have_champion()
        if len(self.board_unknown) > 0 and champion is not None:
            mk_functions.press_e(screen_coords.BOARD_LOC[self.unknown_slots[len(
                self.board_unknown) - 1]].get_coords())
            self.board_unknown.pop()
            self.board_size -= 1
            self.move_known(champion)

    def bench_cleanup(self) -> None:
        """Sells unknown champions"""
        for index, champion in enumerate(self.bench):
            if champion == "?" or isinstance(champion, str):
                print("  Selling unknown champion")
                mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
                self.bench[index] = None
            elif isinstance(champion, Champion):
                if champion.name not in self.champs_to_buy and champion.name in self.board_names:
                    print("  Selling unknown champion")
                    mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
                    self.bench[index] = None

    def clear_anvil(self) -> None:
        """Clears anvil on the bench, selects middle item"""
        for index, champion in enumerate(self.bench):
            if champion is None:
                mk_functions.press_e(screen_coords.BENCH_LOC[index].get_coords())
        sleep(1)
        mk_functions.left_click(screen_coords.BUY_LOC[2].get_coords())
        sleep(0.8)

    def place_items(self) -> None:
        """Iterates through items and tries to add them to champion"""
        self.items = arena_functions.get_items()
        print(f"  Items: {list(filter((None).__ne__, self.items))}")
        for index, _ in enumerate(self.items):
            if self.items[index] is not None:
                self.add_item_to_champs(index)
        if self.tacticians_crown: #checks for Tacticians Crown througout game
            if 'TacticiansCrown' in self.items:
                print("  Tacticians Crown on bench, adding extra slot to board")
                self.board_size -= 1
                self.tacticians_crown = False

    def add_item_to_champs(self, item_index: int) -> None:
        """Iterates through champions in the board and checks if the champion needs items"""
        for champ in self.board:
            if champ.does_need_items() and self.items[item_index] is not None:
                self.add_item_to_champ(item_index, champ)

    def add_item_to_champ(self, item_index: int, champ: Champion) -> None:
        """Takes item index and champ and applies the item"""
        item = self.items[item_index]
        if item in game_assets.FULL_ITEMS:
            if item in champ.build:
                mk_functions.left_click(
                    screen_coords.ITEM_POS[item_index][0].get_coords())
                mk_functions.left_click(champ.coords)
                print(f"  Placed {item} on {champ.name}")
                champ.completed_items.append(item)
                champ.build.remove(item)
                self.items[self.items.index(item)] = None
        elif len(champ.current_building) == 0:
            item_to_move: None = None
            for build_item in champ.build:
                build_item_components: list = list(
                    game_assets.FULL_ITEMS.get(build_item, []))
                if item in build_item_components:
                    item_to_move: None = item
                    build_item_components.remove(item_to_move)
                    champ.current_building.append(
                        (build_item, build_item_components[0]))
                    champ.build.remove(build_item)
            if item_to_move is not None:
                mk_functions.left_click(
                    screen_coords.ITEM_POS[item_index][0].get_coords())
                mk_functions.left_click(champ.coords)
                print(f"  Placed {item} on {champ.name}")
                self.items[self.items.index(item)] = None
        else:
            for builditem in champ.current_building:
                if item == builditem[1]:
                    mk_functions.left_click(
                        screen_coords.ITEM_POS[item_index][0].get_coords())
                    mk_functions.left_click(champ.coords)
                    champ.completed_items.append(builditem[0])
                    champ.current_building.clear()
                    self.items[self.items.index(item)] = None
                    print(f"  Placed {item} on {champ.name}")
                    print(f"  Completed {builditem[0]}")
                    return

    def fix_unknown(self) -> None:
        """Checks if the item passed in arg one is valid"""
        sleep(0.25)
        mk_functions.press_e(
            screen_coords.BOARD_LOC[self.unknown_slots[0]].get_coords())
        self.board_unknown.pop(0)
        self.board_size -= 1

    def remove_champion(self, champion: Champion) -> None:
        """Checks if the item passed in arg one is valid"""
        for index, slot in enumerate(self.bench):
            if isinstance(slot, Champion) and slot.name == champion.name:
                mk_functions.press_e(slot.coords)
                self.bench[index] = None

        self.champs_to_buy = list(filter(f"{champion.name}".__ne__,
                                         self.champs_to_buy))  # Remove all instances of champion in champs_to_buy

        mk_functions.press_e(champion.coords)
        self.board_names.remove(champion.name)
        self.board_size -= champion.size
        self.board.remove(champion)

    def final_comp_check(self) -> None:
        """Checks the board and replaces champions not in final comp"""
        for slot in self.bench:
            if (
                isinstance(slot, Champion)
                and slot.final_comp
                and slot.name not in self.board_names
            ):
                for champion in self.board:
                    if not champion.final_comp and champion.size == slot.size:
                        print(f"  Replacing {champion.name} with {slot.name}")
                        self.remove_champion(champion)
                        self.move_known(slot)
                        break

    def tacticians_crown_check(self) -> None:
        """Checks if the item from carousel is tacticians crown"""
        mk_functions.move_mouse(screen_coords.ITEM_POS[0][0].get_coords())
        sleep(0.5)
        item: str = ocr.get_text(screenxy=screen_coords.ITEM_POS[0][1].get_coords(), scale=3, psm=13,
                            whitelist=ocr.ALPHABET_WHITELIST)
        item: str = arena_functions.valid_item(item)
        try:
            if "TacticiansCrown" in item:
                print("  Tacticians Crown on bench, adding extra slot to board")
                self.board_size -= 1
                self.tacticians_crown = False
            else:
                print(f"{item} is not TacticiansCrown")
        except TypeError:
            print("  Item could not be read for Tacticians Check")

    def spend_gold(self) -> None:
        """Spends gold every round"""
        first_run = True
        min_gold = 24 if self.spam_roll else 50
        while first_run or arena_functions.get_gold() >= min_gold:
            if not first_run:
                if arena_functions.get_level() != 9:
                    mk_functions.buy_xp()
                    print("  Purchasing XP")
                mk_functions.reroll()
                print("  Rerolling shop")
            shop: list = arena_functions.get_shop(self.comps_manager)
            print(f"  Shop: {shop}")
            for champion in shop:
                if (champion[1] in self.champs_to_buy and
                    arena_functions.get_gold() - self.comps_manager.champions[champion[1]]["Gold"] >= 0
                 ):
                    none_slot: int = arena_functions.empty_slot()
                    if none_slot != -1:
                        mk_functions.left_click(screen_coords.BUY_LOC[champion[0]].get_coords())
                        print(f"    Purchased {champion[1]}")
                        self.bought_champion(champion[1], none_slot)
                        self.champs_to_buy.remove(champion[1])
                    else:
                        """Try to buy champ 3 when bench is full"""
                        print(f"  Board is full but want {champion[1]}")
                        mk_functions.left_click(screen_coords.BUY_LOC[champion[0]].get_coords())
                        game_functions.default_pos()
                        sleep(0.5)
                        self.fix_bench_state()
                        none_slot = arena_functions.empty_slot()
                        sleep(0.5)
                        if none_slot != -1:
                            print(f"    Purchased {champion[1]}")
                            self.champs_to_buy.remove(champion[1])
            first_run = False

    def buy_xp_round(self) -> None:
        """Buys XP if gold is equals or over 4"""
        if arena_functions.get_gold() >= 4:
            mk_functions.buy_xp()


    def load_aguments(self):
        return self.comps_manager.CURRENT_COMP()[2]

    def pick_augment(self) -> None:
        """Picks an augment from comp specific/user defined augment list or defaults to first augment"""
        augments: list = []
        comp_augments = self.load_aguments()
        for coords in screen_coords.AUGMENT_POS:
            augment: str = ocr.get_text(screenxy=coords.get_coords(), scale=3, psm=7)
            augments.append(augment)

        for augment in augments:
            for potential in game_assets.AUGMENTS:
                if potential in augment:
                    print(f"  Choosing augment: {augment}")
                    mk_functions.left_click(screen_coords.AUGMENT_LOC[augments.index(augment)].get_coords())
                    return
                    
        if self.augment_roll:
            print("  Rolling for augment")
            mk_functions.left_click(screen_coords.AUGMENT_ROLL_ONE.get_coords())
            mk_functions.left_click(screen_coords.AUGMENT_ROLL_TWO.get_coords())
            mk_functions.left_click(screen_coords.AUGMENT_ROLL_THREE.get_coords())
            self.augment_roll = False
            self.pick_augment()

        print("  [!] No priority or backup augment found, undefined behavior may occur for the rest of the round")
        mk_functions.left_click(screen_coords.AUGMENT_LOC[0].get_coords())

    def check_health(self) -> None:
        """Checks if current health is below 30 and conditionally activates spam roll"""
        health: int = arena_functions.get_health()
        if health > 0:
            print(f"  Health: {health}")
            if not self.spam_roll and health < 30:
                print("    Health under 30, spam roll activated")
                self.spam_roll = True
        else:
            print("  Health check failed")

    def get_label(self) -> None:
        """Gets labels used to display champion name UI on window"""
        labels: list = [
            (f"{slot.name}", slot.coords)
            for slot in self.bench
            if isinstance(slot, Champion)
        ]

        for slot in self.board:
            if isinstance(slot, Champion):
                labels.append((f"{slot.name}", slot.coords))

        labels.extend(
            (slot, screen_coords.BOARD_LOC[self.unknown_slots[index]].get_coords())
            for index, slot in enumerate(self.board_unknown)
        )
        self.message_queue.put(("LABEL", labels))

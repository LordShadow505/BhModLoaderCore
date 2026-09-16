from typing import TypedDict, List, Dict


class MetadataTyped(TypedDict):
    formatVersion: int
    formatType: str


class ModDataSwfsTyped(TypedDict):
    scripts: Dict[str, str]
    sounds: List[str]
    sprites: List[str]
    # Maps scriptAnchor → if-block string extracted from getHandForCostume().
    # Used for merging multiple hand-mods that modify the same Obf script in UI_MainMenu.swf
    # instead of full replacement. Format: {"tier_b/Obf": "if (...) { return ...; }\n   "}
    obfMappings: Dict[str, str]


class ModDataTyped(MetadataTyped):
    gameVersion: str
    name: str
    author: str
    version: str
    description: str
    tags: List[str]
    previewsIds: Dict[str, str]
    hash: str
    swfs: Dict[str, ModDataSwfsTyped]
    files: Dict[str, str]
    authorId: int
    modId: int
    platform: str


class ModloaderCoreMods(TypedDict):
    mod: str
    modHashSum: str

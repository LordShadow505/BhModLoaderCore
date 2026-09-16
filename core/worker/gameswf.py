import os
import sys
import re
import shutil
from typing import Dict, List, Union

from .dataversion import DataVariable, DataClass
from .variables import METADATA_FORMAT_GAME, METADATA_FORMAT_VERSION
from .basedispatch import SendNotification
from ..notifications import NotificationType

from .brawlhalla import BRAWLHALLA_SWFS
from .brawlforge_template import generate_brawlforge_suite_as, load_symbols
from ..swf.swf import (Swf,
                       GetNeededCharacters,
                       GetElementId,
                       SetElementId,
                       GetSwfByElement,
                       GetNeededCharactersId,
                       GetShapeBitmapId,
                       SetShapeBitmapId)
from ..ffdec.classes import (DefineSpriteTag,
                             DefineFontTags,
                             DefineFontNameTag,
                             DefineFontAlignZonesTag,
                             DefineEditTextTag,
                             DefineTextTag,
                             DefineShapeTags,
                             DefineSoundTag,
                             CSMTextSettingsTag,
                             PlaceObject2Tag,
                             PlaceObject3Tag)
def _get_carrier_path():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "carrier_UI_MainMenu.swf")
    if os.path.exists(p):
        return p
    for base in [getattr(sys, '_MEIPASS', None), os.path.dirname(sys.executable), os.path.abspath(".")]:
        if base:
            for sub in ["core/assets/carrier_UI_MainMenu.swf", "core\\assets\\carrier_UI_MainMenu.swf", "assets/carrier_UI_MainMenu.swf", "carrier_UI_MainMenu.swf"]:
                cand = os.path.abspath(os.path.join(base, sub))
                if os.path.exists(cand):
                    return cand
    return p

CARRIER_UI_MAINMENU_PATH = _get_carrier_path()

# ---------------------------------------------------------------------------
# Clean Obf script template: tier_b.Obf class with handMap, colorMap, and paletteMap.
# ---------------------------------------------------------------------------
_OBF_SCRIPT_TEMPLATE = """\
package tier_b
{
   public class Obf
   {
      public static var AB:String = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.";

      public static var handMap:Object = {};
      public static var colorMap:Object = {};
      public static var paletteMap:Object = {};

      public function Obf()
      {
      }

      public static function initHandMap() : void
      {
         handMap = {};
         colorMap = {};
{INIT_MAP_LINES}
      }

      public static function initPalettes() : void
      {
         paletteMap = {};
{INIT_PALETTE_LINES}
      }

      public static function getCamelSuffixes(str:String) : Array
      {
         var res:Array = [];
         if(str == null || str.length == 0)
         {
            return res;
         }
         res.push(str);
         var i:int = 1;
         var len:int = str.length;
         while(i < len)
         {
            var code:Number = str.charCodeAt(i);
            if(code >= 65 && code <= 90)
            {
               var suffix:String = str.substring(i);
               if(suffix.length >= 3 && res.indexOf(suffix) == -1)
               {
                  res.push(suffix);
               }
            }
            i++;
         }
         return res;
      }

      public static function getHandForCostume(costumeName:String) : String
      {
         if(costumeName == null)
         {
            return null;
         }
         if(handMap == null)
         {
            initHandMap();
         }
         
         // 1. Direct match
         if(handMap[costumeName] != null)
         {
            return handMap[costumeName] as String;
         }
         
         // 2. Search configured keys camel suffixes
         for (var k:String in handMap)
         {
            var keySuffixes:Array = getCamelSuffixes(k);
            var ki:int = 0;
            var klen:int = keySuffixes.length;
            while(ki < klen)
            {
               var ks:String = keySuffixes[ki++];
               if(ks == costumeName)
               {
                  return handMap[k] as String;
               }
            }
         }
         
         // 3. Search costumeName camel suffixes
         var costSuffixes:Array = getCamelSuffixes(costumeName);
         var ci:int = 0;
         var clen:int = costSuffixes.length;
         while(ci < clen)
         {
            var cs:String = costSuffixes[ci++];
            if(handMap[cs] != null)
            {
               return handMap[cs] as String;
            }
         }
         
         return null;
      }

      public static function getColorSwapsForCostume(costumeName:String) : Array
      {
         if(costumeName == null)
         {
            return null;
         }
         if(colorMap == null)
         {
            initHandMap();
         }
         
         // 1. Direct match
         if(colorMap[costumeName] != null)
         {
            return colorMap[costumeName] as Array;
         }
         
         // 2. Search configured keys camel suffixes
         for (var k:String in colorMap)
         {
            var keySuffixes:Array = getCamelSuffixes(k);
            var ki:int = 0;
            var klen:int = keySuffixes.length;
            while(ki < klen)
            {
               var ks:String = keySuffixes[ki++];
               if(ks == costumeName)
               {
                  return colorMap[k] as Array;
               }
            }
         }
         
         // 3. Search costumeName camel suffixes
         var costSuffixes:Array = getCamelSuffixes(costumeName);
         var ci:int = 0;
         var clen:int = costSuffixes.length;
         while(ci < clen)
         {
            var cs:String = costSuffixes[ci++];
            if(colorMap[cs] != null)
            {
               return colorMap[cs] as Array;
            }
         }
         
         return null;
      }

      public static function d(param1:Array, param2:int) : String
      {
         var _loc6_:int = 0;
         var _loc7_:int = 0;
         var _loc3_:String = "";
         var _loc4_:int = 0;
         var _loc5_:int = int(param1.length);
         while(_loc4_ < _loc5_)
         {
            _loc6_ = _loc4_++;
            _loc7_ = int((int(param1[_loc6_]) - param2 - _loc6_ * 7) % 65);
            if(_loc7_ < 0)
            {
               _loc7_ += 65;
            }
            _loc3_ += "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.".charAt(_loc7_);
         }
         return _loc3_;
      }

      public static function targetCostume() : String
      {
         return Obf.d([41, 30, 46, 54, 50, 58, 7],15);
      }

      public static function handFile() : String
      {
         return Obf.d([35,15,40,21,64,38,58,55,12,0,26,37,27],3);
      }

      public static function swapSuffix() : String
      {
         return Obf.d([53, 41, 48, 46],20);
      }

      public static function gcField() : String
      {
         return Obf.d([53,61,0,0,15],56);
      }

      public static function families() : Array
      {
         return [Obf.d([3, 56, 63, 61],35),Obf.d([3, 56, 63, 61],35)];
      }

      public static function paletteChannels() : Array
      {
         return [
            "HairLt","Hair","HairDk",
            "Body1VL","Body1Lt","Body1","Body1Dk","Body1VD","Body1Acc",
            "Body2VL","Body2Lt","Body2","Body2Dk","Body2VD","Body2Acc",
            "SpecialVL","SpecialLt","Special","SpecialDk","SpecialVD","SpecialAcc",
            "ClothVL","ClothLt","Cloth","ClothDk",
            "WeaponVL","WeaponLt","Weapon","WeaponDk","WeaponAcc"
         ];
      }
   }
}
"""

_OBF_ANCHOR = "tier_b.Obf"


class GameSwfData(DataClass):
    DataVariable(METADATA_FORMAT_GAME, 0, "formatVersion")
    formatVersion: int = METADATA_FORMAT_VERSION

    DataVariable(METADATA_FORMAT_GAME, 0, "formatType")
    formatType: str = METADATA_FORMAT_GAME

    DataVariable(METADATA_FORMAT_GAME, 1, "anchors")
    anchors: Dict[str, int] = {}

    DataVariable(METADATA_FORMAT_GAME, 1, "scripts")
    scripts: Dict[str, str] = {}

    DataVariable(METADATA_FORMAT_GAME, 1, "installed")
    installed: List[str] = []

    DataVariable(METADATA_FORMAT_GAME, 1, "modifiedAnchorsMap")
    modifiedAnchorsMap: Dict[str, str] = {}

    # obfMappings: {modHash: if_blocks_string}
    # Stores each mod's contribution to getHandForCostume() so they can be
    # merged into one script without overwriting each other.
    DataVariable(METADATA_FORMAT_GAME, 1, "obfMappings")
    obfMappings: Dict[str, str] = {}



class GameSwf(GameSwfData):
    def __init__(self, gameFilePath: str):
        self.swfName = os.path.split(gameFilePath)[1]
        self.gameSwf = Swf(gameFilePath, autoload=False)

    def open(self):

        self.gameSwf.open()
        self._loadFileDataInternal()

    def _loadFileDataInternal(self):
        if self.gameSwf.metaData is None:
            self.gameSwf.addMetadata()
        else:
            self.loadFromJson(self.gameSwf.metaData.get())

        if getattr(self, "obfMappings", None) is None:
            self.obfMappings = {}
        if getattr(self, "scripts", None) is None:
            self.scripts = {}
        if getattr(self, "installed", None) is None:
            self.installed = []
        if getattr(self, "modifiedAnchorsMap", None) is None:
            self.modifiedAnchorsMap = {}
        if getattr(self, "anchors", None) is None:
            self.anchors = {}

    def save(self):

        self.gameSwf.metaData.set(self.getDict())
        self.gameSwf.save()


    def close(self):
        self.gameSwf.close()

    def loadFileData(self):
        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.gameSwf.open()
        
        self._loadFileDataInternal()

        if not fileOpen:
            self.gameSwf.close()

    def saveFileData(self):
        self.saveJsonFile()

    def addInstalledMod(self, modHash: str):
        if self.installed is None:
            self.installed = []
        if modHash not in self.installed:
            self.installed.append(modHash)

    def importScript(self, content: str, scriptAnchor: str, modHash: str):
        # Clone orig sprite
        if getattr(self, "scripts", None) is None:
            self.scripts = {}
        if getattr(self, "modifiedAnchorsMap", None) is None:
            self.modifiedAnchorsMap = {}

        if scriptAnchor not in self.scripts:
            origContent = self.gameSwf.getAS3(scriptAnchor)

            if origContent is None:
                return False

            self.scripts[scriptAnchor] = origContent

        success = self.gameSwf.setAS3(scriptAnchor, content)

        if success:
            self.modifiedAnchorsMap[scriptAnchor] = modHash
            return True

        else:
            return False

    # ------------------------------------------------------------------
    # Obf-merge: used when multiple hand-mods modify UI_MainMenu.swf.
    # Each mod contributes the if-statement lines from its getHandForCostume()
    # function. At install time the clean carrier SWF (with precompiled
    # bytecode for BrawlForgeSuite) is deployed if needed, and the simple
    # Obf script is regenerated cleanly without any compiler '§§' errors.
    # ------------------------------------------------------------------

    def _ensureCarrierInstalled(self):
        """If this is UI_MainMenu.swf and it does not have the BrawlForge carrier packs,
        back up the stock file and deploy the clean pre-compiled carrier SWF.
        Also patches the BrawlForgeSuite constants with hardcoded symbols from symbols.json."""
        if self.swfName.lower() != "ui_mainmenu.swf":
            return

        has_carrier = self.gameSwf.getAS3(_OBF_ANCHOR) is not None
        if not has_carrier and os.path.exists(CARRIER_UI_MAINMENU_PATH):
            stock_backup_path = self.gameSwf.swfPath + ".stock_backup"
            if not os.path.exists(stock_backup_path):
                shutil.copy2(self.gameSwf.swfPath, stock_backup_path)

            fileOpen = self.gameSwf.isOpen()
            if fileOpen:
                self.close()

            shutil.copy2(CARRIER_UI_MAINMENU_PATH, self.gameSwf.swfPath)
            self.open()

        # Always ensure BrawlForgeSuite has current hardcoded symbols after carrier is present
        if self.gameSwf.getAS3("tier_b/BrawlForgeSuite") is not None:
            self._patchBrawlForgeSymbols()

    def _patchBrawlForgeSymbols(self):
        """Writes the BrawlForgeSuite script with current hardcoded symbols into the game SWF.
        Called at install time and by the fix command to keep symbols up to date."""
        try:
            try:
                from ..utils.symbols_manager import resolve_and_update_symbols
                game_dir = os.path.dirname(self.gameSwf.swfPath) if self.gameSwf else None
                resolve_and_update_symbols(brawlhalla_dir=game_dir, force=False, trigger="CarrierDeploy")
            except Exception:
                pass
            as3_code = generate_brawlforge_suite_as()
            success = self.gameSwf.setAS3("tier_b/BrawlForgeSuite", as3_code)
            if success:
                print("[GameSwf] BrawlForgeSuite symbols patched with hardcoded props.", flush=True)
            else:
                print("[GameSwf] WARNING: BrawlForgeSuite setAS3 returned False.", flush=True)
        except Exception as exc:
            print(f"[GameSwf] ERROR patching BrawlForgeSuite symbols: {exc}", flush=True)

    def patch_brawlforge_symbols(self, new_symbols: dict = None) -> bool:
        """Public method: update BrawlForgeSuite constants in the live game SWF.
        Called by the fix command after resolve_brawlhalla_symbols() has been run.
        Returns True on success."""
        if self.swfName.lower() != "ui_mainmenu.swf":
            return False
        if self.gameSwf.getAS3(_OBF_ANCHOR) is None:
            return False  # Carrier not installed, nothing to patch
        try:
            was_open = self.gameSwf.isOpen()
            if not was_open:
                self.open()
            as3_code = generate_brawlforge_suite_as(new_symbols)
            ok = self.gameSwf.setAS3("tier_b/BrawlForgeSuite", as3_code)
            self.save()
            if not was_open:
                self.close()
            print(f"[GameSwf] BrawlForgeSuite re-patched with new symbols: {new_symbols}", flush=True)
            return ok
        except Exception as exc:
            print(f"[GameSwf] ERROR in patch_brawlforge_symbols: {exc}", flush=True)
            return False

    def importObfMappings(self, if_blocks: str, modHash: str):
        """Register `if_blocks` for *modHash* and regenerate the merged Obf script inside the clean carrier."""
        if getattr(self, "obfMappings", None) is None:
            self.obfMappings = {}
        self._ensureCarrierInstalled()
        self.obfMappings[modHash] = if_blocks
        self._regenerateObfScript(modHash)

    def _regenerateObfScript(self, triggeringModHash: str = ""):
        """Combine all obfMappings into initHandMap() and initPalettes() bodies and write it
        into the Obf script in the carrier SWF. Restores stock SWF when no mappings remain."""
        if getattr(self, "obfMappings", None) is None:
            self.obfMappings = {}
        if getattr(self, "scripts", None) is None:
            self.scripts = {}
        if getattr(self, "modifiedAnchorsMap", None) is None:
            self.modifiedAnchorsMap = {}

        hand_stmts = []
        palette_stmts = []
        pattern = re.compile(r'((?:handMap|colorMap|paletteMap)\s*\[[^\]]+\]\s*=\s*[^;]+;)', re.DOTALL)
        for block in self.obfMappings.values():
            if block:
                for m in pattern.finditer(block):
                    stmt = m.group(1).strip()
                    if stmt.startswith("paletteMap"):
                        palette_stmts.append(stmt)
                    else:
                        hand_stmts.append(stmt)

        if not hand_stmts and not palette_stmts:
            # All mods removed — reset Obf script to idle without copying/overwriting the whole SWF
            empty_script = (_OBF_SCRIPT_TEMPLATE
                            .replace("{INIT_MAP_LINES}", "")
                            .replace("{INIT_PALETTE_LINES}", ""))
            self.gameSwf.setAS3(_OBF_ANCHOR, empty_script)
            self.scripts.pop(_OBF_ANCHOR, None)
            self.modifiedAnchorsMap.pop(_OBF_ANCHOR, None)
            return

        # Ensure carrier is deployed before patching Obf
        self._ensureCarrierInstalled()

        def indent_code(code_str, num_spaces=9):
            ind = " " * num_spaces
            lines = []
            for l in code_str.splitlines():
                if l.strip():
                    lines.append(ind + l.strip())
            return "\n".join(lines)

        init_map_body = "\n".join(indent_code(s) for s in hand_stmts) if hand_stmts else ""
        init_palette_body = "\n".join(indent_code(s) for s in palette_stmts) if palette_stmts else ""

        merged_script = (_OBF_SCRIPT_TEMPLATE
                         .replace("{INIT_MAP_LINES}", init_map_body)
                         .replace("{INIT_PALETTE_LINES}", init_palette_body))

        print(f"[GameSwf DEBUG] Merged Obf.as script generated with {len(hand_stmts)} hand statement(s) and {len(palette_stmts)} palette statement(s).", flush=True)
        self.gameSwf.setAS3(_OBF_ANCHOR, merged_script)
        self.modifiedAnchorsMap[_OBF_ANCHOR] = triggeringModHash
        print(f"[GameSwf DEBUG] Obf.as written successfully to '{self.swfName}'.", flush=True)



    def importSound(self, sound: DefineSoundTag, soundAnchor: str, modHash: str):
        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()

        origSoundId = self.gameSwf.symbolClass.getTagByName(soundAnchor)
        if origSoundId is None:
            print(f"Error: Element '{soundAnchor}' not found!")
            return
        
        origSounds = self.gameSwf.getElementById(origSoundId, DefineSoundTag)
        if not origSounds:
            print(f"Error: Sound element '{soundAnchor}' not found in SWF!")
            return
        origSound = origSounds[0]

        # If orig not cloned
        if soundAnchor not in self.anchors:
            newOrigSoundId = self.gameSwf.getNextCharacterId()
            if self.gameSwf.symbolClass.getTag(newOrigSoundId) is not None:
                self.gameSwf.symbolClass.removeTag(newOrigSoundId)

            self.gameSwf.cloneAndAddElement(origSound, newOrigSoundId)
            self.anchors[soundAnchor] = newOrigSoundId

        cloneSound = sound.cloneTag()
        self.gameSwf.replaceElement(origSound, cloneSound)
        SetElementId(cloneSound, origSoundId)

        self.modifiedAnchorsMap[soundAnchor] = modHash

        if not fileOpen:
            self.close()

    def importSprite(self, sprite: DefineSpriteTag, spriteAnchor: str, modHash: str, elementsMap=None):
        fileOpen = self.gameSwf.isOpen()
        if elementsMap is None:
            elementsMap = {}
        cloneSprites = []
        cloneShapes = []

        if not fileOpen:
            self.open()

        origSpriteId = self.gameSwf.symbolClass.getTagByName(spriteAnchor)
        if origSpriteId is None:
            print(f"Error: Element '{spriteAnchor}' not found!")
            return
        
        origSprites = self.gameSwf.getElementById(origSpriteId, DefineSpriteTag)
        if not origSprites:
            print(f"Error: Sprite element '{spriteAnchor}' not found in SWF!")
            return
        origSprite = origSprites[0]

        # Remove modified sprite
        if spriteAnchor in self.anchors:
            for needElId in GetNeededCharactersId(origSprite):
                for needEl in self.gameSwf.getElementById(needElId):
                    self.gameSwf.removeElement(needEl)

        for needElement in [*GetNeededCharacters(sprite), sprite]:
            if GetElementId(needElement) not in elementsMap:
                if needElement == sprite:
                    # If orig cloned
                    if spriteAnchor not in self.anchors:
                        newOrigSpriteId = self.gameSwf.getNextCharacterId()
                        if self.gameSwf.symbolClass.getTag(newOrigSpriteId) is not None:
                            self.gameSwf.symbolClass.removeTag(newOrigSpriteId)

                        self.gameSwf.cloneAndAddElement(origSprite, newOrigSpriteId)
                        self.anchors[spriteAnchor] = newOrigSpriteId

                    newElId = origSpriteId
                    cloneEl = sprite.cloneTag()
                    self.gameSwf.replaceElement(origSprite, cloneEl)
                    SetElementId(cloneEl, origSpriteId)

                else:
                    newElId = self.gameSwf.getNextCharacterId()
                    cloneEl = self.gameSwf.cloneAndAddElement(needElement, newElId)

                    if self.gameSwf.symbolClass.getTag(newElId) is not None:
                        self.gameSwf.symbolClass.removeTag(newElId)

                elementsMap[GetElementId(needElement)] = newElId

                if isinstance(cloneEl, DefineShapeTags):
                    if GetShapeBitmapId(cloneEl) is not None:
                        cloneShapes.append(cloneEl)

                elif isinstance(cloneEl, DefineSpriteTag):
                    cloneSprites.append(cloneEl)

                if isinstance(cloneEl, DefineFontTags):
                    for dependentElement in GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                   (DefineFontNameTag,
                                                                                   DefineFontAlignZonesTag)):
                        self.gameSwf.cloneAndAddElement(dependentElement, newElId)

                elif isinstance(cloneEl, DefineEditTextTag):
                    if dependentElement := GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                  CSMTextSettingsTag):
                        self.gameSwf.cloneAndAddElement(dependentElement[0], newElId)
                    cloneEl.fontId = elementsMap[needElement.fontId]

                elif isinstance(cloneEl, DefineTextTag):
                    if dependentElement := GetSwfByElement(sprite).getElementById(GetElementId(needElement),
                                                                                  CSMTextSettingsTag):
                        self.gameSwf.cloneAndAddElement(dependentElement[0], newElId)

                    for textRecord in cloneEl.textRecords:
                        if textRecord.styleFlagsHasFont:
                            textRecord.fontId = elementsMap[textRecord.fontId]

        for cloneSprite in cloneSprites:
            for sEl in cloneSprite.getTags().iterator():
                if isinstance(sEl, PlaceObject2Tag) and sEl.characterId > 0:
                    SetElementId(sEl, elementsMap[sEl.characterId])
                elif isinstance(sEl, PlaceObject3Tag) and sEl.characterId > 0:
                    SetElementId(sEl, elementsMap[sEl.characterId])

        for cloneShape in cloneShapes:
            bitmapId = GetShapeBitmapId(cloneShape)
            SetShapeBitmapId(cloneShape, elementsMap[bitmapId])

        self.modifiedAnchorsMap[spriteAnchor] = modHash

        if not fileOpen:
            self.close()

    def uninstallMod(self, modHash: str):
        SendNotification(NotificationType.UninstallingModSwf, modHash, os.path.split(self.gameSwf.swfPath)[1])

        fileOpen = self.gameSwf.isOpen()
        if not fileOpen:
            self.open()

        if getattr(self, "obfMappings", None) is None:
            self.obfMappings = {}
        if getattr(self, "modifiedAnchorsMap", None) is None:
            self.modifiedAnchorsMap = {}
        if getattr(self, "scripts", None) is None:
            self.scripts = {}
        if getattr(self, "anchors", None) is None:
            self.anchors = {}

        # Remove Obf mapping for this mod and regenerate merged script
        if modHash in self.obfMappings:
            del self.obfMappings[modHash]
            self._regenerateObfScript()

        for anchor, _modHash in self.modifiedAnchorsMap.copy().items():
            if _modHash == modHash:
                # Skip _OBF_ANCHOR — managed dynamically above
                if anchor == _OBF_ANCHOR:
                    continue

                # Repair script
                if anchor in self.scripts:
                    self.gameSwf.setAS3(anchor, self.scripts[anchor])

                    self.scripts.pop(anchor, None)
                    self.modifiedAnchorsMap.pop(anchor, None)

                    continue

                # Repair sounds and sprites
                origElId = self.anchors.get(anchor)
                if origElId is None:
                    #print(f"Error: Orig element '{anchor}' not found!")
                    SendNotification(NotificationType.UninstallingModSwfOriginalElementNotFound,
                                     _modHash, anchor, self.swfName)
                    continue
                origEl = self.gameSwf.getElementById(origElId)

                if origEl:
                    origEl = origEl[0]
                else:
                    print("Error: origEl = origEl[0]")
                    continue

                modElId = self.gameSwf.symbolClass.getTagByName(anchor)
                if modElId is None:
                    #print(f"Error: Mod element '{modElId}' not found!")
                    SendNotification(NotificationType.UninstallingModSwfElementNotFound,
                                     _modHash, anchor, self.swfName)
                    continue
                modEl = self.gameSwf.getElementById(modElId)

                if modEl:
                    modEl = modEl[0]
                else:
                    print("Error: modEl = modEl[0]")
                    continue

                if isinstance(modEl, DefineSoundTag):
                    #print(f"Remove Sound {anchor}")
                    SendNotification(NotificationType.UninstallingModSwfSound, _modHash, anchor)

                    self.gameSwf.removeElement(origEl)
                    self.gameSwf.replaceElement(modEl, origEl)
                    self.gameSwf.removeElement(modEl)
                    SetElementId(origEl, modElId)

                    self.gameSwf.symbolClass.setTag(modElId, anchor)

                    self.anchors.pop(anchor, None)
                    self.modifiedAnchorsMap.pop(anchor, None)

                elif isinstance(modEl, DefineSpriteTag):
                    #print(f"Remove Sprite {anchor}")
                    SendNotification(NotificationType.UninstallingModSwfSprite, _modHash, anchor)

                    for needElId in GetNeededCharactersId(modEl):
                        for needEl in self.gameSwf.getElementById(needElId):
                            self.gameSwf.removeElement(needEl)

                    self.gameSwf.removeElement(origEl)
                    self.gameSwf.replaceElement(modEl, origEl)
                    self.gameSwf.removeElement(modEl)
                    SetElementId(origEl, modElId)

                    self.gameSwf.symbolClass.setTag(modElId, anchor)

                    self.anchors.pop(anchor, None)
                    self.modifiedAnchorsMap.pop(anchor, None)

        if modHash in self.installed:
            self.installed.remove(modHash)

        if not fileOpen:
            self.close()


GAME_SWFS: Dict[str, GameSwf] = {}


def GetGameFileClass(gameFileName: str) -> Union[GameSwf, None]:
    if gameFileName in GAME_SWFS:
        return GAME_SWFS[gameFileName]
    fn_lower = gameFileName.lower()
    for k, v in GAME_SWFS.items():
        if k.lower() == fn_lower:
            return v
    return None


for _fileName, _filePath in BRAWLHALLA_SWFS.items():
    if "(" not in _fileName and "—" not in _fileName:
        GAME_SWFS[_fileName] = GameSwf(_filePath)

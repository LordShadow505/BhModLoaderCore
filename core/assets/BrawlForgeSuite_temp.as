package tier_b
{
   import flash.Lib;
   import flash.display.DisplayObject;
   import flash.display.Stage;
   import flash.events.Event;
   import flash.events.KeyboardEvent;
   import flash.system.ApplicationDomain;
   import flash.text.TextField;
   import flash.text.TextFieldAutoSize;
   import flash.text.TextFormat;
   import flash.utils.describeType;
   import flash.utils.getDefinitionByName;
   import flash.utils.getQualifiedClassName;

   public class BrawlForgeSuite
   {
      public static var _kept:BrawlForgeSuite = null;
      public static var _stage:Stage = null;
      public static var _gc:* = null;
      public static var _handFile:String = "Gfx_Hands";
      public static var _debugText:TextField = null;
      public static var _costumesSynced:Boolean = false;
      public static var _palettesSynced:Boolean = false;

      // Discovered live symbols (pinned from runtime)
      public static var _costumeRegProp:String = "_-q5b";
      public static var _gfxProp:String = "_-P3J";
      public static var _artSuffixProp:String = "_-O3M";
      public static var _csClassProp:String = "_-G5Q";
      public static var _csRegProp:String = "_-44k";
      public static var _csColorsProp:String = "_-6y";
      public static var _gcProp:String = "_-13t";
      public static var _gcEntitiesProp:String = "_-13t";
      public static var _rebuildMethodName:String = "_-h4y";

      // Diagnostic tracking
      public static var _lastSyncCostumeCount:int = 0;
      public static var _lastSyncHandMatches:int = 0;
      public static var _lastSyncPaletteMatches:int = 0;
      public static var _lastEntityCostume:String = "None";
      public static var _lastEntityScheme:String = "None";
      public static var _lastEntityHandWanted:String = "None";
      public static var _lastEntityHandApplied:String = "None";
      public static var _lastRebuildStatus:String = "None";
      public static var _lastErrorMsg:String = "None";

      public static const KNOWN_COSTUME_REGS:Array = ["_-q5b", "_-22J", "_-M6b", "_-X4Q", "_-P1I"];
      public static const KNOWN_COSTUME_HANDS:Array = ["_-P3J", "_-v1x", "_-bC", "_-gK", "_-k3B", "_-l45"];
      public static const KNOWN_ART_PROPS:Array = ["_-O3M", "_-Fk", "_-Qe", "_-K3w", "symbolSuffix"];
      public static const KNOWN_CS_CLASSES:Array = ["_-G5Q", "_-d14", "_-V4w", "_-W3s", "_-R53", "ColorSchemeType"];
      public static const KNOWN_CS_REGS:Array = ["_-44k", "_-w5Q", "_-p5j", "_-Q4s", "_-S1l", "_-V1h", "_-Q6c", "_-o17"];
      public static const KNOWN_CS_COLORS:Array = ["_-6y", "_-S5J", "_-I4B", "_-Z1S", "colors"];
      public static const KNOWN_CS_IDS:Array = ["_-C5B", "_-g1E", "_-9U", "mColorSchemeID"];
      public static const KNOWN_GC_PROPS:Array = ["_-13t", "_-o4J", "_-819", "_-84x", "gc"];
      public static const KNOWN_GC_ENTITIES:Array = ["_-13t", "_-t5r", "entities"];

      private static var _cachedCostumeTypeClass:Class = null;
      private static var _cachedCSClass:Class = null;
      private static var _cachedCostumeRegistry:* = null;
      private static var _cachedCSRegistry:* = null;

      public var _frames:int = 0;

      public function BrawlForgeSuite()
      {
         _frames = 0;
         if (BrawlForgeSuite._stage != null)
         {
            BrawlForgeSuite._stage.addEventListener(Event.ENTER_FRAME, onEnterFrame, false, 0, false);
         }
      }

      public static function start(param1:Stage) : Boolean
      {
         if (BrawlForgeSuite._kept != null)
         {
            return true;
         }
         if (param1 == null)
         {
            return false;
         }
         try { Obf.initHandMap(); } catch(e1:Error) { _lastErrorMsg = "Obf.initHandMap: " + e1.message; }
         try { Obf.initPalettes(); } catch(e2:Error) { _lastErrorMsg = "Obf.initPalettes: " + e2.message; }
         try { BrawlForgeSuite._handFile = Obf.handFile(); } catch(e3:Error) { BrawlForgeSuite._handFile = "Gfx_Hands"; }

         BrawlForgeSuite._stage = param1;
         BrawlForgeSuite._stage.addEventListener(KeyboardEvent.KEY_DOWN, onKeyDown, false, 0, false);

         syncGlobalCostumes();
         syncGlobalPalettes();

         BrawlForgeSuite._kept = new BrawlForgeSuite();
         return true;
      }

      public static function onKeyDown(e:KeyboardEvent) : void
      {
         if (e.keyCode == 123)
         {
            toggleDebugOverlay();
         }
      }

      public static function getCostumeTypeClass() : Class
      {
         if (_cachedCostumeTypeClass != null) return _cachedCostumeTypeClass;
         try { _cachedCostumeTypeClass = Class(getDefinitionByName("CostumeType")); if (_cachedCostumeTypeClass != null) return _cachedCostumeTypeClass; } catch(e0:Error) {}
         try { if (ApplicationDomain.currentDomain != null) _cachedCostumeTypeClass = Class(ApplicationDomain.currentDomain.getDefinition("CostumeType")); } catch(e1:Error) {}
         if (_cachedCostumeTypeClass == null && Lib.current != null && Lib.current.loaderInfo != null)
         {
            try { _cachedCostumeTypeClass = Class(Lib.current.loaderInfo.applicationDomain.getDefinition("CostumeType")); } catch(e2:Error) {}
         }
         return _cachedCostumeTypeClass;
      }

      public static function getCostumeRegistry() : *
      {
         if (_cachedCostumeRegistry != null) return _cachedCostumeRegistry;

         var ctClass:Class = getCostumeTypeClass();
         if (ctClass == null) return null;

         try
         {
            if (ctClass[_costumeRegProp] != null && ctClass[_costumeRegProp].length > 20)
            {
               _cachedCostumeRegistry = ctClass[_costumeRegProp];
               return _cachedCostumeRegistry;
            }
         }
         catch(e0:Error) {}

         for (var i:int = 0; i < KNOWN_COSTUME_REGS.length; i++)
         {
            var prop:String = String(KNOWN_COSTUME_REGS[i]);
            try
            {
               if (ctClass[prop] != null && ctClass[prop].length > 20)
               {
                  _costumeRegProp = prop;
                  _cachedCostumeRegistry = ctClass[prop];
                  return _cachedCostumeRegistry;
               }
            }
            catch(e:Error) {}
         }
         return null;
      }

      public static function getColorSchemeClass() : Class
      {
         if (_cachedCSClass != null) return _cachedCSClass;

         for (var i:int = 0; i < KNOWN_CS_CLASSES.length; i++)
         {
            var cn:String = String(KNOWN_CS_CLASSES[i]);
            var cls:Class = null;
            try { cls = Class(getDefinitionByName(cn)); } catch(e0:Error) {}
            if (cls == null && ApplicationDomain.currentDomain != null)
            {
               try { cls = Class(ApplicationDomain.currentDomain.getDefinition(cn)); } catch(e1:Error) {}
            }
            if (cls != null)
            {
               _cachedCSClass = cls;
               _csClassProp = cn;
               return _cachedCSClass;
            }
         }
         return null;
      }

      public static function getColorSchemeRegistry() : *
      {
         if (_cachedCSRegistry != null) return _cachedCSRegistry;

         var cls:Class = getColorSchemeClass();
         if (cls == null) return null;

         try
         {
            if (cls[_csRegProp] != null && cls[_csRegProp].length > 20)
            {
               _cachedCSRegistry = cls[_csRegProp];
               return _cachedCSRegistry;
            }
         }
         catch(e0:Error) {}

         for (var ri:int = 0; ri < KNOWN_CS_REGS.length; ri++)
         {
            var rp:String = String(KNOWN_CS_REGS[ri]);
            try
            {
               if (cls[rp] != null && cls[rp].length > 20)
               {
                  _csRegProp = rp;
                  _cachedCSRegistry = cls[rp];
                  return _cachedCSRegistry;
               }
            }
            catch(eR:Error) {}
         }
         return null;
      }

      public static function getSchemeColorsArray(scheme:*) : *
      {
         if (scheme == null) return null;
         try
         {
            if (scheme[_csColorsProp] != null && scheme[_csColorsProp].length > 5)
            {
               return scheme[_csColorsProp];
            }
         }
         catch(e0:Error) {}

         for (var k:int = 0; k < KNOWN_CS_COLORS.length; k++)
         {
            var cp:String = String(KNOWN_CS_COLORS[k]);
            try
            {
               if (scheme[cp] != null && scheme[cp].length > 5)
               {
                  _csColorsProp = cp;
                  return scheme[cp];
               }
            }
            catch(e:Error) {}
         }
         return null;
      }

      public static function handArtOf(target:*) : *
      {
         if (target == null) return null;

         var gfx:* = null;
         try { gfx = target[_gfxProp]; } catch(e0:Error) {}
         if (gfx == null)
         {
            for (var i:int = 0; i < KNOWN_COSTUME_HANDS.length; i++)
            {
               var prop:String = String(KNOWN_COSTUME_HANDS[i]);
               try
               {
                  if (target[prop] != null)
                  {
                     gfx = target[prop];
                     _gfxProp = prop;
                     break;
                  }
               }
               catch(e:Error) {}
            }
         }

         if (gfx == null) return null;

         var arts:* = null;
         try { if (gfx["_-P3t"] != null) arts = gfx["_-P3t"]; } catch(e1:Error) {}
         if (arts == null) { try { if (gfx["_-Q4B"] != null) arts = gfx["_-Q4B"]; } catch(e2:Error) {} }
         if (arts == null) { try { if (gfx.customArt != null) arts = gfx.customArt; } catch(e3:Error) {} }

         if (arts == null) return null;

         var len:int = int(arts.length);
         for (var k:int = 0; k < len; k++)
         {
            var entry:* = arts[k];
            if (entry != null && ("fileName" in entry) && (String(entry.fileName).indexOf("Gfx_Hands") >= 0 || entry.fileName == BrawlForgeSuite._handFile))
            {
               return entry;
            }
         }
         return null;
      }

      public static function getHandArtSuffix(art:*) : String
      {
         if (art == null) return "null";
         try
         {
            if (art[_artSuffixProp] != null) return String(art[_artSuffixProp]);
         }
         catch(e0:Error) {}
         for (var k:int = 0; k < KNOWN_ART_PROPS.length; k++)
         {
            var kp:String = String(KNOWN_ART_PROPS[k]);
            try
            {
               if (kp in art && art[kp] != null)
               {
                  _artSuffixProp = kp;
                  return String(art[kp]);
               }
            }
            catch(eK:Error) {}
         }
         return "Unknown";
      }

      public static function setHandArt(art:*, wanted:String) : void
      {
         if (art == null || wanted == null) return;

         if (_artSuffixProp != "" && _artSuffixProp != "fileName")
         {
            try { art[_artSuffixProp] = wanted; return; } catch(e0:Error) {}
         }

         for (var k:int = 0; k < KNOWN_ART_PROPS.length; k++)
         {
            var kp:String = String(KNOWN_ART_PROPS[k]);
            try
            {
               if (kp in art)
               {
                  art[kp] = wanted;
                  _artSuffixProp = kp;
                  return;
               }
            }
            catch(eK:Error) {}
         }
      }

      public static function syncGlobalCostumes() : void
      {
         var reg:* = getCostumeRegistry();
         if (reg == null || Obf.handMap == null) return;

         var len:int = int(reg.length);
         _lastSyncCostumeCount = len;
         var matches:int = 0;
         for (var i:int = 0; i < len; i++)
         {
            var ct:* = reg[i];
            if (ct != null && ("mCostumeName" in ct) && ct.mCostumeName != null)
            {
               var wanted:String = Obf.getHandForCostume(ct.mCostumeName);
               if (wanted != null)
               {
                  var art:* = handArtOf(ct);
                  if (art != null)
                  {
                     setHandArt(art, wanted);
                     matches++;
                  }
               }
            }
         }
         _lastSyncHandMatches = matches;
         _costumesSynced = true;
      }

      public static function applyPaletteColors(schemeObj:*, customPalette:Array) : void
      {
         if (schemeObj == null || customPalette == null) return;

         var colList:* = getSchemeColorsArray(schemeObj);
         if (colList != null && ("length" in colList) && colList.length > 5)
         {
            var csClass:Class = getColorSchemeClass();
            var channels:Array = null;
            try { channels = Obf.paletteChannels(); } catch(eCh:Error) {}

            if (csClass != null && channels != null && channels.length > 0)
            {
               var cnt:int = int(Math.min(channels.length, customPalette.length));
               for (var i:int = 0; i < cnt; i++)
               {
                  var chName:String = String(channels[i]);
                  var targetVal:uint = uint(customPalette[i]) & 0xFFFFFF;
                  var slot:int = -1;
                  try { slot = csClass["_-p3"](chName + "_Swap", "_Swap"); } catch(eSlot:Error) {}
                  if (slot >= 0 && slot < colList.length)
                  {
                     colList[slot] = targetVal;
                  }
               }
            }
            else
            {
               var nCols:int = int(Math.min(colList.length, customPalette.length));
               for (var c:int = 0; c < nCols; c++)
               {
                  colList[c] = (uint(customPalette[c]) & 0xFFFFFF);
               }
            }
         }
      }

      public static function syncGlobalPalettes() : void
      {
         if (Obf.paletteMap == null) return;

         var reg:* = getColorSchemeRegistry();
         if (reg == null) return;

         var rLen:int = int(reg.length);
         var matches:int = 0;

         for (var key:String in Obf.paletteMap)
         {
            var targetScheme:* = null;
            var sId:int = int(key);
            if (sId > 0 && sId < rLen)
            {
               targetScheme = reg[sId];
            }

            if (targetScheme == null)
            {
               for (var ri:int = 0; ri < rLen; ri++)
               {
                  var sItem:* = reg[ri];
                  if (sItem != null)
                  {
                     try
                     {
                        if (("mColorSchemeName" in sItem) && sItem.mColorSchemeName == key)
                        {
                           targetScheme = sItem;
                           break;
                        }
                     }
                     catch(eName:Error) {}
                     try
                     {
                        if (("mColorSchemeID" in sItem) && sItem.mColorSchemeID == sId)
                        {
                           targetScheme = sItem;
                           break;
                        }
                     }
                     catch(eId:Error) {}
                  }
               }
            }

            if (targetScheme != null)
            {
               var customPal:Array = Obf.paletteMap[key] as Array;
               if (customPal != null)
               {
                  applyPaletteColors(targetScheme, customPal);
                  matches++;
               }
            }
         }
         _lastSyncPaletteMatches = matches;
         _palettesSynced = true;
      }

      public static function findGameController() : *
      {
         if (BrawlForgeSuite._gc != null) return BrawlForgeSuite._gc;
         if (BrawlForgeSuite._stage == null) return null;

         var numC:int = BrawlForgeSuite._stage.numChildren;
         for (var i:int = 0; i < numC; i++)
         {
            var child:DisplayObject = BrawlForgeSuite._stage.getChildAt(i);
            if (child == null) continue;

            try
            {
               if (child[_gcProp] != null)
               {
                  BrawlForgeSuite._gc = child[_gcProp];
                  return BrawlForgeSuite._gc;
               }
            }
            catch(e0:Error) {}

            for (var k:int = 0; k < KNOWN_GC_PROPS.length; k++)
            {
               var prop:String = String(KNOWN_GC_PROPS[k]);
               try
               {
                  if (child[prop] != null)
                  {
                     _gcProp = prop;
                     BrawlForgeSuite._gc = child[prop];
                     return BrawlForgeSuite._gc;
                  }
               }
               catch(eK:Error) {}
            }
         }
         return null;
      }

      public static function getGCEntities(gc:*) : *
      {
         if (gc == null) return null;
         try
         {
            var ents:* = gc[_gcEntitiesProp];
            if (ents != null && ("length" in ents) && ents.length > 0) return ents;
         }
         catch(e0:Error) {}

         for (var k:int = 0; k < KNOWN_GC_ENTITIES.length; k++)
         {
            var ep:String = String(KNOWN_GC_ENTITIES[k]);
            try
            {
               var v:* = gc[ep];
               if (v != null && ("length" in v) && v.length > 0)
               {
                  _gcEntitiesProp = ep;
                  return v;
               }
            }
            catch(eK:Error) {}
         }
         return null;
      }

      private static var _entCostumeProp:String = "";
      private static var _entSchemeProp:String = "";

      public static function tickEntities() : void
      {
         var gc:* = findGameController();
         if (gc == null) return;

         var entities:* = getGCEntities(gc);
         if (entities == null) return;

         var eLen:int = int(entities.length);
         for (var i:int = 0; i < eLen; i++)
         {
            var ent:* = entities[i];
            if (ent != null)
            {
               var costume:* = null;
               var scheme:* = null;

               if (_entCostumeProp != "")
               {
                  try { costume = ent[_entCostumeProp]; } catch(eC0:Error) {}
               }
               if (_entSchemeProp != "")
               {
                  try { scheme = ent[_entSchemeProp]; } catch(eS0:Error) {}
               }

               if (costume == null)
               {
                  try
                  {
                     var entXml:XML = describeType(ent);
                     for each (var node:XML in (entXml.variable + entXml.accessor))
                     {
                        var pName:String = node.@name.toString();
                        try
                        {
                           var val:* = ent[pName];
                           if (val != null && typeof val == "object")
                           {
                              if ("mCostumeName" in val && val.mCostumeName != null)
                              {
                                 costume = val;
                                 _entCostumeProp = pName;
                              }
                              if ("mColorSchemeName" in val && val.mColorSchemeName != null)
                              {
                                 scheme = val;
                                 _entSchemeProp = pName;
                              }
                           }
                        }
                        catch(eP:Error) {}
                     }
                  }
                  catch(eEnt:Error) { _lastErrorMsg = "tickEntities describeType: " + eEnt.message; }
               }

               var didChange:Boolean = false;

               // 1. Hands update
               if (costume != null && ("mCostumeName" in costume) && costume.mCostumeName != null)
               {
                  _lastEntityCostume = String(costume.mCostumeName);
                  var wanted:String = Obf.getHandForCostume(costume.mCostumeName);
                  _lastEntityHandWanted = wanted != null ? wanted : "None (No map)";
                  if (wanted != null)
                  {
                     var art:* = handArtOf(costume);
                     if (art != null)
                     {
                        setHandArt(art, wanted);
                        _lastEntityHandApplied = wanted + " (Costume Art)";
                        didChange = true;
                     }
                     // Also apply directly to entity's own GfxType
                     var entArt:* = handArtOf(ent);
                     if (entArt != null)
                     {
                        setHandArt(entArt, wanted);
                        _lastEntityHandApplied = wanted + " (Entity Art)";
                        didChange = true;
                     }
                  }
               }

               // 2. Palette / Color update on active entity scheme
               if (scheme != null && Obf.paletteMap != null)
               {
                  var sName:String = ("mColorSchemeName" in scheme) ? String(scheme.mColorSchemeName) : "";
                  var sId:int = ("mColorSchemeID" in scheme) ? int(scheme.mColorSchemeID) : -1;
                  _lastEntityScheme = sName + " (#" + sId + ")";
                  var customPal:Array = null;

                  if (sName != "" && Obf.paletteMap[sName] != null) customPal = Obf.paletteMap[sName] as Array;
                  if (customPal == null && sId >= 0 && Obf.paletteMap[String(sId)] != null) customPal = Obf.paletteMap[String(sId)] as Array;

                  if (customPal != null)
                  {
                     applyPaletteColors(scheme, customPal);
                     didChange = true;
                  }
               }

               // Trigger rebuildAppearance
               if (didChange && costume != null)
               {
                  try
                  {
                     if (_rebuildMethodName != "")
                     {
                        ent[_rebuildMethodName](costume, scheme, true);
                        _lastRebuildStatus = "SUCCESS (" + _rebuildMethodName + ")";
                     }
                     else
                     {
                        var entXml2:XML = describeType(ent);
                        for each (var mNode:XML in entXml2.method)
                        {
                           var mName:String = mNode.@name.toString();
                           var mParams:XMLList = mNode.parameter;
                           if (mParams.length() == 3)
                           {
                              try
                              {
                                 ent[mName](costume, scheme, true);
                                 _rebuildMethodName = mName;
                                 _lastRebuildStatus = "DISCOVERED & INVOKED (" + mName + ")";
                                 break;
                              }
                              catch(eReb:Error) { _lastErrorMsg = "rebuildAppearance invoke error: " + eReb.message; }
                           }
                        }
                     }
                  }
                  catch(eMainReb:Error)
                  {
                     _lastRebuildStatus = "FAILED: " + eMainReb.message;
                     _lastErrorMsg = "rebuildAppearance: " + eMainReb.message;
                  }
               }
            }
         }
      }

      public static function updateDebugText() : void
      {
         if (_debugText == null || !_debugText.visible) return;

         var report:String = "";
         try
         {
            report += "======================== BRAWL FORGE LIVE PROBE (F12) ========================\n";

            // 1. Mod Config
            report += "--- [1] CONFIGURACION DE LA MODIFICACION (Obf.as) ---\n";
            try {
               if (Obf.handMap != null)
               {
                  var hCount:int = 0;
                  for (var hk:String in Obf.handMap)
                  {
                     report += "   * Hand: \"" + hk + "\" -> \"" + Obf.handMap[hk] + "\"\n";
                     hCount++;
                  }
                  if (hCount == 0) report += "   * Hand Map is EMPTY\n";
               }
               else
               {
                  report += "   * Obf.handMap is NULL\n";
               }
               if (Obf.paletteMap != null)
               {
                  var pCountTotal:int = 0;
                  for (var pk:String in Obf.paletteMap)
                  {
                     var plist:Array = Obf.paletteMap[pk] as Array;
                     var pCount:int = (plist != null) ? plist.length : 0;
                     report += "   * Palette Key \"" + pk + "\" (" + pCount + " channels overwritten)\n";
                     pCountTotal++;
                  }
                  if (pCountTotal == 0) report += "   * Palette Map is EMPTY\n";
               }
               else
               {
                  report += "   * Obf.paletteMap is NULL\n";
               }
            } catch(e1:Error) {
               report += " [Error reading Obf.as]: " + e1.message + "\n";
            }

            // 2. Discovered Live Symbols
            report += "\n--- [2] PINNED LIVE SYMBOLS (170+ FPS DIRECT ACCESS) ---\n";
            var _loc2_:* = getCostumeRegistry();
            var regCount:int = (_loc2_ != null) ? _loc2_.length : 0;
            report += " Costume Registry: Prop '" + _costumeRegProp + "' -> FOUND (" + regCount + " Costumes | " + _lastSyncHandMatches + " Hand Targets Synced)\n";
            report += " Costume GfxType Prop: '" + _gfxProp + "' | Art Suffix Prop: '" + _artSuffixProp + "' (File: '" + _handFile + "')\n";

            var _csReg:* = getColorSchemeRegistry();
            var csCount:int = (_csReg != null) ? _csReg.length : 0;
            report += " ColorScheme Class: '" + _csClassProp + "' | Registry Prop: '" + _csRegProp + "' -> FOUND (" + csCount + " Schemes | " + _lastSyncPaletteMatches + " Palettes Synced)\n";

            // 3. Stage Display Hierarchy & GameController
            report += "\n--- [3] GAME CONTROLLER & ENTITY STATE ---\n";
            var liveGc:* = findGameController();
            if (liveGc != null)
            {
               var entsList:* = getGCEntities(liveGc);
               var liveCount:int = (entsList != null && ("length" in entsList)) ? int(entsList.length) : 0;
               report += " Game Controller: HOOKED (Prop: '" + _gcProp + "' | Entities Prop: '" + _gcEntitiesProp + "' [" + liveCount + " Entities Active])\n";
               report += " Active Fighter Costume: " + _lastEntityCostume + "\n";
               report += " Active Fighter Scheme:  " + _lastEntityScheme + "\n";
               report += " Hand Map Lookup Wanted: " + _lastEntityHandWanted + "\n";
               report += " Hand Art Suffix Applied: " + _lastEntityHandApplied + "\n";
               report += " RebuildAppearance Call: " + _lastRebuildStatus + "\n";
            }
            else
            {
               report += " Game Controller: Waiting for Character Select / Match.\n";
            }

            report += "\n--- [4] SYNCHRONIZATION & ERROR DIAGNOSTICS ---\n";
            report += " Costumes Synced in Memory: " + (_costumesSynced ? "YES" : "NO") + "\n";
            report += " Palettes Synced in Memory: " + (_palettesSynced ? "YES" : "NO") + "\n";
            report += " Last System Error: " + _lastErrorMsg + "\n";
            report += "===============================================================\n";
         }
         catch(topErr:Error)
         {
            report += "CRITICAL PROBE ERROR: " + topErr.message + "\n";
         }
         _debugText.text = report;
      }

      public static function toggleDebugOverlay() : void
      {
         if (_debugText == null)
         {
            if (BrawlForgeSuite._stage == null) return;
            _debugText = new TextField();
            _debugText.defaultTextFormat = new TextFormat("Consolas", 11, 65280, true);
            _debugText.background = true;
            _debugText.backgroundColor = 2566914048;
            _debugText.border = true;
            _debugText.borderColor = 65280;
            _debugText.autoSize = TextFieldAutoSize.NONE;
            _debugText.width = 980;
            _debugText.height = 640;
            _debugText.x = 20;
            _debugText.y = 20;
            _debugText.selectable = false;
            _debugText.mouseEnabled = false;
            _debugText.wordWrap = true;
            _debugText.multiline = true;
            _debugText.visible = true;
            BrawlForgeSuite._stage.addChild(_debugText);
         }
         else
         {
            _debugText.visible = !_debugText.visible;
            if (_debugText.visible && _debugText.parent != null)
            {
               _debugText.parent.setChildIndex(_debugText, _debugText.parent.numChildren - 1);
            }
         }
         updateDebugText();
      }

      public function onEnterFrame(e:Event) : void
      {
         _frames++;
         if (!_costumesSynced || _frames % 60 == 0)
         {
            syncGlobalCostumes();
         }
         if (!_palettesSynced || _frames % 60 == 0)
         {
            syncGlobalPalettes();
         }
         tickEntities();

         if (_debugText != null && _debugText.visible && _frames % 15 == 0)
         {
            updateDebugText();
         }
      }
   }
}

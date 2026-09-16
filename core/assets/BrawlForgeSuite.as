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
      // -----------------------------------------------------------------------
      // Hardcoded symbol constants -- updated by the Fix command when the game updates.
      // These are filled in by brawlforge_template.py at carrier build time.
      // -----------------------------------------------------------------------
      public static const COSTUME_REG_PROP:String    = "%%COSTUME_REG_PROP%%";
      public static const GFX_PROP:String            = "%%GFX_PROP%%";
      public static const ART_SUFFIX_PROP:String     = "%%ART_SUFFIX_PROP%%";
      public static const CS_CLASS_NAME:String       = "%%CS_CLASS_NAME%%";
      public static const CS_REG_PROP:String         = "%%CS_REG_PROP%%";
      public static const CS_COLORS_PROP:String      = "%%CS_COLORS_PROP%%";
      public static const GC_PROP:String             = "%%GC_PROP%%";
      public static const GC_ENTITIES_PROP:String    = "%%GC_ENTITIES_PROP%%";

      // Known hand type values -- used to identify art suffix prop when hardcoded is wrong
      public static const KNOWN_HAND_TYPES:Array = [
         "Bare","Padded","Glove","Reptile","Hoof","Gauntlet","Fist","Hook","Mitten","Default"
      ];

      public static var _kept:BrawlForgeSuite = null;
      public static var _stage:Stage = null;
      public static var _gc:* = null;
      public static var _handFile:String = "Gfx_Hands";
      public static var _debugText:TextField = null;
      public static var _costumesSynced:Boolean = false;
      public static var _palettesSynced:Boolean = false;

      // Runtime-discovered overrides (cached after one-time startup probe)
      public static var _artSuffixPropResolved:String = "";
      public static var _csColorsProp:String = "";

      // Diagnostic
      public static var _diagCostumeCount:int = 0;
      public static var _diagHandMatches:int = 0;
      public static var _diagCSCount:int = 0;
      public static var _diagPatchedSchemes:Array = [];

      public var _frames:int = 0;

      public function BrawlForgeSuite()
      {
         super();
         this._frames = 0;
         if(BrawlForgeSuite._stage != null)
         {
            BrawlForgeSuite._stage.addEventListener(Event.ENTER_FRAME, this.onEnterFrame, false, 0, false);
         }
      }

      public static function start(param1:Stage) : Boolean
      {
         if(BrawlForgeSuite._kept != null)
         {
            return true;
         }
         if(param1 == null)
         {
            return false;
         }
         try { Obf.initHandMap(); } catch(e1:Error) {}
         try { Obf.initPalettes(); } catch(e2:Error) {}
         try { BrawlForgeSuite._handFile = Obf.handFile(); } catch(e3:Error) { BrawlForgeSuite._handFile = "Gfx_Hands"; }

         BrawlForgeSuite._stage = param1;
         BrawlForgeSuite._stage.addEventListener(KeyboardEvent.KEY_DOWN, onKeyDown, false, 0, false);

         // Sync once at startup using hardcoded props (fast path)
         syncGlobalCostumes();
         syncGlobalPalettes();

         BrawlForgeSuite._kept = new BrawlForgeSuite();
         return true;
      }

      public static function onKeyDown(e:KeyboardEvent) : void
      {
         if(e.keyCode == 123) { toggleDebugOverlay(); }
      }

      // -----------------------------------------------------------------------
      // Fast-path: use hardcoded constants directly.
      // -----------------------------------------------------------------------

      public static function getCostumeRegistry() : *
      {
         var ctClass:Class = null;
         try { ctClass = Class(getDefinitionByName("CostumeType")); } catch(e:Error) {}
         if(ctClass == null)
         {
            try { ctClass = Class(ApplicationDomain.currentDomain.getDefinition("CostumeType")); } catch(e2:Error) {}
         }
         if(ctClass == null)
         {
            return null;
         }
         try
         {
            var reg:* = null;
            try { reg = ctClass["_-K2u"]; } catch(e1:Error) {}
            if(reg == null) { try { reg = ctClass["_-22J"]; } catch(e2:Error) {} }
            if(reg == null) { try { reg = ctClass["_-q5b"]; } catch(e3:Error) {} }
            if(reg == null && COSTUME_REG_PROP.length > 0) { try { reg = ctClass[COSTUME_REG_PROP]; } catch(e4:Error) {} }
            if(reg != null && "length" in reg && int(reg.length) > 20)
            {
               _diagCostumeCount = int(reg.length);
               return reg;
            }
         }
         catch(e:Error) {}
         return null;
      }

      public static function getColorSchemeClass() : Class
      {
         var csClass:Class = null;

         // 1. Direct getDefinitionByName (searches current and root application domains)
         try { csClass = Class(getDefinitionByName("_-G5Q")); } catch(e1:Error) {}
         if(csClass == null && CS_CLASS_NAME.length > 0) { try { csClass = Class(getDefinitionByName(CS_CLASS_NAME)); } catch(e2:Error) {} }
         if(csClass == null) { try { csClass = Class(getDefinitionByName("ColorSchemeType")); } catch(e3:Error) {} }

         // 2. ApplicationDomain.currentDomain and its parentDomain chain
         if(csClass == null)
         {
            try
            {
               var curAD:ApplicationDomain = ApplicationDomain.currentDomain;
               while(curAD != null && csClass == null)
               {
                  try
                  {
                     if(curAD.hasDefinition("_-G5Q")) { csClass = Class(curAD.getDefinition("_-G5Q")); }
                     else if(CS_CLASS_NAME.length > 0 && curAD.hasDefinition(CS_CLASS_NAME)) { csClass = Class(curAD.getDefinition(CS_CLASS_NAME)); }
                     else if(curAD.hasDefinition("ColorSchemeType")) { csClass = Class(curAD.getDefinition("ColorSchemeType")); }
                  }
                  catch(eCur:Error) {}
                  curAD = curAD.parentDomain;
               }
            }
            catch(eP:Error) {}
         }

         // 3. Stage loaderInfo domain
         if(csClass == null && _stage != null && _stage.loaderInfo != null && _stage.loaderInfo.applicationDomain != null)
         {
            try
            {
               var sAD:ApplicationDomain = _stage.loaderInfo.applicationDomain;
               if(sAD != null)
               {
                  if(sAD.hasDefinition("_-G5Q")) { csClass = Class(sAD.getDefinition("_-G5Q")); }
                  else if(CS_CLASS_NAME.length > 0 && sAD.hasDefinition(CS_CLASS_NAME)) { csClass = Class(sAD.getDefinition(CS_CLASS_NAME)); }
                  else if(sAD.hasDefinition("ColorSchemeType")) { csClass = Class(sAD.getDefinition("ColorSchemeType")); }
               }
            }
            catch(eS:Error) {}
         }

         return csClass;
      }

      public static function getColorSchemeRegistry() : *
      {
         var csClass:Class = getColorSchemeClass();
         if(csClass != null)
         {
            var regProps:Array = ["_-44k", CS_REG_PROP, "_-04k", "_-L5p", "_-S6b", "_-p5j", "_-Q4s", "_-S1l"];
            for each(var rp:String in regProps)
            {
               if(rp == null || rp.length == 0) continue;
               try
               {
                  var cand:* = csClass[rp];
                  if(cand != null && "length" in cand && int(cand.length) > 10)
                  {
                     _diagCSCount = int(cand.length);
                     return cand;
                  }
               }
               catch(eP:Error) {}
            }

            // Reflect on csClass to find any static Array with length > 10
            try
            {
               var xml:XML = describeType(csClass);
               for each(var node:XML in xml.variable + xml.accessor)
               {
                  var pn:String = node.@name.toString();
                  try
                  {
                     var v:* = csClass[pn];
                     if(v != null && "length" in v && int(v.length) > 10)
                     {
                        _diagCSCount = int(v.length);
                        return v;
                     }
                  }
                  catch(eV:Error) {}
               }
            }
            catch(eDesc:Error) {}
         }
         return null;
      }

      // -----------------------------------------------------------------------
      // handArtOf: get the ArtData entry whose fileName == _handFile
      // -----------------------------------------------------------------------
      public static function handArtOf(param1:*) : *
      {
         if(param1 == null) { return null; }
         var gfx:* = null;
         try { gfx = param1["_-P3J"]; } catch(e1:Error) {}
         if(gfx == null) { try { gfx = param1["_-v1x"]; } catch(e2:Error) {} }
         if(gfx == null) { try { gfx = param1["_-X64"]; } catch(e3:Error) {} }
         if(gfx == null && GFX_PROP.length > 0) { try { gfx = param1[GFX_PROP]; } catch(e4:Error) {} }
         if(gfx == null) { return null; }

         var arts:* = null;
         try
         {
            arts = tryGetArtsList(gfx);
         }
         catch(e:Error) {}
         if(arts == null || !("length" in arts)) { return null; }

         var j:int = 0;
         var len:int = int(arts.length);
         while(j < len)
         {
            var entry:* = arts[j];
            if(entry != null && "fileName" in entry && String(entry.fileName) == BrawlForgeSuite._handFile)
            {
               return entry;
            }
            j++;
         }
         return null;
      }

      private static var _artListProp:String = "";

      public static function tryGetArtsList(gfx:*) : *
      {
         if(_artListProp.length > 0)
         {
            try
            {
               var fast:* = gfx[_artListProp];
               if(fast != null && "length" in fast && int(fast.length) > 0) { return fast; }
            }
            catch(e:Error) {}
         }
         // Reflect once to find the arts list property
         try
         {
            var xml:XML = describeType(gfx);
            for each(var node:XML in xml.variable + xml.accessor)
            {
               var pn:String = node.@name.toString();
               var pt:String = node.@type.toString();
               if(pt.indexOf("Vector.") >= 0 || pt.indexOf("Array") >= 0 || pt == "*")
               {
                  try
                  {
                     var v:* = gfx[pn];
                     if(v != null && "length" in v && int(v.length) > 0)
                     {
                        var s:* = v[0];
                        if(s != null && "fileName" in s)
                        {
                           _artListProp = pn;
                           return v;
                        }
                     }
                  }
                  catch(eV:Error) { continue; }
               }
            }
         }
         catch(eTop:Error) {}
         return null;
      }

      // -----------------------------------------------------------------------
      // setHandArt: overwrite the suffix/type prop on an art entry.
      // -----------------------------------------------------------------------
      public static function setHandArt(param1:*, param2:String) : void
      {
         if(param1 == null || param2 == null) { return; }

         // 1. Try resolved prop (cached from a previous successful call)
         if(_artSuffixPropResolved.length > 0)
         {
            try { param1[_artSuffixPropResolved] = param2; return; } catch(e:Error) {}
         }

         // 2. Try hardcoded constant
         try
         {
            if(ART_SUFFIX_PROP.length > 0)
            {
               param1[ART_SUFFIX_PROP] = param2;
               _artSuffixPropResolved = ART_SUFFIX_PROP;
               return;
            }
         }
         catch(e:Error) {}

         // 3. Reflect: find String prop whose value is a known hand type (NOT fileName)
         try
         {
            var xml:XML = describeType(param1);
            for each(var node:XML in xml.variable + xml.accessor)
            {
               var pName:String = node.@name.toString();
               if(pName == "fileName") { continue; }
               var pType:String = node.@type.toString();
               if(pType == "String")
               {
                  try
                  {
                     var curVal:String = String(param1[pName]);
                     var hi:int = 0;
                     while(hi < KNOWN_HAND_TYPES.length)
                     {
                        if(curVal == KNOWN_HAND_TYPES[hi])
                        {
                           param1[pName] = param2;
                           _artSuffixPropResolved = pName;
                           return;
                        }
                        hi++;
                     }
                  }
                  catch(eP:Error) { continue; }
               }
            }
         }
         catch(eTop:Error) {}
      }

      // -----------------------------------------------------------------------
      // syncGlobalCostumes: apply hand assignments to all costume registry entries
      // -----------------------------------------------------------------------
      public static function syncGlobalCostumes() : void
      {
         var reg:* = getCostumeRegistry();
         if(reg == null || Obf.handMap == null) { return; }

         var len:int = int(reg.length);
         var i:int = 0;
         var matched:int = 0;
         while(i < len)
         {
            var ct:* = reg[i];
            if(ct != null && "mCostumeName" in ct && ct.mCostumeName != null)
            {
               var wanted:String = Obf.getHandForCostume(ct.mCostumeName);
               if(wanted != null)
               {
                  var art:* = handArtOf(ct);
                  if(art != null)
                  {
                     setHandArt(art, wanted);
                     matched++;
                  }
               }
            }
            i++;
         }
         _diagHandMatches = matched;
         _costumesSynced = true;
      }

      // -----------------------------------------------------------------------
      // syncGlobalPalettes: match color schemes STRICTLY by mColorSchemeName
      // Never matches numeric keys against array indices, preventing corruption
      // of unrelated schemes like Goldforged (Ranked2) or GuildColors!
      // -----------------------------------------------------------------------
      public static function syncGlobalPalettes() : void
      {
         if(Obf.paletteMap == null) { return; }

         var reg:* = getColorSchemeRegistry();
         if(reg == null) { return; }

         var rLen:int = int(reg.length);
         var patchedList:Array = [];

         for(var key:String in Obf.paletteMap)
         {
            var customPalette:Array = Obf.paletteMap[key] as Array;
            if(customPalette == null || customPalette.length == 0) continue;

            var targetScheme:* = null;
            var keyNorm:String = key.toLowerCase().replace(/[\s\-_]/g, "");

            // Search STRICTLY by mColorSchemeName (e.g. "CMYK", "RGB", "SoulFire")
            var r:int = 0;
            while(r < rLen)
            {
               var sItem:* = reg[r];
               if(sItem != null && "mColorSchemeName" in sItem && sItem.mColorSchemeName != null)
               {
                  var sName:String = String(sItem.mColorSchemeName);
                  var sNameNorm:String = sName.toLowerCase().replace(/[\s\-_]/g, "");
                  if(sNameNorm == keyNorm || sName == key)
                  {
                     targetScheme = sItem;
                     break;
                  }
               }
               r++;
            }

            if(targetScheme != null)
            {
               var tName:String = String(targetScheme.mColorSchemeName);
               if(patchedList.indexOf(tName) == -1)
               {
                  applyPaletteToCSSItem(targetScheme, customPalette);
                  patchedList.push(tName);
               }
            }
         }

         _diagPatchedSchemes = patchedList;
         _palettesSynced = true;
      }

      private static function applyPaletteToCSSItem(scheme:*, palette:Array) : void
      {
         if(scheme == null || palette == null || palette.length == 0) return;

         var colors:Array = null;

         // 1. Try known property names
         try { colors = scheme["_-6y"] as Array; } catch(e6y:Error) {}
         if(colors == null && CS_COLORS_PROP.length > 0)
         {
            try { colors = scheme[CS_COLORS_PROP] as Array; } catch(eProp:Error) {}
         }
         if(colors == null && _csColorsProp.length > 0)
         {
            try { colors = scheme[_csColorsProp] as Array; } catch(eCProp:Error) {}
         }
         if(colors == null)
         {
            try { colors = scheme["_-S5J"] as Array; } catch(e1:Error) {}
         }
         if(colors == null)
         {
            try { colors = scheme["_-I4B"] as Array; } catch(e2:Error) {}
         }
         if(colors == null)
         {
            try { colors = scheme["_-Z1S"] as Array; } catch(e3:Error) {}
         }

         // 2. Discover property: find the Array with length >= 20 whose elements are uint colors
         if(colors == null)
         {
            try
            {
               var xml:XML = describeType(scheme);
               for each(var node:XML in xml.variable + xml.accessor)
               {
                  var pn:String = node.@name.toString();
                  try
                  {
                     var arr:Array = scheme[pn] as Array;
                     if(arr != null && arr.length >= 20)
                     {
                        colors = arr;
                        _csColorsProp = pn;
                        break;
                     }
                  }
                  catch(eArr:Error) { continue; }
               }
            }
            catch(eTop:Error) {}
         }

         if(colors != null)
         {
            var csClass:Class = getColorSchemeClass();
            var channels:Array = null;
            try { channels = Obf.paletteChannels(); } catch(eChan:Error) {}
            if(channels == null)
            {
               channels = [
                  "HairLt","Hair","HairDk",
                  "Body1VL","Body1Lt","Body1","Body1Dk","Body1VD","Body1Acc",
                  "Body2VL","Body2Lt","Body2","Body2Dk","Body2VD","Body2Acc",
                  "SpecialVL","SpecialLt","Special","SpecialDk","SpecialVD","SpecialAcc",
                  "ClothVL","ClothLt","Cloth","ClothDk",
                  "WeaponVL","WeaponLt","Weapon","WeaponDk","WeaponAcc"
               ];
            }

            var count:int = int(Math.min(channels.length, palette.length));
            var c:int = 0;
            while(c < count)
            {
               var chName:String = String(channels[c]);
               var targetVal:uint = uint(palette[c]) & 0xFFFFFF;
               var slot:int = -1;

               if(csClass != null)
               {
                  try { slot = csClass["_-p3"](chName + "_Swap", "_Swap"); } catch(e1:Error) {}
                  if(slot < 0) { try { slot = csClass["_-p3"](chName, ""); } catch(e2:Error) {} }
                  if(slot < 0) { try { slot = csClass["_-r5g"](chName); } catch(e3:Error) {} }
               }

               if(slot < 0)
               {
                  slot = c;
               }

               if(slot >= 0 && slot < colors.length)
               {
                  if((uint(colors[slot]) & 0xFFFFFF) != targetVal)
                  {
                     colors[slot] = targetVal;
                  }
               }
               c++;
            }
         }
      }

      public static function findGameController() : *
      {
         if(BrawlForgeSuite._gc != null) { return BrawlForgeSuite._gc; }
         if(BrawlForgeSuite._stage == null) { return null; }

         var numC:int = BrawlForgeSuite._stage.numChildren;
         var i:int = 0;
         while(i < numC)
         {
            var child:DisplayObject = BrawlForgeSuite._stage.getChildAt(i);
            if(child != null)
            {
               try
               {
                  var gc:* = child[GC_PROP];
                  if(gc != null && typeof gc == "object")
                  {
                     BrawlForgeSuite._gc = gc;
                     return BrawlForgeSuite._gc;
                  }
               }
               catch(e:Error) {}
            }
            i++;
         }
         return null;
      }

      public static function getGCEntities() : *
      {
         var gc:* = findGameController();
         if(gc == null) { return null; }
         try
         {
            var ents:* = gc[GC_ENTITIES_PROP];
            if(ents != null && "length" in ents && int(ents.length) > 0)
            {
               return ents;
            }
         }
         catch(e:Error) {}
         return null;
      }

      public static function tickEntities() : void
      {
         var entities:* = getGCEntities();
         if(entities == null) { return; }

         var eLen:int = int(entities.length);
         var i:int = 0;
         while(i < eLen)
         {
            var ent:* = entities[i];
            if(ent != null)
            {
               var costume:* = null;
               try { costume = ent[GC_PROP]; } catch(e:Error) {}
               if(costume == null)
               {
                  try
                  {
                     var eXml:XML = describeType(ent);
                     for each(var eNode:XML in eXml.variable + eXml.accessor)
                     {
                        var epn:String = eNode.@name.toString();
                        try
                        {
                           var ev:* = ent[epn];
                           if(ev != null && "mCostumeName" in ev) { costume = ev; break; }
                        }
                        catch(ep:Error) { continue; }
                     }
                  }
                  catch(eEntErr:Error) {}
               }
               if(costume != null && "mCostumeName" in costume && costume.mCostumeName != null)
               {
                  var wanted:String = Obf.getHandForCostume(costume.mCostumeName);
                  if(wanted != null)
                  {
                     var art:* = handArtOf(costume);
                     if(art != null) { setHandArt(art, wanted); }
                  }
               }
            }
            i++;
         }
      }

      // -----------------------------------------------------------------------
      // Debug overlay (F12)
      // -----------------------------------------------------------------------
      public static function updateDebugText() : void
      {
         if(_debugText == null || !_debugText.visible) { return; }
         var report:String = "";
         try
         {
            report += "========== BRAWL FORGE LIVE PROBE (F12) ==========\n";
            report += "--- [SIMBOLOS HARDCODEADOS] ---\n";
            report += " COSTUME_REG_PROP : '" + COSTUME_REG_PROP + "'\n";
            report += " GFX_PROP         : '" + GFX_PROP + "'\n";
            report += " ART_SUFFIX_PROP  : '" + ART_SUFFIX_PROP + "' (resolved: '" + _artSuffixPropResolved + "')\n";
            report += " CS_CLASS_NAME    : '" + CS_CLASS_NAME + "'\n";
            report += " CS_REG_PROP      : '" + CS_REG_PROP + "'\n";
            report += " CS_COLORS_PROP   : '" + CS_COLORS_PROP + "' (resolved: '" + _csColorsProp + "')\n";
            report += " GC_PROP          : '" + GC_PROP + "'\n";
            report += " GC_ENTITIES_PROP : '" + GC_ENTITIES_PROP + "'\n";
            report += "\n--- [PALETAS MODIFICADAS ACTIVAS] ---\n";
            report += " Patched Schemes : [" + _diagPatchedSchemes.join(", ") + "]\n";
            try
            {
               if(Obf.paletteMap != null)
               {
                  for(var pk:String in Obf.paletteMap)
                  {
                     report += "   * key '" + pk + "' -> Array(" + (Obf.paletteMap[pk] != null ? Obf.paletteMap[pk].length : 0) + ")\n";
                  }
               }
            }
            catch(eP:Error) {}

            report += "\n--- [STATUS] ---\n";
            var reg:* = getCostumeRegistry();
            report += " CostumeRegistry: " + (reg != null ? "FOUND (" + int(reg.length) + " costumes)" : "NOT FOUND") + "\n";
            var csReg:* = getColorSchemeRegistry();
            report += " CSRegistry: " + (csReg != null ? "FOUND (" + int(csReg.length) + " schemes)" : "NOT FOUND") + "\n";
            var gc:* = findGameController();
            report += " GameController: " + (gc != null ? "HOOKED" : "Not found (in menu)") + "\n";
            report += " Costumes Synced: " + (_costumesSynced ? "YES" : "NO") + " (Matches: " + _diagHandMatches + ")\n";
            report += " Palettes Synced: " + (_palettesSynced ? "YES" : "NO") + "\n";
            report += "================================================\n";
         }
         catch(topErr:Error)
         {
            report += "PROBE ERROR: " + topErr.message + "\n";
         }
         _debugText.text = report;
      }

      public static function toggleDebugOverlay() : void
      {
         if(BrawlForgeSuite._stage == null) { return; }
         if(_debugText == null)
         {
            _debugText = new TextField();
            _debugText.defaultTextFormat = new TextFormat("Consolas", 11, 0x00FF00, true);
            _debugText.background = true;
            _debugText.backgroundColor = 0x99000000;
            _debugText.border = true;
            _debugText.borderColor = 0x00FF00;
            _debugText.autoSize = TextFieldAutoSize.NONE;
            _debugText.width = 980;
            _debugText.height = 600;
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
            if(_debugText.visible && _debugText.parent != null)
            {
               _debugText.parent.setChildIndex(_debugText, _debugText.parent.numChildren - 1);
            }
         }
         updateDebugText();
      }

      public function onEnterFrame(e:Event) : void
      {
         ++this._frames;

         // Re-sync every 120 frames (2s at 60fps) or if not yet synced
         if(this._frames % 120 == 0 || !_costumesSynced)
         {
            syncGlobalCostumes();
         }
         if(this._frames % 120 == 0 || !_palettesSynced)
         {
            syncGlobalPalettes();
         }

         // Tick in-match entities every frame (fast path, no reflection)
         if(this._frames % 2 == 0)
         {
            tickEntities();
         }

         // Update debug overlay every 20 frames if visible
         if(_debugText != null && _debugText.visible && this._frames % 20 == 0)
         {
            updateDebugText();
         }
      }
   }
}
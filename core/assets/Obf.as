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
         super();
      }
      
      public static function initHandMap() : void
      {
         handMap = {};
         colorMap = {};
         handMap["Airship"] = "Hoof";
         handMap["DarkheartMonsterBat"] = "Glow";
         handMap["MonsterBat"] = "Glow";
         handMap["Bat"] = "Glow";
         colorMap["Airship"] = [{
            "src":0,
            "dst":0
         },{
            "src":12582908,
            "dst":12582908
         },{
            "src":16764057,
            "dst":12582908
         },{
            "src":5549035,
            "dst":5549035
         },{
            "src":16749164,
            "dst":16749164
         },{
            "src":8744559,
            "dst":8744559
         },{
            "src":4731955,
            "dst":4731955
         }];
         colorMap["DarkheartMonsterBat"] = [{
            "src":12582908,
            "dst":12582908
         },{
            "src":5549035,
            "dst":5549035
         }];
         colorMap["MonsterBat"] = colorMap["DarkheartMonsterBat"];
         colorMap["Bat"] = colorMap["DarkheartMonsterBat"];
         handMap["DarkheartMonsterBat"] = "Glove";
         colorMap["DarkheartMonsterBat"] = [{
            "src":0,
            "dst":0
         },{
            "src":12582908,
            "dst":12582908
         },{
            "src":5549035,
            "dst":5549035
         }];
      }
      
      public static function initPalettes() : void
      {
         paletteMap = {};
         paletteMap["48"] = [16777164,15528325,10266463,13041647,8703599,4167771,2968132,2968132,15440199,13041647,8703599,4683872,2968132,2968132,15440199,16645618,13041647,2162625,47503,47503,16569938,16645618,16777164,12042600,6841679,16645618,12582908,5549035,3092584,15440199];
         paletteMap["RGB"] = paletteMap["48"];
      }
      
      public static function getCamelSuffixes(str:String) : Array
      {
         var code:Number = NaN;
         var suffix:String = null;
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
            code = str.charCodeAt(i);
            if(code >= 65 && code <= 90)
            {
               suffix = str.substring(i);
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
         var k:* = null;
         var keySuffixes:Array = null;
         var ki:int = 0;
         var klen:int = 0;
         var ks:String = null;
         var cs:String = null;
         if(costumeName == null)
         {
            return null;
         }
         if(handMap == null)
         {
            initHandMap();
         }
         if(handMap[costumeName] != null)
         {
            return handMap[costumeName] as String;
         }
         for(k in handMap)
         {
            keySuffixes = getCamelSuffixes(k);
            ki = 0;
            klen = keySuffixes.length;
            while(ki < klen)
            {
               ks = keySuffixes[ki++];
               if(ks == costumeName)
               {
                  return handMap[k] as String;
               }
            }
         }
         var costSuffixes:Array = getCamelSuffixes(costumeName);
         var ci:int = 0;
         var clen:int = costSuffixes.length;
         while(ci < clen)
         {
            cs = costSuffixes[ci++];
            if(handMap[cs] != null)
            {
               return handMap[cs] as String;
            }
         }
         return null;
      }
      
      public static function getColorSwapsForCostume(costumeName:String) : Array
      {
         var k:* = null;
         var keySuffixes:Array = null;
         var ki:int = 0;
         var klen:int = 0;
         var ks:String = null;
         var cs:String = null;
         if(costumeName == null)
         {
            return null;
         }
         if(colorMap == null)
         {
            initHandMap();
         }
         if(colorMap[costumeName] != null)
         {
            return colorMap[costumeName] as Array;
         }
         for(k in colorMap)
         {
            keySuffixes = getCamelSuffixes(k);
            ki = 0;
            klen = keySuffixes.length;
            while(ki < klen)
            {
               ks = keySuffixes[ki++];
               if(ks == costumeName)
               {
                  return colorMap[k] as Array;
               }
            }
         }
         var costSuffixes:Array = getCamelSuffixes(costumeName);
         var ci:int = 0;
         var clen:int = costSuffixes.length;
         while(ci < clen)
         {
            cs = costSuffixes[ci++];
            if(colorMap[cs] != null)
            {
               return colorMap[cs] as Array;
            }
         }
         return null;
      }
      
      public static function d(param1:Array, param2:int) : String
      {
         var _loc6_:* = 0;
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
         return Obf.d([41,30,46,54,50,58,7],15);
      }
      
      public static function handFile() : String
      {
         return Obf.d([35,15,40,21,64,38,58,55,12,0,26,37,27],3);
      }
      
      public static function swapSuffix() : String
      {
         return Obf.d([53,41,48,46],20);
      }
      
      public static function gcField() : String
      {
         return Obf.d([53,61,0,0,15],56);
      }
      
      public static function families() : Array
      {
         return [Obf.d([3,56,63,61],35),Obf.d([3,56,63,61],35)];
      }
      
      public static function paletteChannels() : Array
      {
         return ["HairLt","Hair","HairDk","Body1VL","Body1Lt","Body1","Body1Dk","Body1VD","Body1Acc","Body2VL","Body2Lt","Body2","Body2Dk","Body2VD","Body2Acc","SpecialVL","SpecialLt","Special","SpecialDk","SpecialVD","SpecialAcc","ClothVL","ClothLt","Cloth","ClothDk","WeaponVL","WeaponLt","Weapon","WeaponDk","WeaponAcc"];
      }
   }
}

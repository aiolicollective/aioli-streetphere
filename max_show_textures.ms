-- ============================================================
--  max_show_textures.ms
--  Affiche les textures diffuses dans le viewport 3ds Max
--  (les materiaux importes d'un OBJ arrivent souvent avec
--  "Show Shaded Material in Viewport" desactive -> tout est noir)
--  Utilisation : Scripting > Run Script... > ce fichier
-- ============================================================

fn showMapsOf m =
(
    try ( if m.diffuseMap != undefined then showTextureMap m m.diffuseMap true ) catch()
    if classof m == Multimaterial then
        for sm in m.materialList where sm != undefined do
            try ( if sm.diffuseMap != undefined then showTextureMap sm sm.diffuseMap true ) catch()
)

for m in sceneMaterials do showMapsOf m
for o in geometry where o.material != undefined do showMapsOf o.material
format "Textures viewport activees.\n"

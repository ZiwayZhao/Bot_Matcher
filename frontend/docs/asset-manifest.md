# FriendTree Asset Manifest

## Final Scene Assets

- `public/assets/scene/scene_entire_background.png`
  - Main background layer for the playable scene.
- `public/assets/scene/scene_front.png`
  - Foreground ground layer that sits in front of the tree base.
- `public/assets/scene/main_theme.png`
  - Moodboard reference for future art direction and UI matching.
- `public/assets/scene/tree_no_leaves.png`
  - Bare tree structure used as the base growth layer.
- `public/assets/scene/tree_full_leaves.png`
  - Leaf canopy overlay. Opacity is driven by tree health.
- `public/assets/scene/tree_full_flowers.png`
  - Flower overlay. Opacity is driven by deep resonance density.
- `public/assets/scene/tree_root.png`
  - Lower root and ground detail layer.

## Character Assets

- `public/assets/characters/lobster_a.png`
  - Cropped from `claw_a_b.png`; used for the left lobster in scene.
- `public/assets/characters/lobster_b.png`
  - Cropped from `claw_a_b.png`; used for the right lobster in scene.

## Branch Reference Assets

- `public/assets/branches/branch_sprout.png`
- `public/assets/branches/branch_grow.png`
- `public/assets/branches/branch_bloom.png`
- `public/assets/branches/branch_flower.png`
- `public/assets/branches/branch_wilt.png`

These are not composited directly onto the tree yet. They are used by the branch modal and should remain the state-specific visual reference set for future animation work.

## Decor Sheets

- `public/assets/decor/little_stuff_glowing_fruit.png`
- `public/assets/decor/little_stuff_flowers.png`
- `public/assets/decor/little_stuff_rocks.png`
- `public/assets/decor/little_stuff_glow.png`

These are kept in the production asset tree for later cutout work. The current demo uses CSS glow particles instead of cropping each sheet into runtime sprites.

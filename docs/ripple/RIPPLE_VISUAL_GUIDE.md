# Water Ripple Effect - Visual Guide

## Filter Chain Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     VIDEO COMPOSITION PIPELINE                   │
└─────────────────────────────────────────────────────────────────┘

INPUT STAGE
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Video 1  │  │ Video 2  │  │ Image 1  │  ...
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┴─────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  Scale & Pad    │
         │  (1080x1920)    │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  Concatenate    │
         │  [mainv]        │
         └────────┬────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │   RIPPLE EFFECT (Optional)  │
    └─────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌─────────┐              ┌─────────────┐
│  Top    │              │   Bottom    │
│  Part   │              │    Part     │
│ (0-50%) │              │  (50-100%)  │
└────┬────┘              └──────┬──────┘
     │                          │
     │                          ▼
     │                   ┌─────────────┐
     │                   │  geq Filter │
     │                   │  (Ripple)   │
     │                   └──────┬──────┘
     │                          │
     └──────────┬───────────────┘
                │
                ▼
         ┌─────────────┐
         │   vstack    │
         │  (Combine)  │
         └──────┬──────┘
                │
                ▼
      [mainv_ripple or mainv]
                │
                ▼
    ┌───────────────────────────┐
    │  PRODUCT VIDEO OVERLAY    │
    │  (Optional)               │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  SUBTITLE RENDERING       │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  AUDIO MIXING             │
    │  (Voice + BGM)            │
    └───────────┬───────────────┘
                │
                ▼
         ┌─────────────┐
         │   OUTPUT    │
         │   VIDEO     │
         └─────────────┘
```

## Ripple Effect Detail

```
BEFORE RIPPLE                    AFTER RIPPLE
┌─────────────────┐             ┌─────────────────┐
│                 │             │                 │
│   Top Part      │             │   Top Part      │
│   (Unchanged)   │             │   (Unchanged)   │
│                 │             │                 │
├─────────────────┤             ├─────────────────┤
│                 │             │ ~~~~~~~~~~~~~   │
│  Bottom Part    │    ───►     │  ~~~~~~~~~~~    │
│  (Original)     │             │   ~~~~~~~~~     │
│                 │             │    ~~~~~~~      │
└─────────────────┘             └─────────────────┘
```

## Wave Distortion Visualization

```
TIME = 0 seconds
┌─────────────────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← No distortion
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
├─────────────────────────────────────┤  ← Ripple starts
│ ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░   │  ← Wave peak
│   ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░       │
│ ▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓     │  ← Wave trough
│   ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░       │
│ ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░   │  ← Wave peak
└─────────────────────────────────────┘

TIME = 1 second (waves moved down)
┌─────────────────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
├─────────────────────────────────────┤
│   ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░       │  ← Waves shifted
│ ▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓     │
│   ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░       │
│ ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░   │
│ ▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓     │  ← New wave
└─────────────────────────────────────┘
```

## Parameter Effects

### Amplitude (Strength)
```
amplitude=2          amplitude=5          amplitude=10
│ ▓▓▓▓▓▓▓▓▓▓▓▓ │    │ ▓▓▓▓▓▓▓▓▓▓▓▓ │    │ ▓▓▓▓▓▓▓▓▓▓▓▓ │
│ ░▓▓▓▓▓▓▓▓▓░  │    │  ░░▓▓▓▓▓▓░░  │    │    ░░▓▓░░    │
│ ▓░▓▓▓▓▓▓░▓   │    │ ▓▓░░▓▓░░▓▓   │    │ ▓▓▓▓░░▓▓▓▓   │
│ ░▓▓▓▓▓▓▓▓▓░  │    │  ░░▓▓▓▓▓▓░░  │    │    ░░▓▓░░    │
   Subtle              Moderate            Strong
```

### Wavelength (Density)
```
wavelength=15        wavelength=30        wavelength=60
│ ░▓░▓░▓░▓░▓░ │    │ ░░▓▓▓▓░░▓▓▓▓ │    │ ░░░▓▓▓▓▓▓▓░░░ │
│ ▓░▓░▓░▓░▓░▓ │    │ ▓▓░░▓▓▓▓░░▓▓ │    │ ▓▓▓▓░░░░▓▓▓▓ │
│ ░▓░▓░▓░▓░▓░ │    │ ░░▓▓▓▓░░▓▓▓▓ │    │ ░░░▓▓▓▓▓▓▓░░░ │
│ ▓░▓░▓░▓░▓░▓ │    │ ▓▓░░▓▓▓▓░░▓▓ │    │ ▓▓▓▓░░░░▓▓▓▓ │
   Many waves          Moderate            Few waves
```

### Frequency (Speed)
```
frequency=0.2        frequency=0.5        frequency=1.5
(Slow movement)      (Moderate speed)     (Fast movement)

T=0: ░░▓▓▓▓░░        T=0: ░░▓▓▓▓░░        T=0: ░░▓▓▓▓░░
T=1: ░░▓▓▓▓░░        T=1:  ░░▓▓▓▓░░       T=1:    ░░▓▓▓▓░░
T=2:  ░░▓▓▓▓░░       T=2:   ░░▓▓▓▓░░      T=2: ░░▓▓▓▓░░
     (Small shift)        (Medium shift)       (Large shift)
```

## Area Configuration

### Bottom Half (Default)
```
┌─────────────────┐
│                 │  0%
│                 │
│   No Ripple     │
│                 │
│                 │  50% ← ripple_area_start
├─────────────────┤
│ ~~~~~~~~~~~~~   │
│  ~~~~~~~~~~~    │  Ripple Effect
│   ~~~~~~~~~     │
│    ~~~~~~~      │  100% ← ripple_area_end
└─────────────────┘
```

### Bottom Third
```
┌─────────────────┐
│                 │  0%
│                 │
│                 │
│   No Ripple     │
│                 │
│                 │
│                 │  70% ← ripple_area_start
├─────────────────┤
│ ~~~~~~~~~~~~~   │  Ripple Effect
│  ~~~~~~~~~~~    │  100% ← ripple_area_end
└─────────────────┘
```

### Full Screen
```
┌─────────────────┐  0% ← ripple_area_start
│ ~~~~~~~~~~~~~   │
│  ~~~~~~~~~~~    │
│   ~~~~~~~~~     │
│    ~~~~~~~      │  Ripple Effect
│   ~~~~~~~~~     │  (Entire Video)
│  ~~~~~~~~~~~    │
│ ~~~~~~~~~~~~~   │  100% ← ripple_area_end
└─────────────────┘
```

## UI Layout

```
┌────────────────────────────────────────────────────┐
│  Water Ripple Effect (水波纹特效)                   │
├────────────────────────────────────────────────────┤
│  ☑ Enable Water Ripple Effect                     │
├────────────────────────────────────────────────────┤
│  Effect Area Start:  [========|=====] 50%          │
│  Effect Area End:    [===============|] 100%       │
│  Ripple Strength:    [====|==========] 5           │
│  Ripple Speed:       [====|==========] 0.5         │
│  Ripple Density:     [======|========] 30          │
└────────────────────────────────────────────────────┘
```

## Mathematical Visualization

### Sine Wave Function
```
  1 ┤     ╭─╮     ╭─╮     ╭─╮
    │    ╱   ╲   ╱   ╲   ╱   ╲
  0 ┼───╯─────╰─╯─────╰─╯─────╰───
    │
 -1 ┤
    └──────────────────────────────
    0    λ/2   λ   3λ/2  2λ
         (wavelength)

Formula: sin((Y + frequency*T) * 2π / wavelength)
```

### Pixel Displacement
```
Original Position:  X = 100
Wave Offset:        offset = 5 * sin(...)
New Position:       X' = 100 + offset

Example values:
sin(...) = 1.0  →  X' = 105 (shifted right)
sin(...) = 0.0  →  X' = 100 (no shift)
sin(...) = -1.0 →  X' = 95  (shifted left)
```

## Performance Visualization

```
Processing Time Comparison

Without Ripple:
[████████████████████] 100% (baseline)

With Ripple (amplitude=5):
[████████████████████████] 120-130%

With Ripple (amplitude=15):
[██████████████████████████] 130-140%

Note: Actual times depend on:
- Video resolution
- CPU performance
- Encoding settings
```

## Integration with Other Effects

```
┌─────────────────────────────────────────────┐
│           EFFECT LAYERING                   │
└─────────────────────────────────────────────┘

Layer 1 (Bottom):
┌─────────────────┐
│  Main Video     │  ← Ripple applied here
│  with Ripple    │
└─────────────────┘

Layer 2 (Middle):
┌─────────────────┐
│  Product Video  │  ← No ripple (clear)
│  (Overlay)      │
└─────────────────┘

Layer 3 (Top):
┌─────────────────┐
│  Subtitles      │  ← No ripple (readable)
└─────────────────┘

Final Output:
┌─────────────────┐
│  ┌───────────┐  │
│  │ Product   │  │  ← Clear product
│  └───────────┘  │
│ ~~~~~~~~~~~~~   │  ← Rippled background
│  ~~~~~~~~~~~    │
│   Subtitle      │  ← Clear text
└─────────────────┘
```

## Legend

```
▓ = Video content
░ = Distorted/shifted content
~ = Wave pattern
│ = Boundary
├ = Division line
└ = Corner
```

---

This visual guide helps understand how the water ripple effect works at different levels, from the high-level filter chain to the low-level pixel manipulation.

# Water Ripple Effect - FFmpeg Filter Reference

## Quick Reference

### Complete Filter Chain

```bash
# Split main video
[mainv]split=2[top_part][bottom_part];

# Crop top part (unchanged)
[top_part]crop=1080:960:0:0[top];

# Crop and apply ripple to bottom part
[bottom_part]crop=1080:960:0:960,
geq='X+5*sin((Y+0.5*T)*2*PI/30)':'Cb':'Cr'[bottom_ripple];

# Stack vertically
[top][bottom_ripple]vstack[mainv_ripple]
```

## Parameter Explanation

### geq Formula Breakdown

```
geq='X+amplitude*sin((Y+frequency*T)*2*PI/wavelength)':'Cb':'Cr'
```

**Components**:
- `X`: Horizontal pixel coordinate (0 to width)
- `Y`: Vertical pixel coordinate (0 to height)
- `T`: Time in seconds (increases as video plays)
- `amplitude`: Distortion strength in pixels
- `frequency`: Wave movement speed in Hz
- `wavelength`: Distance between wave peaks in pixels
- `'Cb':'Cr'`: Keep chroma channels unchanged

**How it works**:
1. For each pixel at position (X, Y) at time T
2. Calculate wave offset: `amplitude * sin((Y + frequency*T) * 2*PI / wavelength)`
3. Shift pixel horizontally by this offset
4. Result: Horizontal wave that moves vertically over time

### Visual Effect

```
Original:           With Ripple:
|---------|         |~~~~~~~~~|
|         |         |    ~    |
|         |   -->   |  ~   ~  |
|         |         | ~     ~ |
|---------|         |~~~~~~~~~|
```

## Parameter Tuning Guide

### Amplitude (Distortion Strength)

```
amplitude=1   : Very subtle, barely visible
amplitude=5   : Moderate, noticeable but not distracting (DEFAULT)
amplitude=10  : Strong, clearly visible waves
amplitude=20  : Very strong, dramatic effect
```

### Frequency (Wave Speed)

```
frequency=0.1 : Very slow, gentle movement
frequency=0.5 : Moderate speed (DEFAULT)
frequency=1.0 : Fast movement
frequency=2.0 : Very fast, energetic
```

### Wavelength (Wave Density)

```
wavelength=10  : Very tight, many small waves
wavelength=30  : Moderate spacing (DEFAULT)
wavelength=50  : Wide spacing, fewer waves
wavelength=100 : Very wide, gentle curves
```

## Common Presets

### Subtle Background Effect
```python
amplitude = 3
frequency = 0.3
wavelength = 40
area = 50-100%
```

### Standard Water Effect (Default)
```python
amplitude = 5
frequency = 0.5
wavelength = 30
area = 50-100%
```

### Strong Dramatic Effect
```python
amplitude = 15
frequency = 1.5
wavelength = 20
area = 70-100%
```

### Gentle Full-Screen
```python
amplitude = 4
frequency = 0.2
wavelength = 60
area = 0-100%
```

## Mathematical Details

### Sine Wave Function

The core formula uses a sine wave:
```
sin((Y + frequency * T) * 2 * PI / wavelength)
```

**Breaking it down**:
1. `Y + frequency * T`: Vertical position plus time-based offset
   - As T increases, the wave pattern moves down
   - frequency controls how fast it moves

2. `* 2 * PI / wavelength`: Convert to radians
   - wavelength determines the period of the sine wave
   - Smaller wavelength = more waves per unit height

3. `sin(...)`: Generate wave value between -1 and 1

4. `amplitude * sin(...)`: Scale wave to desired strength
   - Result is pixel offset in range [-amplitude, +amplitude]

### Wave Movement

At time T=0:
```
offset = amplitude * sin(Y * 2*PI / wavelength)
```

At time T=1 (1 second later):
```
offset = amplitude * sin((Y + frequency) * 2*PI / wavelength)
```

The wave pattern shifts down by `frequency` pixels per second.

## Alternative Formulas

### Vertical Waves (horizontal movement)
```
geq='X':'Y+amplitude*sin((X+frequency*T)*2*PI/wavelength)'
```

### Diagonal Waves
```
geq='X+amplitude*sin(((X+Y)+frequency*T)*2*PI/wavelength)':'Cb':'Cr'
```

### Multiple Wave Frequencies
```
geq='X+amplitude*sin((Y+frequency*T)*2*PI/wavelength)+amplitude*0.5*sin((Y+frequency*2*T)*2*PI/(wavelength*0.5))':'Cb':'Cr'
```

## Performance Notes

### Computational Cost

The geq filter evaluates the expression for EVERY pixel in EVERY frame:
- 1080x1920 @ 25fps = 51,840,000 evaluations per second
- Each evaluation includes: addition, multiplication, sine function

### Optimization Tips

1. **Reduce effect area**: Only apply to necessary region
2. **Use integer operations**: Avoid floating-point when possible
3. **Consider alternatives**: lenscorrection filter may be faster
4. **Hardware acceleration**: Use GPU encoding if available

## Troubleshooting

### Effect not visible
- Increase amplitude (try 10-15)
- Check that area range is correct
- Verify frequency is not 0

### Effect too strong
- Decrease amplitude (try 2-3)
- Increase wavelength (try 50-80)
- Reduce frequency (try 0.2-0.3)

### Waves moving wrong direction
- Positive frequency: waves move down
- Negative frequency: waves move up
- Zero frequency: static waves

### Performance issues
- Reduce video resolution
- Decrease effect area
- Consider using simpler filter

## Testing Commands

### Test with FFmpeg directly

```bash
# Test on a single video file
ffmpeg -i input.mp4 -filter_complex "
[0:v]split=2[top][bottom];
[top]crop=1080:960:0:0[t];
[bottom]crop=1080:960:0:960,geq='X+5*sin((Y+0.5*T)*2*PI/30)':'Cb':'Cr'[b];
[t][b]vstack
" -c:v libx264 -preset fast output.mp4
```

### Test different parameters

```bash
# Strong effect
ffmpeg -i input.mp4 -vf "geq='X+15*sin((Y+1.0*T)*2*PI/20)':'Cb':'Cr'" output_strong.mp4

# Subtle effect
ffmpeg -i input.mp4 -vf "geq='X+3*sin((Y+0.2*T)*2*PI/50)':'Cb':'Cr'" output_subtle.mp4

# Full screen
ffmpeg -i input.mp4 -vf "geq='X+5*sin((Y+0.5*T)*2*PI/30)':'Cb':'Cr'" output_fullscreen.mp4
```

## References

- FFmpeg geq documentation: https://ffmpeg.org/ffmpeg-filters.html#geq
- Sine wave mathematics: https://en.wikipedia.org/wiki/Sine_wave
- Video filter guide: https://trac.ffmpeg.org/wiki/FilteringGuide

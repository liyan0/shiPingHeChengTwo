# Water Ripple Effect - Usage Guide & Tips

## Quick Start

### Basic Usage (5 Steps)

1. **Launch Application**
   ```bash
   python main.py
   ```

2. **Navigate to Video Compose Tab**
   - Click on "带货视频合成" (Video Compose) tab

3. **Enable Ripple Effect**
   - Scroll to "水波纹特效" (Water Ripple Effect) section
   - Check "启用水波纹特效" (Enable Water Ripple Effect)

4. **Use Default Settings** (Recommended for first try)
   - Area Start: 50%
   - Area End: 100%
   - Strength: 5
   - Speed: 0.5
   - Density: 30

5. **Start Composition**
   - Configure other settings as usual
   - Click "开始合成" (Start Composition)

## Common Use Cases

### 1. Subtle Background Enhancement

**Goal**: Add gentle movement without being distracting

**Settings**:
```
Area Start: 50%
Area End: 100%
Strength: 3
Speed: 0.3
Density: 40
```

**Best for**:
- Product showcase videos
- Professional presentations
- Educational content

### 2. Eye-Catching Social Media Effect

**Goal**: Create attention-grabbing visual effect

**Settings**:
```
Area Start: 50%
Area End: 100%
Strength: 8
Speed: 0.8
Density: 25
```

**Best for**:
- Short-form video platforms (Douyin, Kuaishou)
- Promotional content
- Entertainment videos

### 3. Dramatic Full-Screen Effect

**Goal**: Maximum visual impact

**Settings**:
```
Area Start: 0%
Area End: 100%
Strength: 12
Speed: 1.2
Density: 20
```

**Best for**:
- Music videos
- Artistic content
- Special effects demonstrations

### 4. Bottom Strip Effect

**Goal**: Subtle effect only at the very bottom

**Settings**:
```
Area Start: 85%
Area End: 100%
Strength: 10
Speed: 0.5
Density: 30
```

**Best for**:
- Videos with important content in upper area
- Text-heavy videos
- Tutorial videos

### 5. Gentle Ocean Wave

**Goal**: Slow, smooth wave like ocean surface

**Settings**:
```
Area Start: 40%
Area End: 100%
Strength: 4
Speed: 0.2
Density: 60
```

**Best for**:
- Relaxation videos
- Nature content
- Meditation/wellness videos

## Parameter Tuning Guide

### Strength (Amplitude)

**Too Weak** (1-2):
- Barely visible
- May not be noticeable on mobile screens
- Use only for very subtle effects

**Just Right** (3-7):
- Clearly visible but not distracting
- Professional appearance
- Recommended for most use cases

**Too Strong** (15-20):
- Can be distracting
- May make text hard to read
- Use only for artistic/dramatic effects

**Recommendation**: Start with 5, adjust by ±2

### Speed (Frequency)

**Too Slow** (0.1-0.2):
- Waves barely move
- Can appear static
- Good for calm, peaceful content

**Just Right** (0.4-0.8):
- Natural wave movement
- Engaging without being frantic
- Recommended for most use cases

**Too Fast** (1.5-2.0):
- Rapid movement
- Can be dizzying
- Use only for energetic content

**Recommendation**: Start with 0.5, adjust by ±0.2

### Density (Wavelength)

**Too Dense** (10-15):
- Many small waves
- Can look noisy
- May not render well at lower resolutions

**Just Right** (25-40):
- Clear wave pattern
- Smooth appearance
- Recommended for most use cases

**Too Sparse** (80-100):
- Very few waves
- May look like simple distortion
- Less "water-like" appearance

**Recommendation**: Start with 30, adjust by ±10

### Area Range

**Top Heavy** (0-50%):
- Unusual, not recommended
- Can distract from main content
- Use only for specific artistic purposes

**Balanced** (30-70% or 40-80%):
- Interesting composition
- Good for videos with centered subjects
- Allows flexibility in framing

**Bottom Heavy** (50-100% or 60-100%):
- Most common and natural
- Mimics water reflection
- Recommended for most use cases

**Full Screen** (0-100%):
- Maximum impact
- Can be overwhelming
- Use sparingly

**Recommendation**: Start with 50-100%

## Optimization Tips

### For Better Performance

1. **Reduce Effect Area**
   - Smaller area = faster processing
   - Use 70-100% instead of 0-100% if possible

2. **Lower Resolution First**
   - Test with 720p before 1080p
   - Verify effect looks good before full quality

3. **Disable When Not Needed**
   - Uncheck the enable box for videos that don't need it
   - No performance impact when disabled

4. **Batch Processing**
   - Process multiple videos overnight
   - Use max concurrent = 1 for ripple-heavy batches

### For Better Visual Quality

1. **Match Video Content**
   - Stronger effects for energetic content
   - Subtle effects for professional content

2. **Consider Product Placement**
   - Ensure product videos are in clear areas
   - Test with actual product videos

3. **Test on Target Platform**
   - View on mobile devices
   - Check how it looks on different screen sizes

4. **Adjust for Video Length**
   - Longer videos: slower, subtler effects
   - Shorter videos: can handle stronger effects

## Troubleshooting

### Problem: Effect Not Visible

**Possible Causes**:
- Checkbox not enabled
- Strength too low
- Area range invalid (start >= end)

**Solutions**:
1. Verify checkbox is checked
2. Increase strength to 8-10
3. Check area start < area end
4. Try full screen (0-100%) to test

### Problem: Effect Too Strong

**Possible Causes**:
- Strength too high
- Density too low
- Speed too fast

**Solutions**:
1. Reduce strength to 3-4
2. Increase density to 50-60
3. Reduce speed to 0.2-0.3
4. Increase area start (e.g., 70% instead of 50%)

### Problem: Looks Unnatural

**Possible Causes**:
- Parameters not balanced
- Wrong density for video resolution
- Speed doesn't match content

**Solutions**:
1. Use preset combinations (see Common Use Cases)
2. Adjust density: 30 for 1080p, 20 for 720p
3. Match speed to video energy level
4. Test with reference video

### Problem: Product Videos Affected

**This should not happen** - product videos are overlaid after ripple

**If it does occur**:
1. Check code in video_compose_task_manager.py
2. Verify filter chain order
3. Report as bug

### Problem: Slow Processing

**Expected Behavior**:
- Ripple adds 20-30% to encoding time
- This is normal for pixel-level effects

**To Speed Up**:
1. Reduce effect area
2. Lower video resolution
3. Use fewer concurrent tasks
4. Consider disabling for some videos

### Problem: Subtitles Hard to Read

**Possible Causes**:
- Ripple area includes subtitle region
- Effect too strong

**Solutions**:
1. Reduce area end to 90% (keep bottom 10% clear)
2. Reduce strength
3. Adjust subtitle position in settings
4. Use subtitle background/shadow

## Best Practices

### Do's

✓ Start with default settings
✓ Test on a single video first
✓ Adjust one parameter at a time
✓ View output on target device
✓ Match effect to content style
✓ Keep product videos clear
✓ Ensure subtitles are readable
✓ Save successful parameter combinations

### Don'ts

✗ Don't use maximum values for all parameters
✗ Don't apply to every video (use selectively)
✗ Don't ignore performance impact
✗ Don't forget to test on mobile
✗ Don't use with already-busy backgrounds
✗ Don't apply to text-heavy videos
✗ Don't use conflicting effects together

## Parameter Presets

### Preset 1: "Gentle Wave" (Default)
```
Area: 50-100%
Strength: 5
Speed: 0.5
Density: 30
Use: General purpose, safe choice
```

### Preset 2: "Subtle Professional"
```
Area: 60-100%
Strength: 3
Speed: 0.3
Density: 40
Use: Business, educational content
```

### Preset 3: "Social Media Pop"
```
Area: 50-100%
Strength: 8
Speed: 0.8
Density: 25
Use: Douyin, Kuaishou, viral content
```

### Preset 4: "Dramatic Full"
```
Area: 0-100%
Strength: 12
Speed: 1.2
Density: 20
Use: Music videos, artistic content
```

### Preset 5: "Bottom Strip"
```
Area: 85-100%
Strength: 10
Speed: 0.5
Density: 30
Use: Tutorial, text-heavy videos
```

### Preset 6: "Ocean Calm"
```
Area: 40-100%
Strength: 4
Speed: 0.2
Density: 60
Use: Relaxation, nature content
```

## Advanced Techniques

### 1. Progressive Effect

**Concept**: Gradually increase effect strength

**Method**:
- Create multiple versions with different strengths
- Use video editing software to blend
- Or: Process same video with different area ranges

### 2. Complementary Effects

**Good Combinations**:
- Ripple + Blur background (product overlay)
- Ripple + Subtle mask (product overlay)
- Ripple + Ken Burns (on images)

**Avoid**:
- Ripple + Strong mask (too busy)
- Ripple + Reverse video (confusing)

### 3. Content-Aware Settings

**For Product Showcase**:
- Area: 50-100%
- Strength: 4-6
- Speed: 0.4-0.6
- Keep product area clear

**For Entertainment**:
- Area: 40-100%
- Strength: 7-10
- Speed: 0.7-1.0
- More dramatic OK

**For Education**:
- Area: 70-100%
- Strength: 3-5
- Speed: 0.3-0.5
- Keep text areas clear

### 4. Resolution Scaling

**For 720p (1280x720)**:
- Reduce density by ~30%: use 20 instead of 30
- Keep other parameters similar

**For 1080p (1920x1080)**:
- Use default density: 30
- Standard parameters work well

**For 4K (3840x2160)**:
- Increase density by ~50%: use 45 instead of 30
- May need to adjust strength

## Workflow Integration

### Typical Workflow

1. **Prepare Materials**
   - Videos, images, audio files
   - Product videos (if using overlay)

2. **Configure Basic Settings**
   - Resolution, duration, counts
   - Subtitle style
   - BGM volume

3. **Enable Ripple Effect**
   - Choose preset or custom settings
   - Test with one video first

4. **Review Output**
   - Check effect visibility
   - Verify product clarity
   - Confirm subtitle readability

5. **Adjust if Needed**
   - Fine-tune parameters
   - Re-process if necessary

6. **Batch Process**
   - Apply to remaining videos
   - Monitor progress

### Quality Checklist

Before finalizing:
- [ ] Ripple effect is visible but not distracting
- [ ] Product videos are clear and unaffected
- [ ] Subtitles are readable
- [ ] Effect matches content style
- [ ] Video plays smoothly
- [ ] Audio is properly mixed
- [ ] Output file size is reasonable
- [ ] Tested on target device/platform

## Platform-Specific Tips

### Douyin (抖音)
- Use stronger effects (7-10 strength)
- Faster speed (0.7-1.0)
- Full vertical format works well
- Test on mobile device

### Kuaishou (快手)
- Similar to Douyin
- Slightly more conservative (6-8 strength)
- Ensure good mobile visibility

### WeChat Moments (微信朋友圈)
- More subtle effects (4-6 strength)
- Slower speed (0.4-0.6)
- Keep professional appearance

### Xiaohongshu (小红书)
- Aesthetic focus
- Moderate effects (5-7 strength)
- Match platform's visual style

## FAQ

**Q: Will this work with all video formats?**
A: Yes, FFmpeg handles all common formats.

**Q: Can I use this with product overlay?**
A: Yes, product videos are overlaid after ripple and remain clear.

**Q: Does it affect audio?**
A: No, ripple is video-only. Audio is unaffected.

**Q: Can I preview before processing?**
A: Not currently. Process one test video first.

**Q: How much does it slow down processing?**
A: Approximately 20-30% increase in encoding time.

**Q: Can I apply to only specific videos in a batch?**
A: Not currently. Enable/disable applies to entire batch.

**Q: Will it work on low-end computers?**
A: Yes, but processing will be slower. Reduce concurrent tasks.

**Q: Can I use negative values?**
A: No, UI limits to positive ranges. Negative would reverse wave direction.

**Q: Does it work with all resolutions?**
A: Yes, but adjust density parameter for different resolutions.

**Q: Can I save my favorite settings?**
A: Not currently. Note down successful combinations manually.

## Resources

- **Implementation Docs**: WATER_RIPPLE_IMPLEMENTATION.md
- **Technical Reference**: RIPPLE_FILTER_REFERENCE.md
- **Visual Guide**: RIPPLE_VISUAL_GUIDE.md
- **Summary**: IMPLEMENTATION_SUMMARY.md
- **Verification**: verify_ripple_implementation.py

## Support

If you encounter issues:
1. Check troubleshooting section above
2. Verify implementation with verify_ripple_implementation.py
3. Review FFmpeg output logs for errors
4. Test with minimal settings first
5. Report bugs with specific parameters used

---

**Happy video creating with water ripple effects!**

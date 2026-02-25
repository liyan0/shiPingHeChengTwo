"""Shared video filter construction utilities."""

import math

from ..models.config import WaterReflectionConfig, BlurredBorderConfig, PipConfig

# Physically-based directional wave definitions.
# (name, theta_deg, amplitude_px, k_rad_per_px, omega_rad_per_s, phi_rad)
_WAVE_DEFS = [
    ("primary_broad",  25.0, 4.5, 0.020, 1.5, 0.0),
    ("crossing_wave", 110.0, 3.0, 0.035, 2.5, 1.8),
    ("medium_detail",  70.0, 2.0, 0.055, 3.5, 3.5),
]


def _build_displacement_maps(
    output_label: str,
    config: WaterReflectionConfig,
    reflect_w: int,
    reflect_h: int,
    fps: int,
    duration: float,
) -> list:
    """Build X/Y displacement map filter fragments for wave distortion."""
    freq_mult = 0.5 + config.frequency
    spd_mult = 0.5 + config.speed

    x_terms = []
    y_terms = []
    for _name, theta_deg, amp_base, k, omega, phi in _WAVE_DEFS:
        theta = math.radians(theta_deg)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        a = amp_base * config.amplitude
        k_adj = k * freq_mult
        omega_adj = omega * spd_mult

        propagation = (
            f"sin({k_adj:.6f}*(X*{cos_t:.6f}+Y*{sin_t:.6f})"
            f"+T*{omega_adj:.4f}+{phi:.4f})"
        )

        ax = a * cos_t
        ay = a * sin_t
        if abs(ax) > 0.001:
            x_terms.append(f"{ax:.4f}*{propagation}")
        if abs(ay) > 0.001:
            y_terms.append(f"{ay:.4f}*{propagation}")

    x_sum = "+".join(x_terms) if x_terms else "0"
    y_sum = "+".join(y_terms) if y_terms else "0"
    x_expr = f"128+({x_sum})"
    y_expr = f"128+({y_sum})"

    size_str = f"{reflect_w}x{reflect_h}"
    xmap = f"{output_label}_xmap"
    ymap = f"{output_label}_ymap"
    parts = []

    parts.append(
        f"nullsrc=size={size_str}:rate={fps}:duration={duration:.3f},"
        f"format=gray,"
        f"geq=lum='{x_expr}',"
        f"format=yuv420p"
        f"[{xmap}]"
    )
    parts.append(
        f"nullsrc=size={size_str}:rate={fps}:duration={duration:.3f},"
        f"format=gray,"
        f"geq=lum='{y_expr}',"
        f"format=yuv420p"
        f"[{ymap}]"
    )

    return parts, xmap, ymap


def build_water_reflection_filter(
    config: WaterReflectionConfig,
    input_label: str,
    output_label: str,
    width: int,
    height: int,
    fps: int,
    duration: float,
) -> list:
    """Build FFmpeg filter_complex fragments for water reflection effect.

    Creates a vertically-flipped reflection at the bottom of the frame with
    wave distortion, fade-out alpha gradient, and blue tint.

    Returns a list of filter-graph fragment strings to be joined with ';'.
    """
    reflect_h = int(height * config.reflection_ratio)
    crop_y = height - reflect_h
    o = output_label  # shorthand for label prefix

    parts = []

    # Step 1: Split input into original + source for reflection
    parts.append(
        f"[{input_label}]split=2[{o}_orig][{o}_src]"
    )

    # Step 2: Crop bottom region as reflection source
    parts.append(
        f"[{o}_src]crop=w={width}:h={reflect_h}:x=0:y={crop_y}[{o}_cropped]"
    )

    # Step 3: Vertical flip
    parts.append(
        f"[{o}_cropped]vflip[{o}_flipped]"
    )

    # Step 4: Wave distortion via displacement maps
    disp_parts, xmap, ymap = _build_displacement_maps(
        o, config, width, reflect_h, fps, duration,
    )
    parts.extend(disp_parts)
    parts.append(
        f"[{o}_flipped][{xmap}][{ymap}]displace=edge=smear[{o}_waved]"
    )

    # Step 5: Convert to RGBA, apply alpha gradient (fade top->bottom) + blue tint
    opacity_val = config.opacity
    tint = config.tint_strength
    r_mult = 1.0 - tint
    g_mult = 1.0 - tint
    # Alpha: top of reflection = opacity*255, bottom = 0 (linear gradient)
    alpha_expr = f"{opacity_val:.2f}*255*(1-Y/{reflect_h})"
    r_expr = f"clip(r(X,Y)*{r_mult:.2f}, 0, 255)"
    g_expr = f"clip(g(X,Y)*{g_mult:.2f}, 0, 255)"
    b_expr = f"clip(b(X,Y)*{min(1.0 + tint * 0.3, 1.3):.2f}, 0, 255)"

    parts.append(
        f"[{o}_waved]format=rgba,"
        f"geq="
        f"r='{r_expr}':"
        f"g='{g_expr}':"
        f"b='{b_expr}':"
        f"a='{alpha_expr}'"
        f"[{o}_tinted]"
    )

    # Step 6: Pad to full frame size (reflection at bottom)
    parts.append(
        f"[{o}_tinted]pad=w={width}:h={height}:x=0:y={crop_y}:color=0x00000000"
        f"[{o}_padded]"
    )

    # Step 7: Overlay reflection onto original
    parts.append(
        f"[{o}_orig][{o}_padded]overlay=0:0:format=auto[{output_label}]"
    )

    return parts


def build_blurred_border_filter(
    config: BlurredBorderConfig,
    main_label: str,
    border_label: str,
    output_label: str,
    width: int,
    height: int,
) -> list:
    """Build FFmpeg filter_complex fragments for blurred video border effect.

    The border video is scaled to full output resolution, Gaussian-blurred,
    then converted to an RGBA frame with a transparent center and opaque edges.
    This frame is overlaid ON TOP of the main video, which keeps its full
    resolution untouched.  A feathered inner edge provides a smooth transition.

    Returns a list of filter-graph fragment strings to be joined with ';'.
    """
    bw = int(min(width, height) * config.border_width / 100.0)
    sigma = config.blur_strength
    o = output_label

    # Feather zone: smooth transition at the inner edge of the border.
    feather = max(2, int(bw * 0.3))

    parts = []

    # Step 1: Scale border video to full output resolution and blur
    parts.append(
        f"[{border_label}]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
        f"gblur=sigma={sigma:.1f}[{o}_bg]"
    )

    # Step 2: Convert to RGBA and apply alpha mask
    #   d = distance from nearest edge = min(min(X, W-1-X), min(Y, H-1-Y))
    #   d < bw           -> alpha=255  (border region, fully opaque)
    #   bw <= d < bw+f   -> linear fade 255->0  (feather zone)
    #   d >= bw+f        -> alpha=0    (center, fully transparent)
    bw_f = bw + feather
    alpha_expr = (
        f"if(lt(min(min(X,{width - 1}-X),min(Y,{height - 1}-Y)),{bw}),"
        f"255,"
        f"if(lt(min(min(X,{width - 1}-X),min(Y,{height - 1}-Y)),{bw_f}),"
        f"255*(1-(min(min(X,{width - 1}-X),min(Y,{height - 1}-Y))-{bw})/{feather}),"
        f"0))"
    )

    parts.append(
        f"[{o}_bg]format=rgba,"
        f"geq="
        f"r='r(X,Y)':"
        f"g='g(X,Y)':"
        f"b='b(X,Y)':"
        f"a='{alpha_expr}'"
        f"[{o}_frame]"
    )

    # Step 3: Overlay the border frame on top of the main video
    # Main video passes through at full resolution, untouched.
    parts.append(
        f"[{main_label}][{o}_frame]overlay=0:0:format=auto[{output_label}]"
    )

    return parts


def build_overlay_material_filters(
    input_label: str,
    output_label: str,
    overlay_input_indices: list,
    width: int,
    height: int,
    duration: float,
) -> list:
    """Build FFmpeg filter fragments for overlay material compositing.

    Each overlay is scaled to cover the full frame (scale up + crop),
    trimmed to duration, then blended using screen mode with per-overlay opacity.
    Black backgrounds are naturally removed by the screen blend mode.

    Args:
        input_label: Current video label (without brackets).
        output_label: Final output label.
        overlay_input_indices: List of (input_idx, opacity_float) tuples.
        width: Output width.
        height: Output height.
        duration: Target duration in seconds.

    Returns:
        List of filter-graph fragment strings to be joined with ';'.
    """
    parts = []
    current = input_label

    # Convert main video to planar RGB for correct screen blend math
    rgb_in = f"{output_label}_rgb_in"
    parts.append(f"[{current}]format=gbrp[{rgb_in}]")
    current = rgb_in

    for i, (input_idx, opacity) in enumerate(overlay_input_indices):
        ol = f"ol{i}"
        # Scale to cover, crop, trim, and convert to planar RGB
        parts.append(
            f"[{input_idx}:v]scale={width}:{height}"
            f":force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
            f"format=gbrp"
            f"[{ol}_scaled]"
        )
        # Screen blend with opacity (in RGB space)
        is_last = (i == len(overlay_input_indices) - 1)
        next_label = output_label if is_last else f"{output_label}_s{i}"
        # Convert back to yuv420p on the last blend
        fmt_suffix = ",format=yuv420p" if is_last else ""
        parts.append(
            f"[{current}][{ol}_scaled]blend="
            f"all_mode=screen:all_opacity={opacity:.2f}"
            f"{fmt_suffix}"
            f"[{next_label}]"
        )
        current = next_label

    return parts


def build_pip_filter(
    config: PipConfig,
    main_label: str,
    pip_label: str,
    output_label: str,
    width: int,
    height: int,
) -> list:
    """Build FFmpeg filter_complex fragments for circular PiP overlay.

    Creates a circular-masked video overlay with optional border ring,
    positioned at configurable coordinates on the main video.

    Returns a list of filter-graph fragment strings to be joined with ';'.
    """
    short_edge = min(width, height)
    diameter = int(short_edge * config.size_percent / 100.0)
    # Ensure diameter is even for cleaner scaling
    diameter = diameter if diameter % 2 == 0 else diameter + 1
    radius = diameter // 2

    # Position: center of circle at (h%, v%) of the frame
    cx = int(width * config.h_percent / 100.0)
    cy = int(height * config.v_percent / 100.0)
    # Top-left corner for overlay
    ox = cx - radius
    oy = cy - radius

    o = output_label
    parts = []

    # Step 1: Scale PiP video so shortest side = diameter, then crop to square
    parts.append(
        f"[{pip_label}]scale={diameter}:{diameter}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={diameter}:{diameter},"
        f"setsar=1[{o}_sq]"
    )

    # Step 2: Convert to RGBA and apply circular alpha mask
    r = radius
    alpha_expr = (
        f"if(lte((X-{r})*(X-{r})+(Y-{r})*(Y-{r}),{r}*{r}),255,0)"
    )
    parts.append(
        f"[{o}_sq]format=rgba,"
        f"geq="
        f"r='r(X,Y)':"
        f"g='g(X,Y)':"
        f"b='b(X,Y)':"
        f"a='{alpha_expr}'"
        f"[{o}_circle]"
    )

    # Step 3: Draw border ring if border_width > 0
    if config.border_width > 0:
        bw = config.border_width
        color = config.border_color.lstrip('#')
        if len(color) != 6:
            color = "FFFFFF"
        br = int(color[0:2], 16)
        bg = int(color[2:4], 16)
        bb = int(color[4:6], 16)

        inner_r = r - bw
        # Ring: pixels where distance > inner_r get border color
        ring_r = (
            f"if(gt((X-{r})*(X-{r})+(Y-{r})*(Y-{r}),{inner_r}*{inner_r}),"
            f"{br},r(X,Y))"
        )
        ring_g = (
            f"if(gt((X-{r})*(X-{r})+(Y-{r})*(Y-{r}),{inner_r}*{inner_r}),"
            f"{bg},g(X,Y))"
        )
        ring_b = (
            f"if(gt((X-{r})*(X-{r})+(Y-{r})*(Y-{r}),{inner_r}*{inner_r}),"
            f"{bb},b(X,Y))"
        )
        ring_alpha = (
            f"if(lte((X-{r})*(X-{r})+(Y-{r})*(Y-{r}),{r}*{r}),255,0)"
        )
        parts.append(
            f"[{o}_circle]geq="
            f"r='{ring_r}':"
            f"g='{ring_g}':"
            f"b='{ring_b}':"
            f"a='{ring_alpha}'"
            f"[{o}_bordered]"
        )
        pip_final = f"{o}_bordered"
    else:
        pip_final = f"{o}_circle"

    # Step 4: Overlay on main video at calculated position
    parts.append(
        f"[{main_label}][{pip_final}]overlay={ox}:{oy}:format=auto[{output_label}]"
    )

    return parts

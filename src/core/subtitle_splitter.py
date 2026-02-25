"""Split long SRT subtitle segments so each stays within a character limit.

Strategy:
1. Merge short fragments (<=3 chars) produced by ASR into adjacent segments.
2. Repair cross-segment broken words detected via jieba word boundaries.
3. Merge semantically incomplete fragments (dangling prepositions etc.).
3b. Opportunistic merge: re-join adjacent segments whose boundary has a
    high split penalty so that DP can re-find a better break point.
4. Use dynamic programming to find optimal split points that minimise
   breaking words/phrases mid-way.  Split-point penalty (low = better):
     -  0: after punctuation (best)
     -  1: after particle (了/着/过) at a word boundary
     -  2: at a jieba word boundary
     - 10: inside a word
     - 15: HARD-PROHIBIT — after 的/地/得, negation, preposition,
           or before a measure word
   Additionally, very short chunks (<=2 chars) receive an extra penalty
   to discourage 1-2 character fragments.
5. Distribute the original time span proportionally by *speaking* character
   count (punctuation excluded).
"""

from typing import List, Optional, Set, Tuple

try:
    import jieba
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

from .subtitle_corrector import SrtSegment, parse_srt, build_srt

_PUNCTUATION = set("，。！？；：、,.!?;:…—–")
_PARTICLES = set("的了着过地得")
_PARTICLES_SAFE = set("了着过")  # particles OK to break after (not 的/地/得)

# --- Penalty-related character sets ---
_NEGATION = set("不没别无莫勿未非")
_MEASURE_WORDS = set("个只条件位块片座栋棵颗双对副套组批群堆串")
_PREPOSITIONS = set("在对让把将被从与跟向往朝按照")

# Characters at the END of a segment that signal it should merge forward.
# Only triggered when the segment is short (see trailing_len_threshold).
_TRAILING_MERGE_CHARS = (
    _PREPOSITIONS                          # 介词
    | set("和或但却而且并")                # 连词
    | set("的了着过地得")                  # 助词
    | set("很太更最都也还就")              # 副词
    | set("是有")                          # 轻动词
    | _NEGATION                            # 否定词
    | set("一二三四五六七八九十百千万亿")    # 数词
    | set("这那哪每各某")                  # 指示/疑问代词
    | set("能会要想可敢肯愿")              # 能愿动词
)

# Characters at the START of a segment that signal it should merge backward.
_LEADING_MERGE_CHARS = (
    set("的了着过")                        # 结构助词
    | set("中里上下内外前后左右间")          # 方位词
    | _MEASURE_WORDS                       # 量词
    | set("来去起住开掉完好到出")            # 趋向补语
    | set("吗呢吧啊呀哦哇嘛")              # 语气词
)


def _time_to_ms(time_str: str) -> int:
    """Convert SRT timestamp 'HH:MM:SS,mmm' to milliseconds."""
    h, m, rest = time_str.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def _ms_to_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp 'HH:MM:SS,mmm'."""
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# --- DP optimal text splitting -------------------------------------------

def _word_boundary_set(text: str) -> Set[int]:
    """Return the set of character positions that are jieba word boundaries.

    A position *i* is a word boundary if it is the start of a word (i.e. the
    cumulative length of preceding words equals *i*).  Position 0 and len(text)
    are always boundaries.
    """
    if _HAS_JIEBA:
        words = jieba.lcut(text)
    else:
        words = list(text)

    boundaries: Set[int] = {0}
    pos = 0
    for w in words:
        pos += len(w)
        boundaries.add(pos)
    return boundaries


def _split_penalty(text: str, j: int, boundaries: Set[int]) -> int:
    """Cost of splitting *text* between text[j-1] and text[j].

    Lower is better:
       0 – after punctuation (best break point)
       1 – after safe particle (了/着/过) at a word boundary
       2 – at a jieba word boundary
      10 – inside a word
      15 – HARD-PROHIBIT: after 的/地/得, negation, preposition,
           or before a measure word — these must not be separated
           from the word they modify/govern.
    """
    if j <= 0 or j >= len(text):
        return 0
    prev_char = text[j - 1]
    next_char = text[j]

    # Level 0: after punctuation — always a good break
    if prev_char in _PUNCTUATION:
        return 0

    # Level 15 (hard-prohibit): patterns that must NEVER be split
    # "的/地/得" + noun/verb — keep modifier with modified word
    if prev_char in ("的", "地", "得"):
        return 15
    # negation + verb/adj — "不知道", "没关系"
    if prev_char in _NEGATION:
        return 15
    # preposition + object — "在等待", "把事情"
    if prev_char in _PREPOSITIONS:
        return 15
    # numeral + measure word — "三个", "一条"
    if next_char in _MEASURE_WORDS:
        return 15

    # Level 1: safe particle at word boundary
    if prev_char in _PARTICLES_SAFE and j in boundaries:
        return 1

    # Level 2: jieba word boundary
    if j in boundaries:
        return 2

    # Level 10: inside a word
    return 10


def _split_text(text: str, max_chars: int) -> List[str]:
    """Split *text* into chunks each <= *max_chars* using DP optimal splitting.

    Uses dynamic programming to minimise total split-point penalty so that
    words and phrases are kept intact whenever possible.
    """
    n = len(text)
    if n <= max_chars:
        return [text]

    boundaries = _word_boundary_set(text)
    half = max_chars / 2

    # dp[i] = minimum total penalty to split text[0:i] into valid chunks
    INF = float("inf")
    dp = [INF] * (n + 1)
    parent = [-1] * (n + 1)
    dp[0] = 0

    for i in range(1, n + 1):
        lo = max(0, i - max_chars)
        for j in range(lo, i):
            if dp[j] == INF:
                continue
            chunk_len = i - j
            short_pen = max(0, int(half - chunk_len)) if chunk_len < half else 0
            if chunk_len <= 2:
                short_pen += 20  # prevent 1-2 char fragments
            cost = dp[j] + _split_penalty(text, j, boundaries) + short_pen
            if cost < dp[i]:
                dp[i] = cost
                parent[i] = j

    # Backtrack to recover split points
    splits: List[int] = []
    pos = n
    while pos > 0:
        prev = parent[pos]
        splits.append(prev)
        pos = prev
    splits.reverse()
    splits.append(n)

    chunks = [text[splits[i]:splits[i + 1]] for i in range(len(splits) - 1)]
    return [c for c in chunks if c]


# --- Fragment merging ----------------------------------------------------

def _merge_short_segments(
    segments: List[SrtSegment],
    min_chars: int = 3,
) -> List[SrtSegment]:
    """Merge ASR fragments with <= *min_chars* characters into neighbours.

    Strategy: forward-merge first (prepend short fragment to the next segment),
    then backward-merge any remaining trailing short fragment.  This correctly
    handles ASR splits like "踏" + "实做事" → "踏实做事".
    """
    if not segments:
        return segments

    # Forward pass: merge short segments into the NEXT segment
    forward: List[SrtSegment] = []
    pending_text = ""
    pending_start: Optional[str] = None

    for seg in segments:
        if pending_text:
            # Prepend pending fragment to this segment
            forward.append(SrtSegment(
                index=0,
                start_time=pending_start,
                end_time=seg.end_time,
                text=pending_text + seg.text,
            ))
            pending_text = ""
            pending_start = None
        elif len(seg.text) <= min_chars:
            # Buffer this short segment for forward merge
            pending_text = seg.text
            pending_start = seg.start_time
        else:
            forward.append(SrtSegment(
                index=0,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
            ))

    # If the last segment was short and still pending, merge backward
    if pending_text and forward:
        prev = forward[-1]
        forward[-1] = SrtSegment(
            index=0,
            start_time=prev.start_time,
            end_time=segments[-1].end_time,
            text=prev.text + pending_text,
        )
    elif pending_text:
        # Only segment(s) were all short; just keep them
        forward.append(SrtSegment(
            index=0,
            start_time=pending_start,
            end_time=segments[-1].end_time,
            text=pending_text,
        ))

    return forward


def _merge_broken_words(segments: List[SrtSegment]) -> List[SrtSegment]:
    """Merge adjacent segments when a jieba word spans the boundary.

    ASR (Whisper) sometimes splits in the middle of a word, e.g.
    "这是一条专" | "门为你而来的" — the word "专门" is broken across two
    segments.  This function detects such cases and merges the pair.

    Requires jieba; skipped gracefully when jieba is unavailable.
    """
    if not _HAS_JIEBA or len(segments) < 2:
        return segments

    merged: List[SrtSegment] = []
    i = 0
    while i < len(segments):
        if i + 1 < len(segments):
            left_text = segments[i].text
            right_text = segments[i + 1].text
            combined = left_text + right_text
            boundary = len(left_text)

            # Check if any jieba word straddles the boundary
            words = jieba.lcut(combined)
            pos = 0
            broken = False
            for w in words:
                word_start = pos
                word_end = pos + len(w)
                if word_start < boundary < word_end:
                    broken = True
                    break
                pos = word_end

            if broken:
                merged.append(SrtSegment(
                    index=0,
                    start_time=segments[i].start_time,
                    end_time=segments[i + 1].end_time,
                    text=combined,
                ))
                i += 2
                continue

        merged.append(segments[i])
        i += 1

    return merged


def _merge_semantic_fragments(
    segments: List[SrtSegment],
    max_chars: int,
    max_gap_ms: int = 500,
    trailing_len_threshold: int = 10,
) -> List[SrtSegment]:
    """Merge semantically incomplete segment pairs before DP splitting.

    Two rules trigger a merge (subject to max_chars and max_gap_ms guards):
      Rule 1 (trailing): current segment ends with a dangling preposition,
        conjunction, particle, or light verb AND is short (<= trailing_len_threshold).
      Rule 2 (leading): next segment starts with a structural particle or
        measure word that cannot stand alone.

    The loop repeats until no further merges occur (convergence by segment count).

    Golden-test note: to validate, feed a real SRT file through this function
    and assert the output segment texts match expected merged strings.
    """
    if len(segments) < 2:
        return segments

    merged = list(segments)

    while True:
        new_merged: List[SrtSegment] = []
        i = 0
        while i < len(merged):
            if i + 1 < len(merged):
                current = merged[i]
                next_seg = merged[i + 1]
                combined_len = len(current.text) + len(next_seg.text)

                # Time-gap guard: do not merge across silence > max_gap_ms
                gap_ms = _time_to_ms(next_seg.start_time) - _time_to_ms(current.end_time)

                should_merge = False
                # Rule 1: trailing — only short segments trigger this
                if (current.text
                        and current.text[-1] in _TRAILING_MERGE_CHARS
                        and len(current.text) <= trailing_len_threshold):
                    should_merge = True
                # Rule 2: leading — next segment starts with a bound morpheme
                if next_seg.text and next_seg.text[0] in _LEADING_MERGE_CHARS:
                    should_merge = True

                if should_merge and combined_len <= max_chars and gap_ms <= max_gap_ms:
                    new_merged.append(SrtSegment(
                        index=0,
                        start_time=current.start_time,
                        end_time=next_seg.end_time,
                        text=current.text + next_seg.text,
                    ))
                    i += 2
                    continue

            new_merged.append(merged[i])
            i += 1

        # Terminate when no merge happened (segment count unchanged)
        if len(new_merged) == len(merged):
            break
        merged = new_merged

    return merged


def _opportunistic_merge(
    segments: List[SrtSegment],
    max_chars: int,
    max_gap_ms: int = 500,
) -> List[SrtSegment]:
    """Re-join adjacent segments whose boundary has a high split penalty.

    When ASR already broke the text at a bad point (e.g. "强大的" | "能量"),
    the semantic merge rules may not catch it because neither segment is
    particularly short.  This function checks the *actual* split penalty at
    every adjacent boundary and merges the pair when:
      - penalty >= 10 (inside-word or hard-prohibit)
      - combined length <= max_chars * 2.5 (so DP can re-split later)
      - time gap <= max_gap_ms

    The merged segment will be re-split by the subsequent DP pass.
    """
    if len(segments) < 2:
        return segments

    merged: List[SrtSegment] = []
    i = 0
    while i < len(segments):
        if i + 1 < len(segments):
            current = segments[i]
            next_seg = segments[i + 1]
            combined = current.text + next_seg.text
            boundary = len(current.text)

            boundaries = _word_boundary_set(combined)
            penalty = _split_penalty(combined, boundary, boundaries)

            gap_ms = _time_to_ms(next_seg.start_time) - _time_to_ms(current.end_time)

            if (penalty >= 10
                    and len(combined) <= max_chars * 2.5
                    and gap_ms <= max_gap_ms):
                merged.append(SrtSegment(
                    index=0,
                    start_time=current.start_time,
                    end_time=next_seg.end_time,
                    text=combined,
                ))
                i += 2
                continue

        merged.append(segments[i])
        i += 1

    return merged


# --- Time distribution ---------------------------------------------------

def _distribute_time(
    start_ms: int,
    end_ms: int,
    chunks: List[str],
) -> List[Tuple[int, int]]:
    """Distribute [start_ms, end_ms) across *chunks* proportionally.

    Punctuation characters are excluded from the weight since they do not
    occupy pronunciation time.
    """
    def _speaking_len(text: str) -> int:
        return sum(1 for ch in text if ch not in _PUNCTUATION)

    total_chars = sum(_speaking_len(c) for c in chunks)
    if total_chars == 0:
        return [(start_ms, end_ms)] * len(chunks)

    duration = end_ms - start_ms
    spans: List[Tuple[int, int]] = []
    cursor = start_ms

    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            spans.append((cursor, end_ms))
        else:
            chunk_dur = round(duration * _speaking_len(chunk) / total_chars)
            span_end = cursor + chunk_dur
            spans.append((cursor, span_end))
            cursor = span_end

    return spans


# --- Public API -----------------------------------------------------------

def split_long_segments(srt_content: str, max_chars: int) -> str:
    """Split SRT segments that exceed *max_chars* and return new SRT content.

    Pipeline: parse -> merge short fragments -> repair broken words -> DP split -> rebuild.
    *max_chars* <= 0 means no splitting; the original content is returned.
    """
    if max_chars <= 0:
        return srt_content

    segments = parse_srt(srt_content)
    if not segments:
        return srt_content

    # Step 1: merge ASR fragments (<=3 chars) into neighbours
    segments = _merge_short_segments(segments)

    # Step 2: repair cross-segment broken words (requires jieba)
    segments = _merge_broken_words(segments)

    # Step 3: merge semantically incomplete fragments (dangling prepositions etc.)
    segments = _merge_semantic_fragments(segments, max_chars)

    # Step 3b: opportunistic merge — re-join segments broken at bad boundaries
    segments = _opportunistic_merge(segments, max_chars)

    # Step 4: split segments that still exceed max_chars
    new_segments: List[SrtSegment] = []

    for seg in segments:
        if len(seg.text) <= max_chars:
            new_segments.append(seg)
            continue

        chunks = _split_text(seg.text, max_chars)
        start_ms = _time_to_ms(seg.start_time)
        end_ms = _time_to_ms(seg.end_time)
        spans = _distribute_time(start_ms, end_ms, chunks)

        for chunk, (s, e) in zip(chunks, spans):
            new_segments.append(SrtSegment(
                index=0,
                start_time=_ms_to_time(s),
                end_time=_ms_to_time(e),
                text=chunk,
            ))

    return build_srt(new_segments)

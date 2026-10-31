# MOTION

Read this before designing or animating anything for The Last Clue.

## 1. Colour

From `frontend/src/styles/app.css` and the in-app LED visualizer. Do not invent hex codes.

| Role | Hex | Use |
| --- | --- | --- |
| Ground | `#c8c2c6` | Light page / fog field |
| Surface | `#efe4d4` | Bone parchment cards |
| Ink | `#00142f` | Type, logo stroke, ghost eyes |
| Muted | `#556070` | Secondary lines |
| Accent | `#e11d38` | Mouth on the official mark, alerts |
| Blue | `#0070f3` | UI actions only, not a wash |
| LED board | `#0b0f17` | Matrix close-up ground |
| LED on | `#38bdf8` | Lit matrix pixels |
| LED off | `#1e2636` | Unlit matrix pixels |
| Fade | `#000000` | Outro fade-out only |

Washes (from the live page): faint red ember `rgba(225, 29, 56, 0.12)` top-right, navy `rgba(0, 20, 47, 0.12)` bottom-left, warm lift `rgba(255, 248, 236, 0.42)` centre. No purple-to-blue gradients.

## 2. Type

- Family: DM Sans (files in `demo-output/outro/assets/fonts/`).
- Wordmark `THE LAST CLUE`: ExtraBold 800, letter-spacing `0.02em` in the outro lockup, ink, ≥ 88px on 1920×1080.
- Scene line `THE GAME ENDS. THE GHOST REMAINS.`: ExtraBold, ≥ 42px.
- Tagline `One Word. One Imposter. Zero Trust.`: Italic, muted, ≥ 28px.
- Support caps (`ARDUINO UNO Q × LOCAL AI`, `OPEN SOURCE PROJECT`): ExtraBold, letter-spacing `0.08em`, muted, ≥ 18px.
- Labels never under 18px on 1080p. No text gradients. No typewriter on headlines.

## 3. Timing (8.0s, 30fps, not a loop)

| Beat | Seconds | What happens |
| --- | --- | --- |
| Final glance | 0.00–1.50 | Real 8×13 lobby ghost on the LED board. One blink 0.72–0.96. |
| Cross | 1.20–1.90 | Hardware board fades; fog field comes in. |
| Ghost remains | 1.50–4.00 | Official ghost mark drifts up 16px, rotates 1.6°, opacity ease. Line fades in 1.85–2.55. |
| Logo reveal | 4.00–4.90 | Ghost line leaves. Framed `assets/logo.svg` + wordmark settle. |
| Hold | 4.90–7.15 | Lockup holds. Tagline, then tech, then open-source. Logo ghost blinks 6.55–6.82. |
| Out | 7.15–8.00 | Fade to black. Frame 8.00 is black. |

`seek(0)` is the matrix. `seek(8)` is black. This is an ending, not a loop.

## 4. How things move

- 30 fps. One clock. Every pixel is a function of time (`window.seek(seconds)`).
- Ease: cubic in-out for fades, cubic-out for settles, short overshoot no more than 1.02 scale.
- No linear slides. No bounce. Ghost drift is slow and even, then rests.
- One focus at a time: matrix, then ghost+line, then the complete lockup.
- Reduced motion: show the held lockup (t = 5.6) with no drift.

## 5. Texture and finish

- Light haunted-parlor field, not a dark trailer.
- LED scene uses the app’s own matrix colours and the lobby sprites from `python/last_clue/hardware/frames.py` (`SPRITE_CALM_A` / closed-eye blink).
- Logo is the real SVG. Do not redraw it. If the SVG has no wordmark, set `THE LAST CLUE` in DM Sans beside it.
- Atmosphere: two soft washes only. No smoke, no particle logo, no neon bloom.

## 6. Never

1. Invent a hex code or a second ghost.
2. Fake a photograph of an Arduino board.
3. Purple-blue gradient backgrounds.
4. Typewriter headlines, bouncing type, or emoji as the mark.
5. Heavy glow, clip art, or stock horror footage.

## 7. Shot list done right

0.2s: 8×13 calm ghost, large, centred on `#0b0f17`.  
0.8s: eyes shut for one beat, then open.  
1.6s: board fading, official ghost mark appearing on `#c8c2c6`.  
2.6s: `THE GAME ENDS. THE GHOST REMAINS.` readable, ghost still.  
5.2s: framed logo + `THE LAST CLUE` + tagline + two support lines, lots of air.  
6.7s: one blink in the mark.  
8.0s: black.

# Frontend — Future Ideas (not started)

Backlog of frontend ideas raised while working on other things. Nothing here is scheduled —
surface this file and ask before starting any of it when frontend work comes up.

## 1. Streaming + in-between agent steps

Right now `POST /chat` is request/response: the UI shows a loading-dots placeholder until the
whole turn (routing, tool calls, SQL execution, final answer) comes back at once.

Idea: stream the reply, and surface the in-between steps (routing decision, "running query",
"generating chart", etc.) as they happen — not just the final answer appearing all at once.

Reference: **AIBA**, a similar frontend the user has seen, does this well. When picking this up,
look at how AIBA structures its streaming + step UI and adapt the pattern rather than designing
from scratch. This is a backend change too (SSE/websocket from `/chat`, or a new streaming
endpoint) — not frontend-only.

## 2. Ambient nature theme (light = day, dark = night)

Not a redesign of the functional UI (chat bubbles, inputs, etc. stay as they are) — an ambient
background feel layered behind/around it. Blue-sky-and-windmills, nature themed. Doesn't have to
be literal photography — could be minimal, blurred, abstract, low-detail. The goal is a calming
feel, not a busy illustration competing with the chat content.

- **Light mode**: daytime blue sky, windmills.
- **Dark mode (night)**: same point of view/place as the light scene, just at night — like sitting
  between plains/mountains. Three windmills, far off, upper-left. A moon, and stars twinkling in
  the sky.
- Execution is open — could be a subtle blurred gradient/CSS scene, a very light SVG illustration,
  actual images, or something animated (twinkling stars) — undecided. Whatever it is, it must stay
  out of the way of readability and not add visual noise to the chat itself.

## 3. App icon

Blue-sky-colored background, a whitish three-winged windmill (blades tapered to the tips) as the
mark — similar in style/flatness to the Google Photos app icon. A little shadow in the middle of
the windmill for depth. Minimal — the goal is a calming impression, not a detailed illustration.

Ties into idea #2 (windmill as the recurring visual motif of the ambient theme).

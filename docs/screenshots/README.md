# Screenshots

Drop three PNGs in this directory (~1200px wide each) to wire up the README image block.

## 1. `chat-ui.png`

What to capture: the chat UI at `http://localhost:3003` after asking a portfolio query that returns 2+ holdings.

Suggested query: **`What does FLORES FAMILY TR own?`**

Make sure the screenshot shows:
- The user query bubble (right side, blue)
- The agent's answer bubble with the markdown table of holdings
- The fuchsia `intent: portfolio` chip above the answer
- The citation chips at the bottom (APNs like `461-211-62`, `447-281-05`)
- The italic synthetic-data disclaimer at the bottom of the answer
- The 👍/👎 feedback row
- The side panel on the right showing the retrieved parcel cards with the amber `synthetic` chips

Crop to roughly the chat area + side panel. Hide the URL bar.

## 2. `langfuse-trace.png`

What to capture: a single trace in Langfuse showing the full waterfall.

Steps:
1. Open https://us.cloud.langfuse.com/project/<your-project-id>/traces
2. Click any recent `oci.query` trace
3. Crop to show the trace name, tags (`intent:...`, `source:...`), and the timeline view with `router → retrieval → summarize → ChatAnthropic` nested

The waterfall view is the most diagnostically useful single image — it's the screenshot that says "yes this is a production-shaped LangGraph agent."

## 3. `langfuse-filtered.png`

What to capture: the traces list filtered by a single source tag.

Steps:
1. Go to the traces list
2. In the left sidebar, click `source:live_arcgis_fallback` checkbox alone
3. Capture the resulting filtered list — even if there are only 2-3 rows, that's the point: "this is how often the seed didn't cover the user's query"

If you have eval-tagged traces too, an alternative is to filter by the `eval` tag — same point, different angle.

---

## Capture tips
- Browser zoom 100%, viewport ~1280×800
- Dark mode for the UI (matches the chat's default Tailwind theme)
- Light mode for Langfuse if your account uses it; otherwise dark
- Save as PNG with `_compressed` variants only if file size matters

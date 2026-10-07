# Reviewer diagram assets

These are architecture diagrams generated from Mermaid source, not product screenshots. Arrows were checked against main `b58beda` on October 7, 2026. Solid/dashed lines identify ordinary dependencies versus configured/separately gated paths; color groups components, not runtime health.

| Asset | Source of truth | Use |
| --- | --- | --- |
| [System overview](system-overview.svg) | [Overview Mermaid](system-overview.mmd). | README and presentation. |
| [External architecture](system-architecture.svg) | First Mermaid fence in [architecture](../architecture.md); mirrored [source](system-architecture.mmd). | Technical component/dependency view. |
| [Governed workflow](governed-workflow.svg) | Second architecture fence; mirrored [source](governed-workflow.mmd). | Strategy path and separate owner/manual demo origin. |
| [Agent grounding](agent-grounding.svg) | Third architecture fence; mirrored [source](agent-grounding.mmd). | SQL lexical Agent retrieval, separate vector service and confirmation. |
| [Persistent memory and learning](persistence-learning.svg) | Fourth architecture fence; mirrored [source](persistence-learning.mmd). | Durable facts and governed promotion. |

The SVGs were parsed and rendered with **Mermaid 11.12.1 in Chromium**, using [the theme configuration](mermaid-config.json). Native SVG text is used rather than HTML labels. Open a diagram directly to inspect its full-size labels. The slide deck summarizes dense flows and links the complete diagrams.

## Regeneration

After editing an architecture fence, copy its exact body into the corresponding `.mmd` file. Regenerate each `.svg` with Mermaid/Chromium and the committed configuration. A Mermaid CLI invocation from the repository root is:

```sh
npx --yes --package @mermaid-js/mermaid-cli mmdc \
  -i docs/diagrams/system-overview.mmd \
  -o docs/diagrams/system-overview.svg \
  -c docs/diagrams/mermaid-config.json -b transparent
```

Repeat for the four detailed sources. The installed CLI may resolve a different Mermaid version; record it when regenerating and inspect the output rather than asserting byte-for-byte identity. Chromium must be available to that CLI. Install documentation tooling into a temporary location; do not change application manifests/locks for these assets.

## Offline presentation

The [12-slide narrative](../reviewer_presentation.md) is the text authority. The [HTML deck](../reviewer_presentation.html) includes its messages, points, speaker notes and demonstration/fallback script. It uses the adjacent SVGs, system fonts and embedded controls, with no CDN or application login. Open it through a local static server or a browser that permits local files; use arrow keys, Notes and Demo script. The [PDF](../reviewer_presentation.pdf) is a printable slide export; speaker notes remain in the narrative/HTML.

To rebuild HTML after changing the narrative, install Marked in a temporary tools directory and run the documentation generator:

```sh
npm install --prefix /tmp/alphatrade-doc-tools --cache /tmp/alphatrade-npm-cache \
  --no-audit --no-fund marked@16.4.1
node docs/tools/build_reviewer_presentation.mjs --tools-dir /tmp/alphatrade-doc-tools
```

Export the regenerated HTML through Chromium's landscape print/PDF flow. Verify all 12 pages, image loads and readable labels. Copy `docs/`, including `diagrams/`, alongside the README when transferring this package; relative links are independent of the destination repository owner/name. No Turing College repository is modified by generation or verification.

<!-- mermaid-ai-skills:start -->
## Mermaid Diagrams

When the user asks to create, edit, or visualize a diagram, follow the
instructions in `.github/instructions/mermaid.instructions.md`.
<!-- mermaid-ai-skills:end -->

## ACRME research & design

For any ACRME research or design work (capacity reservations, CRGs, quota,
zones, placement scoring, DR sizing, ADRs, reference docs), follow
`.github/skills/grounding-acrme-research-design/SKILL.md`, or run as the
`acrme-research-designer` agent (`.github/agents/acrme-research-designer.agent.md`).
Always start with
`python3 .github/skills/grounding-acrme-research-design/scripts/check_grounding.py --baseline-only`.

For Azure research and fact-checking, use Microsoft Learn MCP to search and
fetch official documentation, and Azure MCP documentation/service guidance
where relevant. Discover the available tools and their schemas before calling
them; server prefixes vary across hosts. Follow the grounding skill's Step 3
for citations, evidence classification, tool-unavailability fallbacks, and
read-only environment boundaries. Do not treat MCP access as permission to
query live environments or execute POCs.

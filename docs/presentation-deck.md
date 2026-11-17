# A presentation deck with your own AI

Release 5.7, R5.7-P1 (owner, 16 Nov 2026, 09:57, agreed 16:16 to 16:18 and 17 Nov 2026 13:52; D731). EA Explorer
gives your own AI the content for a deck about a project, through MCP; you talk the deck through with the AI in your
own client, which builds it there, in its own look. EA Explorer keeps nothing of the deck.

## The tools

| Tool | What it gives |
|---|---|
| `deck_outline(project, audience?, slides?)` | A suggested outline from where the project is: the title, why, where we are (the ADM phase now), what is done, the architecture, the customer and the business, decisions, requirements, risks, open questions, sign-offs waiting, next steps. Each slide says which sources to use. A suggestion only: change it with the AI |
| `deck_sources(project, parts?)` | Everything a deck may draw on, each with its **source** (so a slide can say where it came from): the project, its phases with the steps done and the deliverables and artifacts with their documents (titles, states, versions), models, views and drawn views, decisions, dispensations, risks, issues, requirements, key questions, sign-offs, stakeholders, canvases and customer journeys |
| `view_picture(model, view, format?, scale?)` | A view (VP-11, or the organisation's own) or a drawn view as a **PNG** or an **SVG**, drawn as on EA Explorer's screens with the ArchiMate boxes and icons; or as **data** to draw your own: every object (type, notation, name, code, domain, position, size, colour), every relationship (type, source, target, end points) and the domain bands |

The other tools (`get_project`, `model_through_view`, `get_entity`, `customer_journey`, `business_model_canvas` and so
on) give more detail where a slide needs it.

## Rules

* **Anyone signed in through MCP** may use them, and gets only what their own roles let them read: any project and
  model they may read.
* A document marked **NOT FOR AI USE OR AUTOMATED PROCESSING** is given by its **title only** (`titles_only`, and
  `not_for_ai` on the document); its content is never to be read or used.
* The deck **stays with you**: nothing is saved back to EA Explorer, and it takes the AI client's own look.
* Pictures are drawn each time from the model as it is now; nothing is stored.

## To test

1. In your MCP client: "Make a ten-slide deck about Protea Claims Transformation 2028 for the board." The AI calls
   `deck_outline`, then `deck_sources`, and asks before building.
2. Ask for the application landscape: `view_picture` with VP-11 (or a drawn view's name) as a PNG; then as an SVG; then
   as data.
3. Check each slide says where its content came from, and that a document marked NOT FOR AI shows only its title.

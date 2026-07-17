"""
build_terms_page.py

Reads all three WDDS schemas and generates docs/terms/index.html —
a terms reference page where each term has a stable id anchor.

Schemas covered:
  - wdds_schema/schemas/disease_data.json
  - wdds_schema/schemas/project_metadata.json
  - wdds_schema/schemas/datacite/datacite-v4.5.json

Usage:
    python scripts/build_terms_page.py

Output:
    docs/terms/index.html
"""

from __future__ import annotations

import json
import re
import html as html_lib
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = REPO_ROOT / "wdds_schema" / "schemas"
DISEASE_DATA_SCHEMA  = SCHEMAS_DIR / "disease_data.json"
PROJECT_META_SCHEMA  = SCHEMAS_DIR / "project_metadata.json"
DATACITE_SCHEMA      = SCHEMAS_DIR / "datacite" / "datacite-v4.5.json"
WDDS_SCHEMA          = REPO_ROOT / "wdds_schema" / "wdds_schema.json"
OUTPUT_DIR           = REPO_ROOT / "docs" / "terms"
OUTPUT_FILE          = OUTPUT_DIR / "index.html"
BASE_URI_GENERIC = "https://w3id.org/wdds/terms"

BASE_URI_DISEASE  = "https://w3id.org/wdds/terms/disease-data/"
BASE_URI_METADATA = "https://w3id.org/wdds/terms/project-metadata/"
DATACITE_DOCS     = "https://datacite-metadata-schema.readthedocs.io/en/4.5/"

# Schema source URIs shown in each term card
SCHEMA_URIS = {
    "disease_data": (
        "https://raw.githubusercontent.com/viralemergence/wdds/main"
        "/wdds_schema/schemas/disease_data.json"
    ),
    "project_metadata": (
        "https://raw.githubusercontent.com/viralemergence/wdds/main"
        "/wdds_schema/schemas/project_metadata.json"
    ),
    "datacite": (
        "https://raw.githubusercontent.com/viralemergence/wdds/main"
        "/wdds_schema/schemas/datacite/datacite-v4.5.json"
    ),
}


# ---------------------------------------------------------------------------
# Schema loading and $ref resolution
# ---------------------------------------------------------------------------

def load_schema(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_ref(ref: str, datacite: dict) -> dict:
    """
    Resolve a $ref string that points into the DataCite schema.
    Handles patterns like:
      datacite/datacite-v4.5.json#/properties/creators
      datacite/datacite-v4.5.json#/definitions/relatedIdentifierType
    Returns {} if the ref cannot be resolved.
    """
    if "#" not in ref:
        return {}
    _, pointer = ref.split("#", 1)
    parts = [p for p in pointer.split("/") if p]
    node = datacite
    try:
        for part in parts:
            node = node[part]
        return node
    except (KeyError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def h(text: str) -> str:
    """HTML-escape a string."""
    return html_lib.escape(str(text))


def badge(label: str, css_class: str) -> str:
    return f'<span class="badge {css_class}">{h(label)}</span>'


def extract_dwc_uri(description: str) -> str | None:
    """Pull a 'See <url>' Darwin Core reference from a description string."""
    match = re.search(r"See (https?://\S+)", description)
    return match.group(1).rstrip(".") if match else None


def strip_see_url(description: str) -> str:
    """Remove trailing 'See <url>' from a description for display."""
    return re.sub(r"\s*See https?://\S+\.?$", "", description).strip()


def format_type(schema_node: dict) -> str:
    """
    Return badge HTML for the type of a schema node.
    Checks items.type (arrays) then type directly.
    """
    items = schema_node.get("items", {})
    type_val = items.get("type") if items else schema_node.get("type")

    # print("node id")
    # print(schema_node.get("$id"))
    # print(schema_node.get("type"))


    if not type_val:
        print("not type_val")
        return badge("object", "type")

    if isinstance(type_val, list):
        types    = [t for t in type_val if t != "null"]
        if schema_node.get("type") == "array":
            types = ["array"] + types
        nullable = "null" in type_val
    else:
        types    = [type_val]
        if schema_node.get("type") == "array":
            types = ["array"] + types
        nullable = False

    out = " ".join(badge(t, "type") for t in types)
    if nullable:
        out += " " + badge("nullable", "nullable")
   
    return out


def format_enum(values: list) -> str:
    non_null = [v for v in values if v is not None]
    pills = " ".join(badge(str(v), "enum-val") for v in non_null)
    return f'<div class="enum-list"><strong>Allowed values:</strong> {pills}</div>'


def format_examples(examples: list) -> str:
    items = ", ".join(f"<code>{h(str(e))}</code>" for e in examples)
    return f'<div class="examples"><strong>Examples:</strong> {items}</div>'


def format_constraints(schema_node: dict) -> list[str]:
    """Collect min/max/pattern constraints from a schema node or its items."""
    src = schema_node.get("items", schema_node)
    out = []
    if "minimum" in src:
        out.append(f"minimum: {src['minimum']}")
    if "maximum" in src:
        out.append(f"maximum: {src['maximum']}")
    if "minItems" in src:
        out.append(f"minItems: {src['minItems']}")
    if "pattern" in src:
        out.append(f"pattern: <code>{h(src['pattern'])}</code>")
    if "uniqueItems" in src:
        out.append(f"uniqueItems: <code>{h(src['uniqueItems'])}</code>")
    return out


def get_enum_from_node(node: dict) -> list | None:
    """Find enum values in a node, checking items sub-schema too."""
    if "enum" in node:
        return node["enum"]
    items = node.get("items", {})
    if "enum" in items:
        return items["enum"]
    return None


# ---------------------------------------------------------------------------
# Term card rendering
# ---------------------------------------------------------------------------

def render_term(
    anchor_id: str,
    display_name: str,
    definition: dict,
    *,
    source_key: str,
    is_required: bool = False,
    datacite_ref: str | None = None,
    base_uri: str | None = None,
    indent: int = 0,
) -> str:
    """
    Render a single term as a <section> card.

    anchor_id    : the HTML id attribute (used for fragment links)
    display_name : human-readable name shown in the card header
    definition   : the schema dict for this term
    source_key   : key into SCHEMA_URIS
    is_required  : whether this term is required
    datacite_ref : original $ref string if this term delegates to DataCite
    base_uri     : w3id.org base URI for this term; None suppresses the URI row
    indent       : 0 = top-level, 1 = nested sub-property (visual indent)
    """
    description  = definition.get("description", "")
    examples     = definition.get("examples", [])
    enum_vals    = get_enum_from_node(definition)
    dwc_uri      = extract_dwc_uri(description)
    display_desc = strip_see_url(description)
    constraints  = format_constraints(definition)
    type_html    = format_type(definition)
    schema_uri   = SCHEMA_URIS[source_key]
    indent_class = " nested" if indent else ""

    lines = [
        f'  <section class="term{indent_class}" id="{h(anchor_id)}">',
        f'    <div class="term-header">',
        f'      <h3 class="term-name">{h(display_name)}</h3>',
        f'      <div class="term-badges">',
        f'        {type_html}',
        f'        {badge("required", "required") if is_required else badge("optional", "optional")}',
        f'      </div>',
        f'    </div>',
        f'    <div class="term-body">',
    ]

    if display_desc:
        lines.append(f'      <p class="term-desc">{h(display_desc)}</p>')

    if enum_vals:
        lines.append(f"      {format_enum(enum_vals)}")

    if examples:
        lines.append(f"      {format_examples(examples)}")

    if constraints:
        lines.append(
            f'      <div class="constraints">'
            f'<strong>Constraints:</strong> {"; ".join(constraints)}</div>'
        )

    if base_uri:
        term_uri = f"{base_uri}{anchor_id}"
        lines.append(
            f'      <div class="term-uri">'
            f'<strong>URI:</strong> <a href="{term_uri}">{term_uri}</a></div>'
        )

    if dwc_uri:
        lines.append(
            f'      <div class="dwc-ref">'
            f'<strong>Darwin Core mapping:</strong> '
            f'<a href="{dwc_uri}">{dwc_uri}</a></div>'
        )

    if datacite_ref:
        lines.append(
            f'      <div class="datacite-ref">'
            f'<strong>DataCite field:</strong> '
            f'<a href="{DATACITE_DOCS}/search/?q={display_name}">{h(datacite_ref)}</a></div>'
        )

    lines.append(
        f'      <div class="schema-ref">'
        f'<strong>Defined in:</strong> '
        f'<a href="{schema_uri}">{schema_uri}</a></div>'
    )

    lines.append("    </div>")
    lines.append("  </section>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_disease_data_section(schema: dict) -> tuple[str, list[str]]:
    """
    Returns (html_string, list_of_anchor_ids) for the disease data section.
    Required terms first, then optional, both alphabetically sorted.
    """
    properties = schema.get("properties", {})
    required   = set(schema.get("required", []))

    req_terms = sorted(k for k in properties if k in required)
    opt_terms = sorted(k for k in properties if k not in required)
    ordered   = req_terms + opt_terms

    cards = []
    anchors = []
    for name in ordered:
        cards.append(render_term(
            anchor_id    = name,
            display_name = name,
            definition   = properties[name],
            source_key   = "disease_data",
            is_required  = name in required,
            base_uri     = BASE_URI_DISEASE,
        ))
        anchors.append(name)

    section_html = (
        '<div class="schema-section" id="section-disease-data">\n'
        '  <h2 class="section-title">Disease Data Terms</h2>\n'
        '  <p class="section-desc">Fields defined in '
        '<code>wdds_schema/schemas/disease_data.json</code>. '
        'Each term URI follows the pattern '
        f'<code>{BASE_URI_DISEASE}{{termName}}</code>.</p>\n'
        + "\n\n".join(cards)
        + "\n</div>"
    )
    return section_html, anchors


def build_project_metadata_section(
    schema: dict, datacite: dict
) -> tuple[str, list[str]]:
    """
    Returns (html_string, list_of_anchor_ids) for the project metadata section.
    Resolves $ref fields against the DataCite schema.
    Nested sub-properties (e.g. methodology.eventBased) get their own cards.
    """
    properties = schema.get("properties", {})
    required   = set(schema.get("required", []))

    req_terms = sorted(k for k in properties if k in required)
    opt_terms = sorted(k for k in properties if k not in required)
    ordered   = req_terms + opt_terms

    cards   = []
    anchors = []

    for name in ordered:
        defn = properties[name]

        # Inline nested object (e.g. methodology)
        if defn.get("type") == "object" and "properties" in defn:
            # Render parent card
            cards.append(render_term(
                anchor_id    = name,
                display_name = name,
                definition   = defn,
                source_key   = "project_metadata",
                is_required  = name in required,
                base_uri     = BASE_URI_METADATA,
            ))
            anchors.append(name)

            # Render each sub-property as an indented card
            sub_required = set()
            for req_clause in defn.get("anyOf", []) + defn.get("allOf", []):
                sub_required.update(req_clause.get("required", []))

            for sub_name, sub_defn in defn["properties"].items():
                anchor = f"{name}-{sub_name}"
                cards.append(render_term(
                    anchor_id    = anchor,
                    display_name = f"{name}.{sub_name}",
                    definition   = sub_defn,
                    source_key   = "project_metadata",
                    is_required  = sub_name in sub_required,
                    base_uri     = BASE_URI_METADATA,
                    indent       = 1,
                ))
                anchors.append(anchor)
            continue
        
        # Array of objects (e.g. identifiers)
        if defn.get("type") == "array":
            # look for object in types
            items = defn.get("items", {})
            type_val = items.get("type")
            print("in array of objects")
            print(name)
            if "object" in type_val:
                # Render parent card
                cards.append(render_term(
                    anchor_id    = name,
                    display_name = name,
                    definition   = defn,
                    source_key   = "project_metadata",
                    is_required  = name in required,
                    base_uri     = BASE_URI_METADATA,
                ))
                anchors.append(name)

                # Render each sub-property as an indented card
                ## get required properties from items
                sub_required = items.get("required", [])
                
                print("about to create sub cards")
                print(items["properties"].items())
                for sub_name, sub_defn in items["properties"].items():
                    anchor = f"{name}-{sub_name}"
                    cards.append(render_term(
                        anchor_id    = anchor,
                        display_name = f"{name}.{sub_name}",
                        definition   = sub_defn,
                        source_key   = "project_metadata",
                        is_required  = sub_name in sub_required,
                        base_uri     = BASE_URI_METADATA,
                        indent       = 1,
                    ))
                    anchors.append(anchor)
            continue

        # $ref field — resolve and merge
        ref_str  = defn.get("$ref")
        resolved = resolve_ref(ref_str, datacite) if ref_str else {}

        # Local description overrides DataCite description
        merged = {**resolved, **{k: v for k, v in defn.items() if k != "$ref"}}
        if not merged.get("description") and resolved.get("description"):
            merged["description"] = resolved["description"]

        cards.append(render_term(
            anchor_id    = name,
            display_name = name,
            definition   = merged,
            source_key   = "project_metadata",
            is_required  = name in required,
            datacite_ref = ref_str,
            base_uri     = BASE_URI_METADATA,
        ))
        anchors.append(name)

    section_html = (
        '<div class="schema-section" id="section-project-metadata">\n'
        '  <h2 class="section-title">Project Metadata Terms</h2>\n'
        '  <p class="section-desc">Fields defined in '
        '<code>wdds_schema/schemas/project_metadata.json</code>. '
        'Each term URI follows the pattern '
        f'<code>{BASE_URI_METADATA}{{termName}}</code>.'
        'Largely following the '
        f'<a href="{DATACITE_DOCS}">DataCite 4.5 metadata schema</a>.</p>\n'
        + "\n\n".join(cards)
        + "\n</div>"
    )
    return section_html, anchors


def build_datacite_section(datacite: dict) -> tuple[str, list[str]]:
    """
    Returns (html_string, list_of_anchor_ids) for DataCite terms.
    Renders top-level properties and definitions that carry enum values
    (i.e., controlled vocabulary types).
    """
    properties  = datacite.get("properties", {})
    definitions = datacite.get("definitions", {})
    dc_required = set(datacite.get("required", []))

    cards   = []
    anchors = []

    # --- Top-level DataCite properties ---
    for name in sorted(properties):
        anchor = f"datacite-{name}"
        cards.append(render_term(
            anchor_id    = anchor,
            display_name = name,
            definition   = properties[name],
            source_key   = "datacite",
            is_required  = name in dc_required,
            base_uri     = None,
        ))
        anchors.append(anchor)

    # --- DataCite definitions (controlled vocabulary types) ---
    # Only render definitions that have enum values — these are the
    # controlled vocabularies (e.g. contributorType, relationType).
    enum_defs = {
        k: v for k, v in definitions.items()
        if get_enum_from_node(v) is not None
    }

    if enum_defs:
        cards.append(
            '<div class="subsection-heading">'
            '<h3>Controlled Vocabulary Types</h3>'
            '<p>Enumerated types defined in the DataCite schema '
            'and referenced by project metadata fields.</p>'
            '</div>'
        )
        for name in sorted(enum_defs):
            anchor = f"datacite-def-{name}"
            cards.append(render_term(
                anchor_id    = anchor,
                display_name = name,
                definition   = enum_defs[name],
                source_key   = "datacite",
                is_required  = False,
                base_uri     = None,
            ))
            anchors.append(anchor)

    section_html = (
        '<div class="schema-section" id="section-datacite">\n'
        '  <h2 class="section-title">DataCite Terms</h2>\n'
        '  <p class="section-desc">Fields from the '
        f'<a href="{DATACITE_DOCS}">DataCite 4.5 metadata schema</a> '
        'referenced by WDDS project metadata. '
        'Includes top-level properties and controlled vocabulary type definitions.</p>\n'
        + "\n\n".join(cards)
        + "\n</div>"
    )
    return section_html, anchors


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------

CSS = "../styles.css"

JS = """
const input   = document.getElementById('filter');
const terms   = document.querySelectorAll('.term');
const sections = document.querySelectorAll('.schema-section');

input.addEventListener('input', () => {
  const q = input.value.toLowerCase().trim();

  terms.forEach(t => {
    if (!q) { t.classList.remove('hidden'); return; }
    const text = (t.id + ' ' + t.innerText).toLowerCase();
    t.classList.toggle('hidden', !text.includes(q));
  });

  // Hide section headers when all their terms are hidden
  sections.forEach(sec => {
    const visible = [...sec.querySelectorAll('.term')]
      .some(t => !t.classList.contains('hidden'));
    sec.style.display = (!q || visible) ? '' : 'none';
  });
});
"""


def build_toc(
    dd_anchors: list[str],
    pm_anchors: list[str],
    dc_anchors: list[str],
) -> str:
    def link_list(anchors: list[str]) -> str:
        return "\n".join(
            f'      <a href="#{h(a)}">{h(a)}</a>' for a in anchors
        )

    return f"""<div class="toc" aria-label="Table of contents">
  <h2>Contents</h2>
  <div class="toc-group">
    <h3><a href="#section-disease-data">Disease Data</a></h3>
    <div class="toc-links">
{link_list(dd_anchors)}
    </div>
  </div>
  <div class="toc-group">
    <h3><a href="#section-project-metadata">Project Metadata</a></h3>
    <div class="toc-links">
{link_list(pm_anchors)}
    </div>
  </div>
  <div class="toc-group">
    <h3><a href="#section-datacite">DataCite</a></h3>
    <div class="toc-links">
{link_list(dc_anchors)}
    </div>
  </div>
</div>"""


def build_page(
    disease_html: str,
    project_html: str,
    datacite_html: str,
    dd_anchors: list[str],
    pm_anchors: list[str],
    dc_anchors: list[str],
    version_title: str,
) -> str:
    toc = build_toc(dd_anchors, pm_anchors, dc_anchors)
    total = len(dd_anchors) + len(pm_anchors) + len(dc_anchors)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Terms — {h(version_title)}</title>
  <link rel="stylesheet" href={CSS}>
</head>
<body>

<header>
  <h1>{h(version_title)}</h1>
  <p>Controlled vocabulary — {total} term definitions across three schemas</p>
</header>

<nav>
  <a href="https://viralemergence.github.io/wdds/">Home</a>
  <a href="https://viralemergence.github.io/wdds/terms/">Terms</a>
  <a href="https://github.com/viralemergence/wdds">GitHub</a>
</nav>

<main>
  <p class="intro">
    WDDS terms with a <span class="badge required">required</span> badge are
    mandatory fields. Disease data and Project metadata terms have stable URIs of the form
    <code>{BASE_URI_GENERIC}/{{sub-schema}}/{{termName}}</code>.
    Project metadata terms follow the
    <a href="{DATACITE_DOCS}">DataCite 4.5 schema</a> where indicated.
  </p>

{toc}

  <div class="filter-bar">
    <input id="filter" type="search"
           placeholder="Filter terms by name, badge, or description…"
           aria-label="Filter terms">
  </div>

{disease_html}

{project_html}

{datacite_html}
</main>

<footer>
  Generated from
  <a href="https://github.com/viralemergence/wdds">viralemergence/wdds</a>.
  WDDS terms are available via the
  <a href="https://w3id.org/wdds/">w3id.org/wdds</a> persistent namespace.
</footer>

<script>
{JS}
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    disease_schema  = load_schema(DISEASE_DATA_SCHEMA)
    project_schema  = load_schema(PROJECT_META_SCHEMA)
    datacite_schema = load_schema(DATACITE_SCHEMA)
    wdds_meta       = load_schema(WDDS_SCHEMA)

    version_title = wdds_meta.get("title","Wild Disease Data Standard")

    disease_html,  dd_anchors = build_disease_data_section(disease_schema)
    project_html,  pm_anchors = build_project_metadata_section(project_schema, datacite_schema)
    datacite_html, dc_anchors = build_datacite_section(datacite_schema)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    page = build_page(
        disease_html, project_html, datacite_html,
        dd_anchors, pm_anchors, dc_anchors,
        version_title,
    )
    OUTPUT_FILE.write_text(page, encoding="utf-8")

    print(f"Written: {OUTPUT_FILE}")
    print(f"  Disease data terms:    {len(dd_anchors)}")
    print(f"  Project metadata terms:{len(pm_anchors)}")
    print(f"  DataCite terms:        {len(dc_anchors)}")
    print(f"  Total:                 {len(dd_anchors) + len(pm_anchors) + len(dc_anchors)}")


if __name__ == "__main__":
    main()

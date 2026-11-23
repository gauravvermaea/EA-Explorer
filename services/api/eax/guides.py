"""The TOGAF guides EA Explorer follows (Release 12, R12.9; D879): each with its number, title, its page at The Open
Group and what EA Explorer uses it for, shown on the Reference library page and to the AI. EA Explorer carries none
of their text (each is The Open Group's, not for redistribution): only the reference, and what it is used for, in our
own words. The page address is the one the guides themselves give (www.opengroup.org/library/<number>).
"""

from __future__ import annotations

URL = "https://www.opengroup.org/library/{code}"

# (number, title, what EA Explorer uses it for, where)
GUIDES: list[tuple[str, str, str, str]] = [
    ("C220", "The TOGAF Standard, 10th Edition", "The ADM, its phases, steps, deliverables and artifacts; the content framework",
     "Projects, the project library"),
    ("G186", "A Practitioners' Approach to Developing Enterprise Architecture Following the TOGAF ADM",
     "The worked approach behind the project library's steps", "The project library"),
    ("G184", "The TOGAF Leader's Guide to Establishing and Evolving an EA Capability",
     "The EA capability project type: the Preliminary phase in full, the target capability and its roadmap", "Project templates"),
    ("G188", "Architecture Project Management", "The project plan: phases planned, milestones, RACI, approval gates, status",
     "A project's Project plan tab"),
    ("G176", "Business Scenarios", "Business scenarios to find and test requirements in Requirements Management",
     "The project library (RM), view VP-49"),
    ("G248", "An Approach to Selecting Building Blocks", "Choosing the building blocks in phases E and F",
     "The project library (E, F), view VP-58, the Building Block attribute"),
    ("G190", "Information Mapping", "The Information Map, always live from the model", "View VP-47"),
    ("G206", "Organization Mapping", "The Organization Map, always live from the model", "View VP-01"),
    ("G211", "Business Capabilities, Version 2", "Capability maps and heat maps; the business capability assessment survey",
     "View VP-19, Surveys"),
    ("G233", "Business Capability Planning", "Planning change from the capability map", "Capability views"),
    ("G178", "Value Streams", "Value streams and their stages", "Value stream views"),
    ("G18A", "Business Models", "The business model canvas", "A project's Business model canvas tab"),
    ("G210", "Applying the TOGAF ADM using Agile Sprints", "Sprints: the goal, Sprint zero, the review, the backlog's priorities",
     "The Agile project type, a project's Sprints tab"),
    ("G20F", "Enabling Enterprise Agility", "The Agile project type", "Project templates"),
    ("G217", "Using the TOGAF Standard in the Digital Enterprise", "The digital transformation project type", "Project templates"),
    ("G21H", "TOGAF Digital Business Reference Model", "The Digital Business Reference Model in the library",
     "The model library, the digital transformation model template"),
    ("G21D", "Government Reference Model", "The Government Reference Model in the library", "The model library, the government model template"),
    ("G212", "Digital Technology Adoption: A Guide to Readiness Assessment and Roadmap Development",
     "The digital technology readiness survey", "Surveys"),
    ("G203", "Architecture Maturity Models", "The EA capability maturity assessment (ACMM)", "Maturity"),
    ("G198", "Architecture Skills Framework", "TOGAF roles and skill levels beside each person's skills", "My profile, the Skills repository"),
    ("G249", "Architecture Roles and Skills", "The architect roles, skill categories and proficiency levels", "My profile, the Skills repository"),
    ("G152", "Integrating Risk and Security within a TOGAF Enterprise Architecture",
     "The risk and security project type, the risk register, views VP-50 to VP-53", "Project templates, the Governance log's Risks"),
    ("G21B", "Information Architecture: Customer Master Data Management (C-MDM)", "The data governance project type", "Project templates"),
    ("G234", "Information Architecture: Metadata Management", "The data governance project type, data ownership and lineage",
     "Project templates, views VP-54 to VP-56"),
    ("G238", "Information Architecture: Business Intelligence & Analytics", "Reports and dashboards as data objects in data lineage",
     "View VP-56"),
    ("C196", "Digital Practitioner Body of Knowledge (DPBoK)", "The digital competencies in the Digital Business Reference Model",
     "The model library"),
]


def listing() -> list[dict]:
    """Every guide, with its page."""
    return [{"code": c, "title": t, "used_for": u, "where": w, "url": URL.format(code=c.lower())} for c, t, u, w in GUIDES]

"""The Release 12 model templates (D858, D879): one for each new kind of work, each a locked template in the library
that new models start from.

A model template is structure and references only (D858): the ArchiMate 4 metamodel with the Release 12 types (risk
and security, data governance, Agile; seed/archimate4.py), and a description that says which element types the work
uses, which reference model to bring in and which viewpoints show it. No made-up starter elements: the samples show
them filled in (R12.7). The project templates of the same kind start their models from these (seed/project_templates.json,
slot "template"); Government is a model template only, used by any TOGAF project (D879).

The seed loads any that are missing, on a fresh install and on an upgrade alike (like the industry reference models).
"""

from __future__ import annotations

VERSION = "1.0"

# (code, name, description)
TEMPLATES = [
    ("government", "Government model template",
     "For a government organisation's architecture (TOGAF Series Guide: Government Reference Model, G21D). Use the "
     "Government Reference Model (TOGAF GRM) from the library in phase B: place the organisation's departments, agencies "
     "and services against its sectors, functions and services, and find the functions departments share. Element types: "
     "business actors for departments, agencies and other spheres of government; services for citizen and business "
     "services and their channels; work packages for programmes; drivers, principles and requirements for policy and "
     "legislation; capabilities for a department's capability map. Views: capability map, organisation map, service "
     "catalogue, roadmap. Structure only: start a model from it."),
    ("agile", "Agile model template",
     "For architecture done in sprints (TOGAF Series Guides: Applying the TOGAF ADM using Agile Sprints; Enabling "
     "Enterprise Agility). Element types: epics and features (the backlog's change), the capabilities, value streams and "
     "applications they change, requirements, and plateaus for each release's transition. Views: capability map, value "
     "stream map, roadmap. Structure only: start a model from it."),
    ("digital", "Digital transformation model template",
     "For a digital transformation that starts from the customer and the business model (The Open Group's Digital "
     "Practitioner Body of Knowledge, C196, and the TOGAF Digital Business Reference Model). Element types: products, "
     "value streams and their stages, capabilities with their maturity, business and data objects, applications and "
     "platforms, and the work packages and plateaus between transitions; customer journeys on the project. Views: value "
     "stream map, capability heat map, roadmap. Structure only: start a model from it."),
    ("ea-capability", "EA capability model template",
     "For setting up or evolving an organisation's enterprise architecture capability (TOGAF Leader's Guide to "
     "Establishing and Evolving an EA Capability). Element types: principles, the architecture organisation (actors and "
     "roles), the governance processes, the repository's applications, capabilities of the EA practice with their "
     "maturity, and the work packages of its improvement roadmap. Views: organisation map, capability heat map, roadmap. "
     "Structure only: start a model from it."),
    ("risk-security", "Risk and security model template",
     "For risk and security architecture (TOGAF Series Guide: Integrating Risk and Security within a TOGAF Enterprise "
     "Architecture, G152). Element types: risks with their likelihood, impact, treatment and residual risk, threats, "
     "controls, security requirements, and data classification on business and data objects, related to the "
     "applications, data, technology and business services they protect. Views: risk register, controls against risks, "
     "classified data and where it is held. Structure only: start a model from it."),
    ("data-governance", "Data governance model template",
     "For data architecture and governance (TOGAF Series Guides on master data, metadata, and business intelligence and "
     "analytics). Element types: data domains with their owner and steward, business and data objects with their system "
     "of record, quality rules with their targets, meanings for agreed definitions, and analytics products. Views: data "
     "with no owner or definition, master data held in more than one system, lineage from source to report, quality "
     "against target. Structure only: start a model from it."),
]


def key(code: str) -> str:
    """The template's model key (its guid is made from it)."""
    return f"model-template-{code}-{VERSION}"


def name(code: str) -> str:
    """The template's name."""
    return next(n for c, n, _d in TEMPLATES if c == code)

"""The structure of the TOGAF Series Guide: Digital Business Reference Model (DBRM, G21H, 2025), the source of
eax/seed/industry_dbrm.py: its four domains, ten core elements and their parts, and the DPBoK competencies that enable
each Digital Enablement pillar (the guide's Table 4-1). Names are the guide's (except "Objectives", a banned word, D114, which is "Targets"); every description is EA Explorer's own
(the guide's copy is not for redistribution). Run tools/build_dbrm_model.py after changing it.
"""

# (domain, description, [(element, description, [(part, description)])])
DBRM = [
 ("Digital Domain", "Working from the outside in: what customers need, and how the enterprise organises itself to deliver digitally.", [
  ("Customer Focus", "Seeing products and services as customers use them, including needs they have not said.", [
   ("Digital Context/Needs", "Whether customers are ready to adopt a digital offering, and the digital-first culture it needs inside."),
   ("Customer Experience", "Everything a customer goes through with the enterprise and its brand, over the whole time they are a customer."),
   ("Digital Value", "The value digital technology adds, directly and indirectly, to the enterprise's main value chain.")]),
  ("Digital Enterprise", "The portfolio, operations and competencies that let the enterprise deliver digitally.", [
   ("Digital Products and Service Portfolio/Model", "Managing products and services delivered fully digitally, or obtained by digital means."),
   ("Digital Operations", "The operating and business capabilities, value streams, processes, people and systems that run digital offerings at a fair cost."),
   ("Digital Competencies", "The resources, services and assets people and teams need to build digital offerings, in the DPBoK's four contexts.")])]),
 ("Strategy Domain", "The why of the business: its context, its motivation and the services and products at its core.", [
  ("Strategic Context", "The outside factors that can affect the business: law and regulation, markets, competitors, influencers and investors.", [
   ("Legislative and Regulatory Framework", "The rules the enterprise must keep to, the limits they set and the openings good compliance gives."),
   ("Market Trends and Consumer Drivers", "The industry's value chain, its trends, and how cost and value spread along it."),
   ("Industry Landscape and Competitors", "Who offers the same, and how they compare on value and performance."),
   ("Business Influencers and Customers", "What helps or hinders the business, inside and out, and how customers shape its direction."),
   ("Investment and Stakeholder Value Creation Framework", "What shareholders and other stakeholders value, and get, from the enterprise.")]),
  ("Business Motivation", "Why the business exists and how it stays sustainable and resilient.", [
   ("Business Vision and Mission", "Where the enterprise wants to go, and how it means to get there."),
   ("Business Strategy and Principles", "The chosen course of action and the principles that set priorities and drive capability development."),
   ("Business Measures, Outcome, and Impact", "The results sought, and the social, environmental and economic effect of the enterprise."),
   ("Strategic Goals, Targets, and Drivers", "The direction, and the short, medium and long-term goals that realise it."),
   ("Corporate Governance Framework and Enterprise Architecture Strategy", "The governance that sets acceptable behaviour, and the architecture strategy that guides investment.")]),
  ("Business Services and Products", "The services and products the enterprise treats as its core, to set priorities and sourcing.", [
   ("Primary Business Services", "The services the enterprise exists for: its main revenue and its edge."),
   ("Core Business Products", "The products that matter as much as the primary services, especially where production is central."),
   ("Value-Add Services", "Extras that delight customers or widen the offering without losing what the enterprise is.")])]),
 ("Structural Domain", "The what of the business: its ecosystem and business model, operating model and capabilities.", [
  ("Ecosystem and Business Model", "How the enterprise creates value with its partners, at the right cost and return.", [
   ("Business Ecosystem Model", "The partners and role players, what each provides, and the role the enterprise means to play."),
   ("Strategic Principles and Business Model", "The value proposition, how it is delivered and how it is paid for."),
   ("Policy and Risk Management Framework", "The policies and risk management that keep the business model within bounds."),
   ("Organization Culture and Behavior", "The culture and behaviour the business model depends on.")]),
  ("Operating Model", "How the enterprise organises itself to deliver its business model.", [
   ("Strategic Posture and Value Disciplines", "The stance and value discipline the enterprise chooses to compete on."),
   ("Service Model", "How services are delivered to customers."),
   ("Organizational Model", "How the organisation is arranged to deliver."),
   ("Resource Model", "The people, assets and money the operating model draws on.")]),
  ("Business Capability Model", "The capabilities the enterprise needs, grouped by what they are for.", [
   ("Customer-Facing and Marketing-Focused Capabilities", "Outward-facing capabilities that win and serve customers."),
   ("Service Delivery Management Capabilities", "The operational capabilities that deliver the services."),
   ("Service Delivery Enabling Capabilities", "Capabilities that support delivery without being at its core."),
   ("Shared & Support Capabilities", "Capabilities shared across the enterprise for efficiency.")])]),
 ("Operational Domain", "The how of the business: the operating environment and what makes digital delivery possible.", [
  ("Business Operating Environment", "The processes, systems and resources that run the business, operating and capability models.", [
   ("Service Experience and Customer Journey Maps", "How customers experience the services, step by step."),
   ("Value Chain Model and Value Streams", "How value is created, end to end."),
   ("Business Information Map", "The information the business needs and how it relates."),
   ("Business Process Map", "The business processes and how they connect."),
   ("Actors, Roles, and Organization Structure", "Who does what, and how they are organised."),
   ("Business Systems and Data Models", "The systems the business runs on, and their data.")]),
  ("Digital Enablement", "The strategies, principles and resources that let the business deliver digitally.", [
   ("Digital Principles and Strategy", "The principles and strategy for going digital."),
   ("Digital Governance", "How digital work is governed."),
   ("Digital Products and Services", "The digital offerings themselves."),
   ("Agile Digital Delivery Model", "How digital offerings are built and run in an Agile way."),
   ("Digital Platforms", "The shared digital platforms offerings are built on.")])]),
]

# the DPBoK's four contexts and their competencies (under Digital Competencies)
CONTEXTS = [
 ("Context I: Individual/Founder", "The minimum needed to deliver digital value.",
  ["Conception of Digital Value", "Digital Infrastructure and Related Practices", "Agile Development and Continuous Delivery"]),
 ("Context II: Team", "Working well as a team, the base of digital product development.",
  ["Product Management", "Work Execution", "Operations"]),
 ("Context III: Team of Teams", "Coordinating many teams without losing their cohesion.",
  ["Coordination Mechanisms", "Investment and Sourcing", "Organization and Cultural Factors"]),
 ("Context IV: Enduring Enterprise", "Steering, managing risk and assuring performance at scale and over time.",
  ["Governance, Risk, Security, and Compliance", "Information Management", "Architecture and Portfolio Management"]),
]

# which competency enables which Digital Enablement pillar (the guide's Table 4-1)
ENABLES = [
 ("Architecture and Portfolio Management", "Digital Principles and Strategy"),
 ("Information Management", "Digital Principles and Strategy"),
 ("Conception of Digital Value", "Digital Principles and Strategy"),
 ("Governance, Risk, Security, and Compliance", "Digital Governance"),
 ("Coordination Mechanisms", "Digital Products and Services"),
 ("Investment and Sourcing", "Digital Products and Services"),
 ("Product Management", "Digital Products and Services"),
 ("Organization and Cultural Factors", "Agile Digital Delivery Model"),
 ("Work Execution", "Agile Digital Delivery Model"),
 ("Operations", "Agile Digital Delivery Model"),
 ("Agile Development and Continuous Delivery", "Agile Digital Delivery Model"),
 ("Digital Infrastructure and Related Practices", "Digital Platforms"),
]

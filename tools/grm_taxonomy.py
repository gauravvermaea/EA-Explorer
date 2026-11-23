"""The taxonomy of the TOGAF Series Guide: Government Reference Model (G21D), the source of eax/seed/industry_grm.py:
each sector with its functions, services and drivers for change. Names are the guide's, descriptions EA Explorer's own.
Run tools/build_grm_model.py after changing it."""

# The GRM's taxonomy: sector (Level 1), function (Level 2), service (Level 3), and each sector's drivers for change.
# Names as the guide gives them; every description is written in EA Explorer's own words (the guide's copy is not for
# redistribution).
# (sector, description, [(function, description, [(service, description)])], [(driver, description)])
GRM = [
 ("International Affairs and Trade", "How government supports and trades with other economies, and conducts its foreign policy, aid, treaties and diplomacy.", [
  ("Development and Aid", "Help for developing and less developed economies.", [
   ("International Development", "Support for developing economies through goods and services given freely."),
   ("Humanitarian Aid", "Support for economies recovering from conflict or crisis.")]),
  ("Trade", "Prosperity through trade with other countries.", [
   ("Global Trade", "Growing the economy by making overseas trade and the movement of goods and services easier."),
   ("Export Control", "Regulating goods leaving the country, in line with national and international rules."),
   ("Import Control", "Regulating goods entering the country, in line with national and international rules.")]),
  ("International Affairs", "Relationships with other governments: diplomatic advice, partnerships and agreements.", [
   ("Foreign Affairs", "Diplomatic help and consultation with other governments."),
   ("Foreign Treaties", "Monitoring treaties in force and negotiating new partnerships and agreements.")])],
  [("Powerful Political Forces Setting Agenda", "Shifting political norms, and more regulation and control of aid organisations."),
   ("New Types of Vulnerabilities", "Supply shocks and the pandemic exposed fragile supply chains and may push trade closer to home."),
   ("De-Globalization", "Protectionism and regional self-reliance fragmenting supply chains and trade."),
   ("Technology", "Digital trade, blockchain, digital identity, analytics and collaboration tools changing how aid and treaties are run.")]),
 ("Defense and Security", "The defence of the country and the security of its people, government and allies.", [
  ("Defense Activities", "National defence programmes, including threat reduction and counter-terrorism.", [
   ("Military Operations", "Defence events and activities not covered elsewhere, such as procurement outside the defence force."),
   ("Threat Reduction", "Stopping the spread of goods or sensitive information tied to threats, including cyber operations."),
   ("Counter-Terrorism", "Responses at home and abroad to deter and end acts of terrorism.")]),
  ("Defense Readiness and Preparation", "Keeping the forces ready: equipment, procurement, infrastructure, development and the pay and benefits of personnel.", [
   ("Defense Training and Allocation", "Improving individual and team performance through real and simulated training."),
   ("Defense Application", "Bringing engagement and manoeuvre together to meet defence aims in any environment."),
   ("Defense Network and IT Infrastructure", "The networks and information flows defence needs to connect and work together."),
   ("Population Protection", "Keeping the population, the government and its leaders safe.")]),
  ("Intelligence and International Security", "Protecting and understanding the interests of the government and its allies.", [
   ("International Security Assistance", "Protecting the government's interests and answering threats across shared networks and information."),
   ("Intelligence and Counter-Intelligence Operations", "Analysing and understanding what the government and citizens need to be protected from."),
   ("Special Intelligence", "Specialised collection and analysis of information in the national interest.")])],
  [("Infrastructure Optimization", "Making better use of defence estates, equipment and networks."),
   ("Workforce Transformation", "New skills, roles and ways of working for defence personnel."),
   ("Technology", "New technologies changing how defence and security operate."),
   ("Contemporary Operating Environment", "Threats that are more varied, faster moving and harder to predict.")]),
 ("General Government and Local Services", "The everyday services government gives the public, and the local services of a community.", [
  ("Customer Services", "Help and advice for the people who use government services.", [
   ("Cashiers", "Staff who handle enquiries and general clerical work."),
   ("Tax Forms", "Providing and supporting the forms taxpayers and exempt organisations use to report."),
   ("Front Desk", "Running the people who carry out front-office administration."),
   ("Imports Administrations", "Preparing and answering queries on the documents shipments need to enter the country."),
   ("Planning Applications", "Handling applications for permission to build on or change the use of land."),
   ("Housing Gateway", "Running affordable housing schemes: eligibility and applications."),
   ("Registration Cards", "Managing the paperwork for people claiming asylum."),
   ("Social Security, Benefits, and Pensions", "Queries and paperwork for social security numbers, benefits and pensions."),
   ("Business Licenses", "Applications to start a business."),
   ("Student Finance", "Student loans and grants for the costs of higher education."),
   ("License Applications", "Applications for the authority needed to carry out a regulated role."),
   ("People Hub", "Hiring, running and training customer service and operations staff."),
   ("Workforce Planning", "Comparing today's workforce with the one needed, to close the gaps.")]),
  ("Customer Operations", "The functions that deal with the public directly.", [
   ("Social Security Administration", "Issuing social security numbers and running retirement, survivor and disability programmes."),
   ("Benefits", "Deciding who is eligible for benefits, and paying them."),
   ("Pensions", "Regular payments that support people in retirement."),
   ("Income Support", "Extra money for people on low incomes."),
   ("Benefits Fraud", "Investigating claims by people not entitled to the benefit."),
   ("Customer Complaints", "Looking into and resolving complaints about customer operations."),
   ("Back to Work", "Guidance and support for people returning to work after a break.")]),
  ("Local Service", "Services for a particular place or community.", [
   ("Superintendent Registrar", "Registering local births, marriages and deaths."),
   ("Community Planning and Consultation", "Advice to community groups on budgets, legal matters and local projects."),
   ("Customer Forums", "An online place for a community to come together and give feedback."),
   ("Community Grants", "Grants and loans that fund community projects and services."),
   ("Neighborhood Engagement and Development", "Building local networks, working with businesses on community projects, and activities for residents."),
   ("Local Law", "Legal advice and processes at town and area level.")])],
  [("Manage Changing Expectations and Reputation", "Better, more personal service: customer data, round-the-clock channels and well-trained staff."),
   ("Environment", "Acting on climate change: air quality, waste and recycling, low-emission transport and green infrastructure.")]),
 ("Young People and Education", "Children's services, schooling, and further and higher education and skills.", [
  ("Children's Service", "Social services, safeguarding and support for young people and for parents in the early years.", [
   ("Looked-after Children", "Children in the care of the local authority, by court order or agreement with the parents."),
   ("Fostering and Adoption", "Placing a child with another family for a time or for good."),
   ("Children's Social Care and Safeguarding", "The training, policies and processes that keep children from harm."),
   ("Family and Parenting", "Information and support for parents and carers and for family relationships."),
   ("Early Years", "Learning, development and care before school."),
   ("Children and Adolescent Services", "Support through the stages towards adulthood.")]),
  ("Education", "Teaching children skills and knowledge to national standards.", [
   ("Primary Schools", "Education at elementary level, centred on reading and writing."),
   ("Secondary Schools", "Education in secondary schools."),
   ("Specialist Teaching", "Extra help, adapted programmes, equipment or materials for learners who need them."),
   ("Standards and Achievement", "Course and exam material and exam administration to the education standards, and accrediting qualifications."),
   ("Curriculum", "The required courses and units, kept consistent across schools.")]),
  ("Higher Education and Skills", "Further education and work-related training, with industry and tertiary institutions.", [
   ("Higher Education", "Education after secondary school."),
   ("Early Careers", "Training in the workplace and traineeships."),
   ("Apprenticeships", "Training on the job together with classroom learning.")])],
  [("Innovate Curriculums and Engage with Students at an Individual Level", "Learning shaped around each student."),
   ("Internationalize Education", "Education that reaches and draws on other countries."),
   ("Modernize Classrooms", "New technology and ways of teaching in the classroom."),
   ("Adjust National Curriculums", "National curriculums brought up to date with the skills now needed.")]),
 ("Health and Community Wellbeing", "The physical and mental health of the population and the services that protect it.", [
  ("Hospital and Community Services", "Services that protect adults' physical and mental health.", [
   ("Adult Social Care", "Support for adults with physical or learning difficulties."),
   ("Adult Mental Health", "Psychological, employment and personal support for adults with mental health needs."),
   ("Preventative Health", "Care that prevents illness and disease."),
   ("Psychotherapy", "Therapy for adults with mental and emotional difficulties."),
   ("Counseling", "Talking therapy for adults with mental and emotional difficulties."),
   ("Community Services", "Looking after the wellbeing of a community and watching over its health services."),
   ("Adult Safeguarding", "The training, policies and processes that keep adults from harm."),
   ("Medical Aligned Professions", "Diagnostic, technical, therapeutic and support services by qualified health professionals."),
   ("Hospital Outpatients", "Hospital care without an overnight stay."),
   ("Hospital Inpatients", "Hospital care with at least one overnight stay."),
   ("Facilities Management", "Keeping hospital and community buildings running."),
   ("Emergency Services", "Care before hospital: ambulances, urgent response and treatment outside hospital.")]),
  ("Medical", "The kinds and specialisations of health care.", [
   ("Medical Professional Lead", "Setting the direction for medical practice and its professionals."),
   ("Primary Care Strategy", "The direction and framework for primary care."),
   ("Regulatory Oversight", "Making sure health policy is applied the same way everywhere."),
   ("Information and Strategy Governance", "Aligning medical people, processes, tools and technology to the results wanted."),
   ("Mortality", "Services and information around a death and bereavement."),
   ("Litigation", "Legal disputes involving public medical bodies."),
   ("Pharmacy", "Prescribing, dispensing and distributing medicines.")]),
  ("Nursing", "Care of the sick and infirm.", [
   ("Nursing Strategy and Governance", "Aligning nursing services, processes, tools and technology to the results wanted."),
   ("Nursing Standards and QA", "Checking the standard of patient care and of nurses' skills."),
   ("Health and Community Nursing", "Community care led by district and community nurses and their teams.")])],
  [("Respond to Demographic Changes", "An older, growing and changing population needing different care."),
   ("Innovate", "New models of care and ways of working."),
   ("Incorporate Technology Advancements", "New medical and digital technology in care.")]),
 ("Judiciary, Justice, and Home Affairs", "Protecting the public, upholding the law and delivering justice.", [
  ("Protection and Law Enforcement", "Keeping the public safe and making sure the law is obeyed.", [
   ("Customs", "Checking goods for what is illegal or taxable, and advising on quotas and customs rules."),
   ("Immigration", "Checking that travellers arriving may enter the country, and clearing them on arrival."),
   ("Emergency Planning", "Help in unforeseen events: funding, logistics, and coordinating government and community services."),
   ("Fire Service", "Fighting fires, limiting damage, and fire safety and prevention."),
   ("Health and Safety", "Designing and running health and safety programmes."),
   ("Police Service", "Public safety, advice on the rules, and reducing violence and illegal drug use.")]),
  ("Criminal Justice and Offender Management", "Bringing those who have committed crimes or offences to justice.", [
   ("Youth Offending", "Working with young offenders and community services to stop them reoffending."),
   ("Criminal Justice", "Delivering justice for crimes, including prosecution."),
   ("Prison Monitoring", "Overseeing the places where offenders are held."),
   ("Police Authority", "Coordinating the law enforcement services."),
   ("Law Commission", "Reviewing the law and recommending reform."),
   ("Criminal Compensation", "Paying victims of crime for what the crime cost them."),
   ("Police Complaints", "Handling complaints about the police, to keep the public's confidence.")])],
  [("Prepare for New Threats", "New kinds of crime and threat to be ready for."),
   ("Victim Support", "More and better support for victims of crime."),
   ("Modernize Prison Infrastructure", "Bringing prisons and their systems up to date."),
   ("Leverage New Technologies", "Using new technology in policing and justice.")]),
 ("Financial", "Government revenue, finance strategy, accounting, investments, and risk and audit.", [
  ("Revenue", "Collecting what is owed to the government, at home and from abroad.", [
   ("Tax Office", "Running the tax system and developing and applying tax policy."),
   ("Social Security", "Assistance that protects people's welfare against instability in their lives."),
   ("Import Duty", "Customs collecting taxes on imports and some exports."),
   ("Tax and Revenue Compliance", "Helping people and businesses pay their taxes and levies as required.")]),
  ("Strategic Finance", "Long-term financial strategy for future services, with financial monitoring and control.", [
   ("Policy Support", "Judging whether current programmes and policies can be sustained."),
   ("Corporate and Business Planning", "Planning how to use the organisation's capabilities to reach its goals."),
   ("Strategic Risk", "Understanding exposure to risk and what to do about it."),
   ("Financial Planning", "The government's long-term financial needs: raising and allocating resources and managing costs."),
   ("Investment Decisions", "Deciding where and how much capital to invest.")]),
  ("Accounting and Reporting", "Recording, classifying, summarising and reporting financial transactions.", [
   ("Finance Business Partnering", "Relationships with the businesses, organisations and people who help meet the government's goals."),
   ("Finance Planning and Performance", "Measuring how well the government's financial assets and capital are used."),
   ("Accounting Standards Compliance", "Keeping accounting consistent and its decisions sound.")]),
  ("Investment Management", "Managing financial assets and other investments.", [
   ("Cash Management", "Collecting and managing cash flows."),
   ("Investments", "Assets held to produce income in future."),
   ("Shareholders of Owned Subsidiaries", "Shares held in companies the government owns or controls."),
   ("Pension Fund Management", "Investing and managing pension fund assets.")]),
  ("Risk and Audit", "Examining regulated activities to make sure they meet the standards.", [
   ("Enterprise Risk", "Finding and dealing with events that threaten the strategic goals."),
   ("Financial Governance", "Collecting, monitoring and controlling financial information."),
   ("Internal Audit", "Independent assurance that risk management, governance and internal controls work.")])],
  [("Strategic Shock", "Sudden economic or other shocks the public finances must absorb."),
   ("Fast Technological Change", "Technology changing how money is raised, managed and reported.")]),
 ("Growth, Housing, and Environment", "Economic growth and partnerships, the natural environment, public property and regulation.", [
  ("Partnerships", "Working relationships between functions and with industry.", [
   ("Business and SME Support", "Support for businesses and small and medium enterprises."),
   ("Tourism", "Attracting visitors, supporting the tourism industry and advising on its rules."),
   ("Sport", "Running, maintaining and regulating sports and recreation facilities."),
   ("Culture", "Supporting the arts and cultural bodies such as museums and galleries."),
   ("Rural Economy", "Developing, investing in and regulating the countryside and farming."),
   ("Grants", "Loans that help fund partners."),
   ("Telecommunications", "Supporting telecoms organisations and advising on their rules, standards and new technology."),
   ("Water", "Supporting water industry partnerships and advising on water rules and standards."),
   ("Electricity", "Supporting power industry partnerships and advising on electricity rules and standards."),
   ("Port", "Supporting port partnerships and regulating maritime ports."),
   ("Post", "Collecting and delivering mail, issuing stamps and advising on postal rules.")]),
  ("Natural Environment", "Looking after the environment and wildlife so they last.", [
   ("Environmental Services", "Maintaining, protecting and advising on the natural environment."),
   ("Environmental Ecology", "Restoring habitats, protecting ecosystems and supporting conservation."),
   ("Meteorological Services", "Weather forecasts, climate information and severe weather warnings."),
   ("Veterinary Services", "Advice and research on the health of domestic animals."),
   ("Marine and Fisheries", "Looking after the sea and coast and raising awareness of it.")]),
  ("Property and Special Projects", "Investment and management for development and infrastructure projects.", [
   ("Property", "Developing and managing buildings."),
   ("Surveying", "Valuing, costing, managing and maintaining public property."),
   ("Architects", "Planning, designing and building properties."),
   ("Capital Projects", "Developing and managing long-term investment projects."),
   ("Asset Management", "Managing government assets.")]),
  ("Regulation", "Carrying out regulatory processes.", [
   ("Building Control", "The minimum standards for design and construction."),
   ("Trading Standards", "Enforcing the law that protects consumers."),
   ("Document Verification Service", "Checking government-issued documents, against the law and fraud."),
   ("Environmental Health", "Judging the effect of industry, tourism and community use on the environment."),
   ("Licensing", "Granting, managing and revoking the authority to carry out a regulated task."),
   ("Environmental Protection", "Correcting and offsetting harm to the environment.")])],
  [("Population Growth and Economic Activity", "More people and activity putting pressure on housing, services and land."),
   ("Climate Change", "Adapting to and reducing the effects of a changing climate."),
   ("Digitalization and Technology", "Digital services and technology changing growth, housing and the environment.")]),
 ("Policy, Performance, Population, and Local Innovation", "Public policy, planning and performance, population statistics, and strategy and innovation.", [
  ("Policy", "Developing policy and judging whether programmes can be sustained, across environment, society, economy and markets.", [
   ("Collaborative Policy", "Watching and responding to what the market needs."),
   ("Policy Secretariat", "Coordinating the analysis and drafting behind public policy, and simplifying policy procedures."),
   ("Social Policy", "Guidelines, principles and laws that reduce inequality and protect welfare."),
   ("Environmental Policy", "Guidelines, principles and laws that reduce society's effect on the environment."),
   ("Economic Policy", "Guidelines, principles and laws for economic stability and growth.")]),
  ("Planning and Performance", "Working out, continually, the best way to reach the goals.", [
   ("Capacity Planning", "How much change and output the government can take on to meet its plans."),
   ("Key Performance Indicators", "Measuring outcomes and activities against the strategic goals."),
   ("Population Statistics (and Census)", "Population statistics and the census, and the trends behind research and policy.")]),
  ("Innovation and Strategy", "Plans and initiatives that reach goals and meet unmet needs, using new technology.", [
   ("Social Strategy", "Plans for social goals and reducing inequality."),
   ("Environmental Strategy", "Plans for environmental goals and tackling climate change."),
   ("Economic Strategy", "Plans for economic goals and using resources better."),
   ("Population Strategy", "Plans for population goals and their risks."),
   ("Housing Strategy", "Plans for housing goals: flexible, affordable housing."),
   ("Short, Medium-Term Strategy", "Goals for the year ahead and the near term, and how to reach them."),
   ("Long-Term Strategy", "Strategic goals and the best way to reach them.")])],
  [("Respond to Demographic Changes", "Policy and planning for a changing population."),
   ("Automate and Innovate", "Automation and innovation in how government plans and performs."),
   ("Adopt New Economic Metrics", "Measuring progress beyond the traditional economic figures.")]),
 ("Shared Services", "The support services shared across government: people, communications, commercial, transformation and finance.", [
  ("People and Corporate Services", "People and organisation-wide support services, brought together.", [
   ("People and Organizational Change", "Changing the organisation's strategy, processes, culture and technology."),
   ("Culture and Modernization", "Modernising people services and the working culture."),
   ("Human Resources", "Managing employees: hiring, training and communication."),
   ("Business Administration Support", "Overseeing the running of business operations."),
   ("Business Continuity", "Keeping operations going in the face of threats."),
   ("Compliance", "Monitoring that people guidelines and regulations are followed."),
   ("Employee Health and Safety", "Designing and running employee health and safety programmes."),
   ("Soft Facilities Management", "Services that make the workplace more comfortable.")]),
  ("Communications", "Information, regulation and media services in support of communication.", [
   ("External Media", "Information between the government and the outside world."),
   ("Internal Communications", "The industries that carry information to citizens at home, and their regulation."),
   ("Marketing", "Marketing content and how it is presented, in any medium."),
   ("Web Design", "Designing interactive web content."),
   ("International Communications", "The industries that carry information abroad, and their regulation.")]),
  ("Commercial Services", "Sourcing, managing and procuring contracts with suppliers, partners and third parties.", [
   ("Market Engagement", "Talking to suppliers before procurement."),
   ("Market Creation", "Removing barriers and setting property rights so a market can form."),
   ("Commercial Negotiations", "Running strategic negotiations for new opportunities."),
   ("Contract Management", "Drawing up, carrying out and reviewing contracts with partners and suppliers."),
   ("Procurement", "Weighing risk and options, awarding contracts and managing them.")]),
  ("Transformation", "Reassessing a function from the ground up and changing it.", [
   ("Business Processes", "Monitoring and improving business processes and activities."),
   ("IT Operations", "The processes and services the IT department runs."),
   ("Information Management", "Collecting and moving data and information."),
   ("Information Security", "Protecting information and systems from unauthorised access, use, change or destruction."),
   ("Digital Government", "Using information and technology to offer services digitally."),
   ("Enterprise Architecture", "Defining the current, transition and target state of processes, people and technology."),
   ("Data Protection", "Protecting personal data and handling it as the law requires."),
   ("Portfolio and Performance Management", "Running government investments and assets well.")]),
  ("Finance Hub", "A financial centre where many financial services institutions are based.", [
   ("Standardized Processes", "Agreed, proven procedures for reliable practice."),
   ("Analytics", "Analysis of data of every kind, from very large data sets to rare events."),
   ("Reporting", "Financial information, reports and analysis of transactions."),
   ("Transactional Services", "Overseeing transactions such as mergers and acquisitions."),
   ("Debt Management", "A strategy for managing debt to its risk and cost targets."),
   ("Pension Fund Administration (PFA)", "Retirement savings accounts, paying retirement benefits and accounting for pension funds."),
   ("Payroll", "Paying employees for each pay period.")])],
  [("People Reform", "Changing how the public service employs, develops and organises people."),
   ("Digitalization", "Moving shared services onto digital channels."),
   ("Enhance Technology Capabilities", "New technology to make shared services better and cheaper.")]),
 ("Transport and Operations", "Moving people and goods safely, and looking after public property, streets and spaces.", [
  ("Transport", "The safe movement of people and goods by land, air, sea and space.", [
   ("Ground Transport", "Moving people and goods safely over land."),
   ("Air Transport", "Moving people and goods safely by air."),
   ("Water Transport", "Moving people and goods safely over water."),
   ("Space Transport", "Moving people and goods safely in space."),
   ("Other Transport", "Moving people and goods by any other means.")]),
  ("Operations", "Looking after waste, public property, green spaces, parking and streets.", [
   ("Waste Management", "Collecting, moving, recycling and disposing of waste."),
   ("Property Maintenance", "Keeping government buildings secure and in good repair."),
   ("Car Parks", "Keeping public car parks secure and in good repair."),
   ("Street Maintenance and Highways", "Repairing and maintaining roads, footways and highways."),
   ("Parks and Trees", "Planting, maintaining and conserving trees and green spaces in parks.")])],
  [("Public Opinion", "What the public expects of transport and public spaces."),
   ("Policy", "Transport policy changing what is built and how it is run."),
   ("Smart Mobility", "Connected, shared and data-driven transport.")]),
]

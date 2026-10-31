// ---------------------------------------------------------------------------
// Persona Forge — product mock data
// Two fully-built tenants so switching between them in the org switcher
// actually shows different data. Everything here is fictional, hand-written
// sample content — edit freely. Fields are annotated with the PRD/Roadmap/
// Concept doc section they trace back to, where relevant.
// ---------------------------------------------------------------------------

// Shared across tenants — not tenant-specific data, but shared catalogs.
// Concept & Monetization §2.1/2.2: add-ons available on top of any tier.
const ADDONS = [
  {
    name: "AI Backend Build-Out",
    price: "From $15,000, one-time",
    description: "We provision and validate a dedicated backend for this tenant — model class, hardware, and data/tool integrations.",
  },
  {
    name: "Additional Persona Pack",
    price: "$400/mo per persona",
    description: "License another active persona on this tenant, beyond the one included in the base plan.",
  },
  {
    name: "Premium Model Swap-In",
    price: "Custom pricing",
    description: "Swap this tenant's backend to a frontier-scale open-weight model (e.g. Kimi K2-class) for higher-stakes workloads.",
  },
  {
    name: "On-Prem Deployment",
    price: "Custom pricing",
    description: "Deploy inside your own infrastructure for confidentiality or regulatory requirements that preclude shared-cloud hosting.",
  },
];

// PRD §3.6: "standard auth with MFA at MVP, SSO/SAML planned for enterprise phase."
const AUTH_METHODS = [
  { name: "Username & password with MFA", status: "active", note: "Enforced for all users on this tenant." },
  { name: "SSO / SAML (OIDC / SAML2)", status: "locked", note: "Enterprise phase — Phase 2/3." },
];

const TENANTS = {

  // ========================================================================
  // NORTHBRIDGE CAPITAL — mid-market buyout fund, larger seat count
  // ========================================================================
  northbridge: {
    id: "northbridge",
    name: "Northbridge Capital",
    initials: "NC",
    currentUser: { name: "Priya Shah", email: "priya@northbridgecap.com", initials: "PS" },

    billing: {
      plan: "Growth",
      priceLabel: "$2,400/mo base",
      tokensUsed: 2840000,
      tokensIncluded: 4000000,
      overageRate: "$4.00 per 100K tokens over allowance",
      nextInvoiceDate: "Oct 1, 2026",
      invoices: [
        { date: "Sep 1, 2026", amount: "$2,400.00", status: "Paid" },
        { date: "Aug 1, 2026", amount: "$2,610.00", status: "Paid" },
        { date: "Jul 1, 2026", amount: "$2,400.00", status: "Paid" },
      ],
    },

    usage: {
      activeUsers: 12,
      licensedSeats: 15,
      conformanceRate: 98.6,
    },

    usageByWeek: [38, 52, 61, 74, 69, 83, 91, 76],

    // PRD §3.5: "per-agent activity" as part of the usage dashboard.
    agentUsage: [
      { agent: "Diligence Q&A", conversations: 142, tokens: 1650000 },
      { agent: "Deal Screening Analyst", conversations: 38, tokens: 780000 },
      { agent: "Diligence Memo Drafting", conversations: 21, tokens: 410000 },
    ],

    notifications: [
      { title: "Persona v3 activated", detail: "Escalation rule updated by Priya Shah", time: "2h ago", unread: true },
      { title: "3 items in review queue", detail: "Awaiting a decision", time: "5h ago", unread: true },
      { title: "Monthly invoice paid", detail: "$2,400.00 — Sept cycle", time: "3d ago", unread: false },
    ],

    persona: {
      name: "Diligence Analyst",
      version: "v3",
      updatedBy: "Priya Shah",
      updatedAt: "Sept 12, 2026",
      validated: true,
      tone: "Precise, neutral, and sourced. States uncertainty plainly rather than rounding up to confidence. Never editorializes on deal quality.",
      scope: "Deal screening, data-room Q&A, and diligence-memo drafting for the active deal list. Answers only from documents attached to the current deal room.",
      forbiddenTopics: [
        "Investment recommendations or go/no-go opinions",
        "Any figure not sourced from an attached document",
        "Comparisons to other active or historical deals by name",
      ],
      escalation: "If a question falls outside the current deal room, or asks for a judgment call rather than a fact, the agent declines and routes the question to a human analyst rather than guessing.",
      // PRD §3.1: persona spec includes "example transcripts."
      exampleTranscript: [
        { who: "user", text: "What's our exposure if the largest customer churns?" },
        { who: "agent", text: "Per Exhibit C, that customer is 18% of FY25 revenue. I don't have a churn-impact model attached to this deal room, so I can't project the effect — flagging this as a good question for the memo." },
      ],
      priorVersions: [
        { version: "v2", updatedAt: "Aug 3, 2026", note: "Added explicit escalation rule for out-of-room questions." },
        { version: "v1", updatedAt: "Jul 18, 2026", note: "Initial spec for the design-partner pilot." },
      ],
    },

    agents: [
      {
        id: "deal-screening",
        name: "Deal Screening Analyst",
        description: "Runs a first pass on an incoming deal against your investment thesis and flags anything out of scope before an analyst sees it.",
        inputs: "Deal memo, thesis document",
        expectedOutput: "A pass/flag verdict per thesis criterion, with the source line for each.",
        connectors: "Data room",
      },
      {
        id: "diligence-qa",
        name: "Diligence Q&A",
        description: "Answers questions against the current deal room only — contracts, financials, cap table — with a citation back to the source document.",
        inputs: "Data room documents",
        expectedOutput: "A sourced answer with a document/page citation, or a decline if unsourced.",
        connectors: "Data room, document store",
      },
      {
        id: "memo-drafting",
        name: "Diligence Memo Drafting",
        description: "Assembles a first-draft diligence memo section from verified Q&A history, ready for an analyst to revise.",
        inputs: "Q&A history, memo template",
        expectedOutput: "A drafted memo section citing only verified Q&A entries.",
        connectors: "Document store",
      },
    ],

    reviewQueue: [
      { id: "rq-1", agent: "Diligence Q&A", category: "Out of scope", severity: "Medium", status: "Open", snippet: "Asked to compare this deal's valuation to a prior portfolio company by name.", time: "Today, 9:14 AM" },
      { id: "rq-2", agent: "Deal Screening Analyst", category: "Low confidence", severity: "Low", status: "Open", snippet: "Cited a revenue figure with no matching source line in the attached memo.", time: "Today, 8:02 AM" },
      { id: "rq-3", agent: "Diligence Q&A", category: "Opinion requested", severity: "Low", status: "Open", snippet: "User asked whether the company was 'a good investment.'", time: "Yesterday, 4:41 PM" },
      { id: "rq-4", agent: "Diligence Q&A", category: "Out of scope", severity: "Low", status: "Resolved", snippet: "Asked about a customer contract not yet uploaded to the data room.", time: "Sept 15, 2:10 PM" },
      { id: "rq-5", agent: "Deal Screening Analyst", category: "Low confidence", severity: "Medium", status: "Resolved", snippet: "Flagged a churn-rate figure calculated from two mismatched reporting periods.", time: "Sept 11, 11:36 AM" },
    ],

    auditLog: [
      { id: "a-1042", agent: "Diligence Q&A", personaVersion: "v3", outcome: "Verified", time: "Today, 10:02 AM", snippet: "Confirmed the customer concentration figure from Exhibit C." },
      { id: "a-1041", agent: "Diligence Q&A", personaVersion: "v3", outcome: "Flagged", time: "Today, 9:14 AM", snippet: "Declined a valuation comparison outside the current deal room." },
      { id: "a-1040", agent: "Deal Screening Analyst", personaVersion: "v3", outcome: "Flagged", time: "Today, 8:02 AM", snippet: "Revenue figure could not be traced to a source line." },
      { id: "a-1039", agent: "Deal Screening Analyst", personaVersion: "v3", outcome: "Verified", time: "Today, 7:51 AM", snippet: "Flagged customer contract for missing termination clause, correctly scoped." },
      { id: "a-1038", agent: "Diligence Q&A", personaVersion: "v3", outcome: "Verified", time: "Yesterday, 5:20 PM", snippet: "Answered cap table question with citation to Schedule 3.2." },
      { id: "a-1037", agent: "Diligence Q&A", personaVersion: "v3", outcome: "Flagged", time: "Yesterday, 4:41 PM", snippet: "Declined an investment-opinion question, routed to analyst." },
      { id: "a-1036", agent: "Diligence Memo Drafting", personaVersion: "v3", outcome: "Verified", time: "Yesterday, 2:05 PM", snippet: "Drafted the working-capital section from verified Q&A history." },
      { id: "a-1035", agent: "Deal Screening Analyst", personaVersion: "v3", outcome: "Verified", time: "Sept 18, 4:47 PM", snippet: "Screened incoming SaaS deal memo against thesis — flagged for review." },
      { id: "a-1034", agent: "Diligence Q&A", personaVersion: "v3", outcome: "Verified", time: "Sept 18, 3:12 PM", snippet: "Cited employee count from Exhibit A, page 2." },
      { id: "a-1033", agent: "Diligence Q&A", personaVersion: "v3", outcome: "Verified", time: "Sept 18, 11:40 AM", snippet: "Answered a question on the vendor concentration schedule." },
      { id: "a-1032", agent: "Diligence Q&A", personaVersion: "v3", outcome: "Flagged", time: "Sept 17, 4:12 PM", snippet: "Asked about a document not yet present in the data room." },
      { id: "a-1031", agent: "Deal Screening Analyst", personaVersion: "v2", outcome: "Verified", time: "Sept 16, 9:30 AM", snippet: "Screened a manufacturing add-on against sector thesis criteria." },
      { id: "a-1030", agent: "Diligence Memo Drafting", personaVersion: "v2", outcome: "Verified", time: "Sept 15, 3:55 PM", snippet: "Drafted the customer-concentration section for the memo." },
      { id: "a-1029", agent: "Diligence Q&A", personaVersion: "v2", outcome: "Flagged", time: "Sept 15, 2:10 PM", snippet: "Asked about a contract not yet uploaded to the data room." },
      { id: "a-1028", agent: "Diligence Q&A", personaVersion: "v2", outcome: "Verified", time: "Sept 14, 1:18 PM", snippet: "Confirmed EBITDA adjustment schedule from Exhibit D." },
      { id: "a-1027", agent: "Deal Screening Analyst", personaVersion: "v2", outcome: "Flagged", time: "Sept 11, 11:36 AM", snippet: "Churn-rate figure calculated from mismatched reporting periods." },
      { id: "a-1026", agent: "Diligence Q&A", personaVersion: "v2", outcome: "Verified", time: "Sept 10, 10:02 AM", snippet: "Answered a question on the equity cap table waterfall." },
      { id: "a-1025", agent: "Diligence Q&A", personaVersion: "v2", outcome: "Verified", time: "Sept 9, 4:20 PM", snippet: "Cited the lease-obligation schedule from Exhibit F." },
    ],

    // PRD §3.6: admin actions logged separately from the conversation-level audit trail.
    adminActivityLog: [
      { actor: "Priya Shah", action: "Activated persona v3", detail: "Added escalation rule for out-of-room questions", time: "Sept 12, 2026, 4:02 PM" },
      { actor: "Priya Shah", action: "Invited user", detail: "Ana Torres as Standard User", time: "Sept 9, 2026, 11:20 AM" },
      { actor: "James Okafor", action: "Changed role", detail: "Marcus Webb: Standard User → Tenant Admin reverted same day", time: "Sept 6, 2026, 3:41 PM" },
      { actor: "Priya Shah", action: "Activated agent", detail: "Diligence Memo Drafting", time: "Aug 28, 2026, 9:15 AM" },
      { actor: "Priya Shah", action: "Activated persona v2", detail: "Added explicit escalation rule", time: "Aug 3, 2026, 1:30 PM" },
      { actor: "James Okafor", action: "Invited user", detail: "Sarah Lindqvist as Standard User", time: "Jul 30, 2026, 10:05 AM" },
      { actor: "Priya Shah", action: "Activated persona v1", detail: "Initial spec for the design-partner pilot", time: "Jul 18, 2026, 2:00 PM" },
    ],

    users: [
      { name: "Priya Shah", email: "priya@northbridgecap.com", role: "Tenant Admin", lastActive: "Just now" },
      { name: "Daniel Cho", email: "daniel@northbridgecap.com", role: "Standard User", lastActive: "1h ago" },
      { name: "Maya Fernandez", email: "maya@northbridgecap.com", role: "Standard User", lastActive: "3h ago" },
      { name: "Owen Blake", email: "owen@northbridgecap.com", role: "Standard User", lastActive: "Yesterday" },
      { name: "Sarah Lindqvist", email: "sarah@northbridgecap.com", role: "Standard User", lastActive: "Yesterday" },
      { name: "Marcus Webb", email: "marcus@northbridgecap.com", role: "Standard User", lastActive: "2d ago" },
      { name: "Ana Torres", email: "ana@northbridgecap.com", role: "Standard User", lastActive: "4d ago" },
      { name: "James Okafor", email: "james@northbridgecap.com", role: "Tenant Admin", lastActive: "5d ago" },
    ],

    conversations: [
      { id: "c-1", title: "Customer concentration — Exhibit C", agent: "Diligence Q&A", time: "Today, 10:02 AM" },
      { id: "c-2", title: "SaaS deal thesis screen", agent: "Deal Screening Analyst", time: "Sept 18, 4:47 PM" },
      { id: "c-3", title: "Working-capital memo section", agent: "Diligence Memo Drafting", time: "Sept 17, 2:05 PM" },
      { id: "c-4", title: "Vendor concentration schedule", agent: "Diligence Q&A", time: "Sept 16, 11:40 AM" },
    ],

    chatScript: [
      { keywords: ["customer", "concentration"], reply: "Customer concentration: the top customer accounts for 18% of FY25 revenue, per Exhibit C, page 4. No single customer exceeds 25%, which is within the range noted in the investment thesis.", verified: true },
      { keywords: ["compare", "portfolio", "other deal", "previous deal"], reply: "I can't compare this to other deals by name — that's outside what I'm scoped to answer from this data room. I've routed the question to an analyst.", verified: false, flagReason: "Out of scope — cross-deal comparison" },
      { keywords: ["good investment", "should we invest", "worth it", "recommend"], reply: "I don't offer an investment recommendation — that's a judgment call outside my scope. I've flagged this for an analyst to weigh in.", verified: false, flagReason: "Opinion requested" },
      { keywords: ["termination", "contract"], reply: "The primary customer contract (Schedule 4.1) includes a 90-day termination-for-convenience clause with no penalty. Flagging this for review since it's a common negotiation point.", verified: true },
    ],
    chatDefaultReply: {
      reply: "I don't have a source for that in the current data room, so I won't guess. Want me to note it as an open question for the team?",
      verified: true,
    },
  },

  // ========================================================================
  // ASHFORD PARTNERS — smaller growth-equity fund, add-on acquisitions focus
  // ========================================================================
  ashford: {
    id: "ashford",
    name: "Ashford Partners",
    initials: "AP",
    currentUser: { name: "Priya Shah", email: "priya@ashfordpartners.com", initials: "PS" },

    billing: {
      plan: "Starter",
      priceLabel: "$900/mo base",
      tokensUsed: 1380000,
      tokensIncluded: 1500000,
      overageRate: "$5.50 per 100K tokens over allowance",
      nextInvoiceDate: "Oct 1, 2026",
      invoices: [
        { date: "Sep 1, 2026", amount: "$900.00", status: "Paid" },
        { date: "Aug 1, 2026", amount: "$1,073.50", status: "Paid" },
        { date: "Jul 1, 2026", amount: "$900.00", status: "Paid" },
      ],
    },

    usage: {
      activeUsers: 5,
      licensedSeats: 6,
      conformanceRate: 99.1,
    },

    usageByWeek: [61, 58, 70, 82, 88, 94, 90, 97],

    agentUsage: [
      { agent: "Vendor Diligence Q&A", conversations: 64, tokens: 810000 },
      { agent: "Add-On Screening", conversations: 22, tokens: 410000 },
      { agent: "Synergy Memo Drafting", conversations: 9, tokens: 160000 },
    ],

    notifications: [
      { title: "Approaching token allowance", detail: "92% of monthly allowance used", time: "1h ago", unread: true },
      { title: "New user invited", detail: "Ravi Malhotra added as Standard User", time: "1d ago", unread: false },
    ],

    persona: {
      name: "Add-On Diligence Analyst",
      version: "v2",
      updatedBy: "Ravi Malhotra",
      updatedAt: "Sept 5, 2026",
      validated: true,
      tone: "Concise and operator-facing. Written for portfolio-company teams as much as deal staff — plain language, minimal jargon, always cites its source.",
      scope: "Vendor and add-on target diligence for portfolio companies actively pursuing bolt-on acquisitions. Answers only from the active add-on's data room and the parent portfolio company's reference documents.",
      forbiddenTopics: [
        "Valuation opinions or purchase-price recommendations",
        "Synergy estimates not derived from an attached model",
        "Any reference to deals outside the current portfolio company's active pipeline",
      ],
      escalation: "Questions that require comparing the target against the parent company's confidential financials are routed to the deal lead rather than answered directly, to keep that comparison human-reviewed.",
      exampleTranscript: [
        { who: "user", text: "How does the target's pricing compare to us?" },
        { who: "agent", text: "That needs a direct comparison against our own confidential financials, so I've routed it to the deal lead rather than answering it myself." },
      ],
      priorVersions: [
        { version: "v1", updatedAt: "Jul 22, 2026", note: "Initial spec for the design-partner pilot." },
      ],
    },

    agents: [
      {
        id: "addon-screening",
        name: "Add-On Screening",
        description: "Screens an inbound add-on target against the parent portfolio company's acquisition criteria before it reaches the deal team.",
        inputs: "Target teaser, acquisition criteria",
        expectedOutput: "A criterion-by-criterion pass/flag verdict with source references.",
        connectors: "Data room",
      },
      {
        id: "vendor-qa",
        name: "Vendor Diligence Q&A",
        description: "Answers questions about a target's vendor and customer contracts, sourced only from the current data room.",
        inputs: "Data room documents",
        expectedOutput: "A sourced answer with a document reference, or a decline if unsourced.",
        connectors: "Data room",
      },
      {
        id: "synergy-memo",
        name: "Synergy Memo Drafting",
        description: "Drafts the operational-synergy section of an add-on memo from the attached integration model — never invents a synergy figure.",
        inputs: "Integration model, Q&A history",
        expectedOutput: "A drafted synergy section citing only figures present in the integration model.",
        connectors: "Document store",
      },
    ],

    reviewQueue: [
      { id: "rq-a1", agent: "Vendor Diligence Q&A", category: "Confidential comparison", severity: "Medium", status: "Open", snippet: "Asked to compare target's margins directly against the parent company's own margins.", time: "Today, 11:20 AM" },
      { id: "rq-a2", agent: "Add-On Screening", category: "Low confidence", severity: "Low", status: "Resolved", snippet: "Flagged an ambiguous EBITDA multiple with two possible source readings.", time: "Sept 14, 3:02 PM" },
    ],

    auditLog: [
      { id: "b-2014", agent: "Vendor Diligence Q&A", personaVersion: "v2", outcome: "Flagged", time: "Today, 11:20 AM", snippet: "Declined a direct margin comparison against the parent company." },
      { id: "b-2013", agent: "Add-On Screening", personaVersion: "v2", outcome: "Verified", time: "Today, 9:45 AM", snippet: "Screened an HVAC services target against the acquisition checklist." },
      { id: "b-2012", agent: "Vendor Diligence Q&A", personaVersion: "v2", outcome: "Verified", time: "Yesterday, 2:31 PM", snippet: "Confirmed the target's top-3 vendor concentration from the contracts folder." },
      { id: "b-2011", agent: "Synergy Memo Drafting", personaVersion: "v2", outcome: "Verified", time: "Sept 18, 5:10 PM", snippet: "Drafted the headcount-overlap section from the integration model." },
      { id: "b-2010", agent: "Add-On Screening", personaVersion: "v2", outcome: "Verified", time: "Sept 17, 10:02 AM", snippet: "Screened a logistics add-on target, passed all criteria." },
      { id: "b-2009", agent: "Vendor Diligence Q&A", personaVersion: "v1", outcome: "Flagged", time: "Sept 14, 3:02 PM", snippet: "Ambiguous EBITDA multiple with two possible source readings." },
      { id: "b-2008", agent: "Vendor Diligence Q&A", personaVersion: "v1", outcome: "Verified", time: "Sept 12, 1:47 PM", snippet: "Cited the customer contract renewal terms from the data room." },
      { id: "b-2007", agent: "Add-On Screening", personaVersion: "v1", outcome: "Verified", time: "Sept 9, 4:30 PM", snippet: "Screened a facilities-management target, flagged one criterion for review." },
    ],

    adminActivityLog: [
      { actor: "Ravi Malhotra", action: "Invited user", detail: "Grace Kim as Standard User", time: "Sept 19, 2026, 9:00 AM" },
      { actor: "Ravi Malhotra", action: "Activated persona v2", detail: "Refined scope to the active portfolio company's pipeline only", time: "Sept 5, 2026, 10:15 AM" },
      { actor: "Priya Shah", action: "Invited user", detail: "Tom Reilly as Standard User", time: "Aug 22, 2026, 2:40 PM" },
      { actor: "Ravi Malhotra", action: "Activated agent", detail: "Synergy Memo Drafting", time: "Aug 10, 2026, 11:00 AM" },
      { actor: "Ravi Malhotra", action: "Activated persona v1", detail: "Initial spec for the design-partner pilot", time: "Jul 22, 2026, 3:30 PM" },
    ],

    users: [
      { name: "Ravi Malhotra", email: "ravi@ashfordpartners.com", role: "Tenant Admin", lastActive: "20m ago" },
      { name: "Priya Shah", email: "priya@ashfordpartners.com", role: "Tenant Admin", lastActive: "1h ago" },
      { name: "Lena Okonkwo", email: "lena@ashfordpartners.com", role: "Standard User", lastActive: "Yesterday" },
      { name: "Tom Reilly", email: "tom@ashfordpartners.com", role: "Standard User", lastActive: "2d ago" },
      { name: "Grace Kim", email: "grace@ashfordpartners.com", role: "Standard User", lastActive: "3d ago" },
    ],

    conversations: [
      { id: "d-1", title: "Margin comparison — declined", agent: "Vendor Diligence Q&A", time: "Today, 11:20 AM" },
      { id: "d-2", title: "HVAC target screen", agent: "Add-On Screening", time: "Today, 9:45 AM" },
      { id: "d-3", title: "Headcount overlap section", agent: "Synergy Memo Drafting", time: "Sept 18, 5:10 PM" },
    ],

    chatScript: [
      { keywords: ["margin", "compare", "parent"], reply: "I can't compare the target's margins directly against the parent company's own financials — that comparison needs a human review. I've routed it to the deal lead.", verified: false, flagReason: "Confidential comparison" },
      { keywords: ["vendor", "concentration"], reply: "The target's top 3 vendors account for 61% of cost of goods sold, per the contracts folder, Tab 2. No single vendor exceeds 30%.", verified: true },
      { keywords: ["synergy", "headcount"], reply: "Headcount overlap: 14 roles across finance and back-office are flagged as overlapping in the integration model, Tab 4. I haven't estimated a cost synergy — that figure isn't in the model yet.", verified: true },
      { keywords: ["good acquisition", "should we buy", "recommend", "worth it"], reply: "I don't offer an acquisition recommendation — that's a call for the deal team. I've flagged this for review.", verified: false, flagReason: "Opinion requested" },
    ],
    chatDefaultReply: {
      reply: "That's not sourced in the current data room, so I won't guess. Want me to log it as an open question for the deal team?",
      verified: true,
    },
  },
};

let currentTenantId = "northbridge";

function getTenant() {
  return TENANTS[currentTenantId];
}

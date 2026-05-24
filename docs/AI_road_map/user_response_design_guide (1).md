# Cenaris NDIS Compliance - User Response Design Guide

## 📋 Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Response Architecture Overview](#response-architecture-overview)
3. [Tier-by-Tier Breakdown](#tier-by-tier-breakdown)
4. [Visual Design Specifications](#visual-design-specifications)
5. [Content Writing Guidelines](#content-writing-guidelines)
6. [API Response Structure](#api-response-structure)
7. [Implementation Examples](#implementation-examples)
8. [Mobile vs Desktop Layouts](#mobile-vs-desktop-layouts)

---

## Design Philosophy

### Core Principle: "Status → Why → What to Do"

Every user needs to answer three questions when they see their assessment results:

1. **"How did I do?"** → Overall status with confidence score
2. **"Why this score?"** → Transparent breakdown of scoring components
3. **"What should I do?"** → Actionable, prioritized improvement steps

### Key Design Principles

- ✅ **Actionable over Diagnostic** - Always tell users HOW to fix, not just WHAT is wrong
- ✅ **Progressive Disclosure** - Show most important info first, details on demand
- ✅ **Plain Language** - No jargon; write for non-technical NDIS workers
- ✅ **Visual Hierarchy** - Color coding and typography guide the eye
- ✅ **Trust Building** - Show evidence and reasoning, not black box AI
- ✅ **Quantified Impact** - Show potential score gains for each action

---

## Response Architecture Overview

### Information Hierarchy (Top to Bottom)

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  TIER 1: HERO SECTION (Always Visible)                     │
│  ├─ Document name                                           │
│  ├─ Overall status badge (Critical/High Risk/OK/Mature)     │
│  ├─ Confidence percentage                                   │
│  ├─ One-sentence summary                                    │
│  └─ Priority #1 action                                      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TIER 2: SCORE BREAKDOWN (Expandable)                      │
│  ├─ 5 component scores with progress bars                   │
│  ├─ Points earned vs possible for each                      │
│  └─ Quick fix suggestions per component                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TIER 3: PRIORITY ACTIONS (Expandable)                     │
│  ├─ Ranked action cards (Critical → High → Medium)          │
│  ├─ Each card: What + Impact + How to Fix + Score Gain      │
│  └─ Examples and specific guidance                          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TIER 4: NDIS CITATIONS (Expandable)                       │
│  ├─ Matched standards with relevance scores                 │
│  ├─ Gap analysis (what standard says vs what doc shows)     │
│  ├─ Missing standards list                                  │
│  └─ Links to view full standards                            │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TIER 5: DOCUMENT EVIDENCE (Expandable)                    │
│  ├─ Snippets found in user's document                       │
│  ├─ Highlighted terms and matched phrases                   │
│  ├─ What was expected but not found                         │
│  └─ Possible quality issues                                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TIER 6: WARNINGS & FLAGS (Always Visible if Present)      │
│  ├─ Extraction warnings (scanned PDF, low quality)          │
│  ├─ Scoring warnings (template detected, irrelevant style)  │
│  └─ Recommendations for re-upload                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Responsive Behavior

**Desktop (>1024px):**
- Hero section: Full width
- Tiers 2-5: Collapsible cards in 2-column layout where appropriate
- Warnings: Sticky banner at bottom

**Tablet (768-1024px):**
- Single column layout
- Cards collapse by default, expand on tap
- Warnings: Inline banners

**Mobile (<768px):**
- Vertical stack
- Hero section: Condensed (smaller fonts, icon-based status)
- All tiers collapsed by default
- Swipe-to-expand interaction

---

## Tier-by-Tier Breakdown

### TIER 1: Hero Section

**Purpose:** Immediate understanding at a glance

**Components:**

```
┌─────────────────────────────────────────────────────────────┐
│  📄 Document: 2280354_A3.pdf                     [Download] │
│                                                             │
│  🔴 CRITICAL GAP                                            │
│                                                             │
│  Confidence: 25%                                            │
│  Coverage: 0% | Evidence: 56%                               │
│                                                             │
│  This document needs significant work before it can         │
│  demonstrate NDIS compliance.                               │
│                                                             │
│  ⚡ Priority: Fix blank template sections first             │
│     Potential score gain: +35 points                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Visual Specifications:**

- **Background Color:** Matches status
  - 🔴 Critical: `#FEE2E2` (light red)
  - 🟠 High Risk: `#FED7AA` (light orange)
  - 🟡 OK: `#FEF3C7` (light yellow)
  - 🟢 Mature: `#D1FAE5` (light green)

- **Status Badge:**
  - Font: Bold, 18px
  - Padding: 8px 16px
  - Border-radius: 6px
  - Icon: Matching emoji or SVG

- **Confidence Score:**
  - Font: Bold, 32px
  - Color: Matches status severity
  - Secondary metrics (Coverage, Evidence): 14px, gray

- **Summary Text:**
  - Font: Regular, 16px
  - Max 2 lines
  - Plain language, no jargon

- **Priority Action:**
  - Lightning bolt icon (⚡)
  - Bold text
  - Shows #1 action + potential gain
  - Click to jump to detailed action card

**Content Templates by Status:**

**Critical Gap (<30%):**
```
This document needs significant work before it can demonstrate 
NDIS compliance.
```

**High Risk Gap (30-54%):**
```
This document has identified gaps that require attention to meet 
NDIS compliance standards.
```

**OK (55-74%):**
```
This document shows evidence of NDIS compliance but could be 
strengthened with additional detail.
```

**Mature (75%+):**
```
This document demonstrates strong NDIS compliance with robust 
evidence and clear procedures.
```

---

### TIER 2: Score Breakdown

**Purpose:** Show WHY the score is what it is

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  📊 Why This Score                              [Collapse ▲]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Your document was assessed across 5 dimensions:            │
│                                                             │
│  🔴 Coverage: 12%                                           │
│  ██░░░░░░░░░░░░░░░░░░  3 of 25 points                      │
│                                                             │
│  What this measures: Presence of NDIS terminology and       │
│  requirement terms across all practice standard areas       │
│                                                             │
│  Your result: Missing 88% of required NDIS terms            │
│                                                             │
│  Quick fix: Add sections addressing participant consent,    │
│  safeguarding, restrictive practice, and incident           │
│  management                                                 │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🔴 Depth: 10%                                              │
│  ██░░░░░░░░░░░░░░░░░░  2 of 20 points                      │
│                                                             │
│  What this measures: Document length and level of detail    │
│  in procedures and processes                                │
│                                                             │
│  Your result: Document is only 142 characters (need 800+)   │
│                                                             │
│  Quick fix: Expand each section with:                       │
│  • Step-by-step instructions                                │
│  • Responsible roles and timeframes                         │
│  • Record-keeping requirements                              │
│  • Monitoring and review processes                          │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🟡 Substance: 45%                                          │
│  █████████░░░░░░░░░░  18 of 40 points                      │
│                                                             │
│  What this measures: Presence of action-oriented language,  │
│  responsibilities, compliance processes, and timeframes     │
│                                                             │
│  Your result: Some action indicators found, but lacks       │
│  comprehensive procedural detail                            │
│                                                             │
│  Quick fix: Use must/shall/will language, assign clear      │
│  responsibilities, and specify timeframes                   │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🟡 Structure: 60%                                          │
│  ████████████░░░░░░░░  6 of 10 points                      │
│                                                             │
│  What this measures: Document organization with headings,   │
│  lists, and procedural structure                            │
│                                                             │
│  Your result: Numbered lists detected, but template         │
│  penalty applied due to unfilled sections                   │
│                                                             │
│  Quick fix: Complete all placeholder sections and remove    │
│  blank form fields                                          │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🔴 Evidence Quality: 0%                                    │
│  ░░░░░░░░░░░░░░░░░░░░  0 of 5 points                       │
│                                                             │
│  What this measures: Strength of specific, contextual       │
│  evidence that demonstrates compliance                      │
│                                                             │
│  Your result: No strong evidence snippets found in document │
│                                                             │
│  Quick fix: Include specific examples, completed risk       │
│  assessments, and documented procedures                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Visual Specifications:**

- **Progress Bars:**
  - Width: 100% of container
  - Height: 24px
  - Border-radius: 4px
  - Background: Light gray `#F3F4F6`
  - Fill color: Matches dimension status
  - Animated on load (0 → final value over 0.5s)

- **Dimension Labels:**
  - Icon + Name: Bold, 16px
  - Percentage: Bold, 24px, colored
  - Points: Regular, 14px, gray

- **Description Text:**
  - "What this measures": Italic, 14px, `#6B7280`
  - "Your result": Regular, 14px
  - "Quick fix": Bold label, bulleted list

- **Dividers:**
  - Thin line, `#E5E7EB`
  - Margin: 16px vertical

**Color Coding by Score Range:**

- 0-25%: `#DC2626` (red-600)
- 26-50%: `#F97316` (orange-500)
- 51-75%: `#EAB308` (yellow-500)
- 76-100%: `#10B981` (green-500)

---

### TIER 3: Priority Actions

**Purpose:** Tell users EXACTLY what to do next

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  🎯 Fix These Issues                            [Collapse ▲]│
│                                                             │
│  Ranked by impact on your compliance score                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  🔴 CRITICAL #1                                             │
│                                                             │
│  Blank Template Detected                                    │
│                                                             │
│  ❓ What's Wrong                                            │
│  Your document appears to be an unfilled template with      │
│  placeholder text like [NAME], _____, <insert here>, etc.   │
│                                                             │
│  📊 Impact on Your Score                                    │
│  • Current penalty: -70% score reduction                    │
│  • Status: Preventing valid compliance assessment           │
│  • Affected dimensions: Structure (-4 pts), Evidence (-5)   │
│                                                             │
│  ✅ How to Fix                                              │
│  1. Fill in all [PLACEHOLDER] brackets                      │
│     Before: "Policy owner: [NAME]"                          │
│     After:  "Policy owner: Sarah Chen, Compliance Manager"  │
│                                                             │
│  2. Replace all _____ blank lines                           │
│     Before: "Review frequency: _______"                     │
│     After:  "Review frequency: Quarterly"                   │
│                                                             │
│  3. Complete all instructional sections                     │
│     Remove: "(Insert your organization's process here)"     │
│     Add:    Actual step-by-step procedures                  │
│                                                             │
│  4. Add real participant scenarios                          │
│     Instead of: "Example: [TO BE COMPLETED]"                │
│     Write:      "Example: When participant John requests    │
│                 additional support hours, the Service       │
│                 Coordinator reviews his NDIS plan..."       │
│                                                             │
│  📈 Potential Score Gain: +35 to 40 points                  │
│  This is your highest-impact action!                        │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  🔴 CRITICAL #2                                             │
│                                                             │
│  Document Too Short                                         │
│                                                             │
│  ❓ What's Wrong                                            │
│  Only 142 characters extracted from your document           │
│  (need at least 800 characters for reliable assessment)     │
│                                                             │
│  📊 Impact on Your Score                                    │
│  • Lost 18 of 20 Depth points                               │
│  • Evidence snippets: 0 (need substantial text to find)     │
│  • Coverage: Only 3 of 25 points (not enough text to        │
│    match NDIS terminology)                                  │
│                                                             │
│  ✅ How to Fix                                              │
│  Expand each procedure section with complete details:       │
│                                                             │
│  1. Step-by-Step Instructions                               │
│     ❌ Don't write: "Staff must complete training"          │
│     ✅ Do write:    "All new staff members must complete    │
│                    NDIS Code of Conduct training within     │
│                    30 days of hire. Training includes:      │
│                    • Module 1: Rights and dignity (2hrs)    │
│                    • Module 2: Safeguarding (3hrs)          │
│                    • Module 3: Reporting obligations (1hr)  │
│                    Completion is verified by online test    │
│                    (80% pass required)."                    │
│                                                             │
│  2. Assign Responsibilities (Who Does What)                 │
│     • Training Coordinator: Schedules sessions              │
│     • Line Manager: Confirms attendance                     │
│     • HR: Maintains training records                        │
│                                                             │
│  3. Specify Timeframes (When Actions Occur)                 │
│     • Training: Within 30 days of hire                      │
│     • Assessment: Within 7 days of training completion      │
│     • Certificate: Issued immediately upon passing          │
│                                                             │
│  4. Document Record-Keeping                                 │
│     "Training completion certificates are stored in the     │
│     HR Management System with 7-year retention period.      │
│     Electronic records include: staff name, training date,  │
│     modules completed, test scores, and trainer signature." │
│                                                             │
│  5. Include Monitoring & Review                             │
│     "The Training Coordinator reviews completion rates      │
│     monthly and reports to the Compliance Committee.        │
│     Annual review of training content occurs in Q4."        │
│                                                             │
│  📈 Potential Score Gain: +15 to 18 points                  │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  🟡 HIGH PRIORITY #3                                        │
│                                                             │
│  Missing Core NDIS Terminology                              │
│                                                             │
│  ❓ What's Wrong                                            │
│  Your document only includes 1 of 15 essential NDIS domain  │
│  terms. This suggests gaps in coverage of required          │
│  practice standards.                                        │
│                                                             │
│  📊 Impact on Your Score                                    │
│  • Lost 22 of 25 Coverage points                            │
│  • Only 12% coverage of NDIS requirements                   │
│                                                             │
│  ✅ How to Fix                                              │
│                                                             │
│  Missing Critical Terms:                                    │
│                                                             │
│  📌 Add "Participant Consent" Section                       │
│  Must include:                                              │
│  • How consent is obtained (verbal, written, guardian)      │
│  • When consent is required (assessments, changes, sharing) │
│  • How consent is documented and stored                     │
│  • Process when consent is withdrawn                        │
│                                                             │
│  Example:                                                   │
│  "Before providing any service or support, staff must       │
│  obtain informed consent from the participant or their      │
│  decision-maker. Consent is documented using Form 12-A      │
│  and includes: nature of support, risks and benefits,       │
│  alternatives, right to withdraw. Consent forms are         │
│  reviewed annually or when circumstances change."           │
│                                                             │
│  📌 Add "Safeguarding" Section                              │
│  Must include:                                              │
│  • Prevention strategies                                    │
│  • Recognition of abuse, neglect, exploitation              │
│  • Reporting obligations and procedures                     │
│  • Investigation and response protocols                     │
│                                                             │
│  📌 Add "Restrictive Practice" Section                      │
│  (If applicable to your services)                           │
│  Must include:                                              │
│  • Definition and types of restrictive practices            │
│  • When they may be used (last resort principle)            │
│  • Authorization and consent requirements                   │
│  • Monitoring, reporting, and reduction strategies          │
│                                                             │
│  📌 Add "Incident Management" Section                       │
│  Must include:                                              │
│  • What constitutes a reportable incident                   │
│  • Immediate response procedures                            │
│  • Notification requirements (NDIS Commission, families)    │
│  • Investigation process and timeframes                     │
│  • Corrective actions and prevention measures               │
│                                                             │
│  📌 Add "Quality Indicators" Section                        │
│  Must include:                                              │
│  • How you measure service quality                          │
│  • Participant feedback mechanisms                          │
│  • Performance monitoring and reporting                     │
│  • Continuous improvement processes                         │
│                                                             │
│  💡 Reference These NDIS Standards:                         │
│  • Section 1: Rights, Choice & Control                      │
│  • Section 2: Governance & Operational Management           │
│  • Section 8: High Intensity Supports                       │
│                                                             │
│  📈 Potential Score Gain: +20 to 22 points                  │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  🟢 RECOMMENDED #4                                          │
│                                                             │
│  Strengthen Action Language                                 │
│                                                             │
│  ❓ What's Wrong                                            │
│  Document has 45% Substance score. While some action        │
│  language is present, it could be more directive and        │
│  compliance-focused.                                        │
│                                                             │
│  ✅ How to Fix                                              │
│  Replace weak language with strong compliance verbs:        │
│                                                             │
│  ❌ Avoid:    "should", "may", "could", "consider"          │
│  ✅ Use:      "must", "shall", "will", "ensure"             │
│                                                             │
│  Examples:                                                  │
│  Before: "Staff should complete incident reports"           │
│  After:  "Staff must complete incident reports within       │
│           24 hours of occurrence"                           │
│                                                             │
│  Before: "Consider obtaining participant feedback"          │
│  After:  "The Service Coordinator will obtain participant   │
│           feedback quarterly using the standard survey      │
│           template"                                         │
│                                                             │
│  📈 Potential Score Gain: +8 to 12 points                   │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  🟢 RECOMMENDED #5                                          │
│                                                             │
│  Add Regulatory Citations                                   │
│                                                             │
│  ❓ What's Wrong                                            │
│  Only 3 NDIS standards matched (need 5+ for Mature rating)  │
│                                                             │
│  ✅ How to Fix                                              │
│  Add explicit references to NDIS Practice Standards:        │
│                                                             │
│  Example:                                                   │
│  "This policy aligns with NDIS Practice Standards:          │
│  • Section 2 (Provider Governance and Operational           │
│    Management) - Outcome 2a: Governance and Operational     │
│    Management                                               │
│  • Section 7 (Qualified and Capable Workforce) - Outcome    │
│    7a: Workforce Capability"                                │
│                                                             │
│  📈 Potential Score Gain: +4 to 6 points (confidence boost) │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Visual Specifications:**

- **Priority Badges:**
  - 🔴 CRITICAL: Red background `#DC2626`, white text
  - 🟡 HIGH PRIORITY: Yellow background `#EAB308`, black text
  - 🟢 RECOMMENDED: Green background `#10B981`, white text
  - Font: Bold, 14px
  - Padding: 4px 12px
  - Border-radius: 4px

- **Card Layout:**
  - Border: 2px solid, matches priority color
  - Border-radius: 8px
  - Padding: 24px
  - Margin-bottom: 16px
  - Box-shadow: Subtle drop shadow

- **Section Headers:**
  - ❓ What's Wrong: Bold, 16px
  - 📊 Impact: Bold, 16px
  - ✅ How to Fix: Bold, 16px
  - 📈 Potential Gain: Bold, 16px, highlighted background

- **Code Blocks (Examples):**
  - Before/After: Monospace font
  - ❌ Before: Red background `#FEE2E2`
  - ✅ After: Green background `#D1FAE5`
  - Padding: 12px
  - Border-left: 4px solid

---

### TIER 4: NDIS Citations

**Purpose:** Show regulatory context and gaps

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  📚 NDIS Regulatory Alignment                   [Collapse ▲]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Citations Found: 3                                         │
│  Status: 🟡 Moderate (need 5+ for strong confidence)       │
│                                                             │
│  ✅ MATCHED STANDARDS                                       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 1. NDIS Practice Standards 7.2                        │ │
│  │                                                       │ │
│  │ Provider Governance and Operational Management        │ │
│  │                                                       │ │
│  │ Relevance Score: 98.4%                                │ │
│  │                                                       │ │
│  │ 📖 What This Standard Requires:                       │ │
│  │ "Each participant's support is overseen by robust     │ │
│  │ governance and operational management systems that    │ │
│  │ are relevant and proportionate to the size and scale  │ │
│  │ of the provider and the scope and complexity of       │ │
│  │ supports delivered."                                  │ │
│  │                                                       │ │
│  │ ✅ What Your Document Addresses:                      │ │
│  │ • Mentions governance structure                       │ │
│  │ • References operational management                   │ │
│  │                                                       │ │
│  │ ⚠️  Gaps Identified:                                  │ │
│  │ • No evidence of participant support oversight        │ │
│  │ • Missing operational management system details       │ │
│  │ • No documentation of proportionate scaling           │ │
│  │                                                       │ │
│  │ 💡 Suggestion:                                        │ │
│  │ Add a section describing:                             │ │
│  │ • How governance committee oversees participant       │ │
│  │   support quality                                     │ │
│  │ • Operational management system components            │ │
│  │ • How systems scale with organization size            │ │
│  │                                                       │ │
│  │ [View Full Standard] [Compare Side-by-Side]          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 2. NDIS Practice Standards 8.D.4                      │ │
│  │                                                       │ │
│  │ Risk Management System                                │ │
│  │                                                       │ │
│  │ Relevance Score: 98.3%                                │ │
│  │                                                       │ │
│  │ 📖 What This Standard Requires:                       │ │
│  │ "A documented risk management system that             │ │
│  │ effectively manages identified risks, covers each     │ │
│  │ of the following – incident management – complaints   │ │
│  │ management and resolution – financial management –    │ │
│  │ governance and operational management – human         │ │
│  │ resource management..."                               │ │
│  │                                                       │ │
│  │ ⚠️  Gap: Incomplete Risk Management Flow              │ │
│  │ Your document mentions risk but doesn't show the      │ │
│  │ full incident → complaints → resolution workflow      │ │
│  │ required by this standard.                            │ │
│  │                                                       │ │
│  │ 💡 Suggestion:                                        │ │
│  │ Create a comprehensive risk management section:       │ │
│  │ • Incident identification and reporting               │ │
│  │ • Complaints handling process                         │ │
│  │ • Resolution and corrective actions                   │ │
│  │ • Integration with other management systems           │ │
│  │                                                       │ │
│  │ [View Full Standard]                                  │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 3. NDIS Practice Standards 1.2                        │ │
│  │                                                       │ │
│  │ Exploitation and Discrimination                       │ │
│  │                                                       │ │
│  │ Relevance Score: 84.1%                                │ │
│  │                                                       │ │
│  │ ⚠️  Partial Match:                                    │ │
│  │ Document references rights and dignity but lacks      │ │
│  │ specific safeguards against exploitation and          │ │
│  │ discrimination.                                       │ │
│  │                                                       │ │
│  │ [View Full Standard]                                  │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  ⚠️  MISSING STANDARDS (Not Addressed in Your Document)     │
│                                                             │
│  Your document should address these additional standards:   │
│                                                             │
│  ❌ Section 1: Exploitation and Discrimination              │
│     • Risk identification and prevention                    │
│     • Staff training on recognizing exploitation            │
│     • Reporting procedures                                  │
│                                                             │
│  ❌ Section 5: Service Access                               │
│     • Participant access to services                        │
│     • Communication and information provision               │
│     • Service agreements and clarity                        │
│                                                             │
│  ❌ Section 6: Specialist Disability Accommodation          │
│     (Only if you provide SDA services)                      │
│     • Physical environment standards                        │
│     • Building design and accessibility                     │
│                                                             │
│  💡 Impact of Adding These Sections:                        │
│  Adding comprehensive coverage of missing standards could   │
│  increase your score by 15-25 points and improve NDIS       │
│  citations from 3 to 6+, achieving "Mature" status.         │
│                                                             │
│  [Browse All NDIS Practice Standards]                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Visual Specifications:**

- **Citation Cards:**
  - Nested box design
  - Background: `#F9FAFB` (light gray)
  - Border: 1px solid `#E5E7EB`
  - Border-radius: 6px
  - Padding: 16px

- **Relevance Score:**
  - 90-100%: Green `#10B981`
  - 75-89%: Yellow `#EAB308`
  - 60-74%: Orange `#F97316`
  - <60%: Red `#DC2626`
  - Display as percentage with progress bar

- **Status Indicators:**
  - ✅ Matched: Green checkmark
  - ⚠️  Gap: Yellow warning
  - ❌ Missing: Red X

- **Interactive Elements:**
  - [View Full Standard]: Opens modal or new tab
  - [Compare Side-by-Side]: Split view (doc vs standard)
  - [Browse All Standards]: Link to NDIS website

---

### TIER 5: Document Evidence

**Purpose:** Show AI reasoning and build trust

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 Evidence Found in Your Document             [Collapse ▲]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  This shows what content our AI identified in your          │
│  document and what was missing.                             │
│                                                             │
│  💚 STRONG EVIDENCE                                         │
│  Highly relevant sections: 0 snippets                       │
│                                                             │
│  No strongly compliant sections found. This typically       │
│  indicates:                                                 │
│  • Document is a blank template                             │
│  • Content is too brief for assessment                      │
│  • Document doesn't contain policy/procedure text           │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  💛 PARTIAL EVIDENCE                                        │
│  Somewhat relevant sections: 0 snippets                     │
│                                                             │
│  No partial evidence found.                                 │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  🔴 WHAT WE EXPECTED TO FIND                                │
│                                                             │
│  Based on NDIS requirements, we looked for but did not      │
│  find evidence of:                                          │
│                                                             │
│  ❌ Participant Consent Procedures                          │
│     Expected to see:                                        │
│     • How consent is obtained                               │
│     • When consent is required                              │
│     • Documentation methods                                 │
│     • Withdrawal process                                    │
│                                                             │
│  ❌ Incident Reporting Workflows                            │
│     Expected to see:                                        │
│     • Definition of reportable incidents                    │
│     • Immediate response steps                              │
│     • Notification timeframes                               │
│     • Investigation procedures                              │
│                                                             │
│  ❌ Staff Training Requirements                             │
│     Expected to see:                                        │
│     • Mandatory training list                               │
│     • Completion timeframes                                 │
│     • Assessment methods                                    │
│     • Record-keeping processes                              │
│                                                             │
│  ❌ Risk Assessment Processes                               │
│     Expected to see:                                        │
│     • Risk identification methods                           │
│     • Assessment frequency                                  │
│     • Mitigation strategies                                 │
│     • Review and monitoring                                 │
│                                                             │
│  ❌ Complaint Handling Procedures                           │
│     Expected to see:                                        │
│     • How complaints are received                           │
│     • Acknowledgment timeframes                             │
│     • Investigation process                                 │
│     • Resolution and feedback                               │
│                                                             │
│  ❌ Record-Keeping Requirements                             │
│     Expected to see:                                        │
│     • What records must be kept                             │
│     • Storage methods and security                          │
│     • Retention periods                                     │
│     • Access and audit processes                            │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  ⚠️  POSSIBLE QUALITY ISSUES                                │
│                                                             │
│  Our analysis identified the following concerns:            │
│                                                             │
│  🟡 Blank Template Structure                                │
│     The document contains template markers like             │
│     [PLACEHOLDER], _____, and instructional text that       │
│     suggests it hasn't been filled in yet.                  │
│                                                             │
│  🟡 Very Short Document                                     │
│     Only 142 characters were extracted. This is             │
│     insufficient for a comprehensive compliance             │
│     document, which typically requires 800+ characters      │
│     of substantial content.                                 │
│                                                             │
│  🟡 Low Text Extraction Quality                             │
│     The PDF may be scanned/image-based, resulting in        │
│     poor text extraction. Consider:                         │
│     • Re-scanning at higher resolution                      │
│     • Using OCR software                                    │
│     • Converting to text-based PDF                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Example with Actual Evidence Found:**

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 Evidence Found in Your Document             [Collapse ▲]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  💚 STRONG EVIDENCE                                         │
│  Highly relevant sections: 2 snippets                       │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Snippet 1 (Page 3, Lines 24-28)                       │ │
│  │                                                       │ │
│  │ "All staff members must complete NDIS Code of Conduct │ │
│  │ training within 30 days of commencement. The Training │ │
│  │ Coordinator schedules sessions quarterly. Completion  │ │
│  │ is verified through online assessment (minimum 80%    │ │
│  │ pass required). Certificates are stored in the HR     │ │
│  │ Management System with 7-year retention."             │ │
│  │                                                       │ │
│  │ ✅ Why This Is Strong Evidence:                       │ │
│  │ • Clear responsibility (Training Coordinator)         │ │
│  │ • Specific timeframe (30 days, quarterly)             │ │
│  │ • Measurable standard (80% pass)                      │ │
│  │ • Record-keeping defined (HR system, 7 years)         │ │
│  │                                                       │ │
│  │ Matched NDIS Requirements:                            │
│  │ • Staff training ✓                                    │ │
│  │ • Timeframes ✓                                        │ │
│  │ • Verification ✓                                      │ │
│  │ • Records ✓                                           │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Snippet 2 (Page 5, Lines 12-16)                       │ │
│  │                                                       │ │
│  │ "Participants have the right to make complaints at    │ │
│  │ any time. Complaints are acknowledged within 24 hours │ │
│  │ and investigated within 10 business days. The         │ │
│  │ Complaints Officer documents all complaints in the    │ │
│  │ Compliance Register and reports monthly to the Board."│ │
│  │                                                       │ │
│  │ ✅ Why This Is Strong Evidence:                       │ │
│  │ • Acknowledges participant rights                     │ │
│  │ • Specific timeframes (24hrs, 10 days)                │ │
│  │ • Clear process and responsibility                    │ │
│  │ • Oversight mechanism (Board reporting)               │ │
│  │                                                       │ │
│  │ Matched NDIS Requirements:                            │ │
│  │ • Complaint access ✓                                  │ │
│  │ • Response timeframes ✓                               │ │
│  │ • Documentation ✓                                     │ │
│  │ • Governance oversight ✓                              │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                             │
│  💛 PARTIAL EVIDENCE                                        │
│  Somewhat relevant sections: 1 snippet                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Snippet 3 (Page 2, Lines 8-10)                        │ │
│  │                                                       │ │
│  │ "The organization maintains a risk register that is   │ │
│  │ reviewed quarterly by the senior management team."    │ │
│  │                                                       │ │
│  │ ⚠️  Why This Is Only Partial Evidence:                │ │
│  │ • Mentions risk management ✓                          │ │
│  │ • States review frequency ✓                           │ │
│  │ • Missing: risk identification process                │ │
│  │ • Missing: risk assessment methodology                │ │
│  │ • Missing: mitigation strategies                      │ │
│  │ • Missing: specific NDIS-related risks                │ │
│  │                                                       │ │
│  │ 💡 To Strengthen:                                     │ │
│  │ Expand this section to describe:                      │ │
│  │ • How risks are identified                            │
│  │ • Risk rating system (likelihood × impact)            │ │
│  │ • Mitigation and control measures                     │ │
│  │ • Monitoring and escalation processes                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### TIER 6: Warnings & Quality Issues

**Purpose:** Explain technical problems affecting score

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  Warnings & Quality Issues                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  The following issues may have affected your score:         │
│                                                             │
│  🟡 [EXTRACTION] Low Text Density for PDF                   │
│                                                             │
│  What this means:                                           │
│  Your PDF contains minimal extractable text relative to     │
│  file size. This suggests a scanned or image-based PDF.     │
│                                                             │
│  Impact:                                                    │
│  • Score reliability reduced to 58% confidence              │
│  • May have missed content due to poor OCR                  │
│  • Depth and Evidence scores likely underestimated          │
│                                                             │
│  How to fix:                                                │
│  ✓ Re-scan document at 300 DPI or higher                    │
│  ✓ Use OCR software (Adobe Acrobat, ABBYY FineReader)       │
│  ✓ Export original source document as text-based PDF        │
│  ✓ Convert to DOCX format if possible                       │
│                                                             │
│  [Learn more about PDF quality]                             │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🟡 [SCORING] Template-Like Structure Detected              │
│                                                             │
│  What this means:                                           │
│  The document appears to contain unfilled template          │
│  sections with placeholders like [NAME], _____, or          │
│  instructional text meant for authors.                      │
│                                                             │
│  Impact:                                                    │
│  • Structure score penalized by 70%                         │
│  • Score constrained to prevent false positives             │
│  • Unable to assess actual compliance until completed       │
│                                                             │
│  How to fix:                                                │
│  ✓ Fill in all [PLACEHOLDER] sections                      │
│  ✓ Replace blank lines with actual content                  │
│  ✓ Remove instructional notes for template users            │
│  ✓ Add real examples instead of "[TO BE COMPLETED]"         │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🔴 [RAG] Semantic Embeddings Warming Up                    │
│                                                             │
│  What this means:                                           │
│  Our NDIS citation database is still initializing, so       │
│  this assessment used keyword-based retrieval instead of    │
│  advanced semantic matching.                                │
│                                                             │
│  Impact:                                                    │
│  • Citation quality may be lower than usual                 │
│  • Confidence capped at 80% for this assessment             │
│  • Some relevant standards may have been missed             │
│                                                             │
│  What to do:                                                │
│  ✓ Re-analyze document in 5-10 minutes for better results   │
│  ✓ Current score is still valid but conservative            │
│                                                             │
│  [Re-analyze now] [Notify me when ready]                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Visual Specifications:**

- **Warning Cards:**
  - Icon + Category tag: `[EXTRACTION]`, `[SCORING]`, `[RAG]`
  - Background: Light yellow `#FEF3C7`
  - Border-left: 4px solid `#EAB308`
  - Padding: 16px
  - Border-radius: 6px

- **Severity Levels:**
  - 🔴 Red: Significant impact, requires action
  - 🟡 Yellow: Moderate impact, review recommended
  - 🔵 Blue: Informational, no action needed

---

## Visual Design Specifications

### Color System

**Status Colors:**

| Status | Background | Border | Text | Badge |
|--------|-----------|--------|------|-------|
| Critical Gap | `#FEE2E2` | `#DC2626` | `#7F1D1D` | 🔴 |
| High Risk Gap | `#FED7AA` | `#F97316` | `#7C2D12` | 🟠 |
| OK | `#FEF3C7` | `#EAB308` | `#713F12` | 🟡 |
| Mature | `#D1FAE5` | `#10B981` | `#065F46` | 🟢 |

**Component Score Colors:**

| Range | Color | Hex |
|-------|-------|-----|
| 0-25% | Red | `#DC2626` |
| 26-50% | Orange | `#F97316` |
| 51-75% | Yellow | `#EAB308` |
| 76-100% | Green | `#10B981` |

**UI Element Colors:**

| Element | Color | Hex |
|---------|-------|-----|
| Primary Button | Blue | `#3B82F6` |
| Secondary Button | Gray | `#6B7280` |
| Link Text | Blue | `#2563EB` |
| Divider Lines | Light Gray | `#E5E7EB` |
| Card Background | Off-white | `#F9FAFB` |
| Text Primary | Dark Gray | `#111827` |
| Text Secondary | Medium Gray | `#6B7280` |

### Typography

**Font Families:**
- Headings: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Body: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Monospace (code): `"JetBrains Mono", "Fira Code", Consolas, monospace`

**Font Sizes:**

| Element | Size | Weight |
|---------|------|--------|
| Hero Title | 32px | Bold (700) |
| Status Badge | 18px | Bold (700) |
| Section Header | 20px | Semibold (600) |
| Subsection Header | 16px | Semibold (600) |
| Body Text | 14px | Regular (400) |
| Small Text | 12px | Regular (400) |
| Caption | 11px | Regular (400) |

### Spacing

**Padding:**
- Hero Section: 32px
- Cards: 24px
- Buttons: 12px horizontal, 8px vertical
- Tags/Badges: 12px horizontal, 4px vertical

**Margins:**
- Between sections: 24px
- Between cards: 16px
- Between paragraphs: 12px

### Icons

**Emoji Usage:**
- 📄 Document
- 🔴 Critical
- 🟠 High Risk
- 🟡 Caution
- 🟢 Success
- ⚡ Priority Action
- 📊 Data/Chart
- 🎯 Target/Goal
- 📚 Knowledge/Standards
- 🔍 Evidence/Search
- ⚠️  Warning
- ✅ Success/Checkmark
- ❌ Failure/X
- 💡 Tip/Idea
- 📈 Improvement
- 💚 Strong
- 💛 Moderate
- 🔴 Weak

### Responsive Breakpoints

```css
/* Mobile */
@media (max-width: 767px) {
  /* Single column, stacked layout */
  /* Smaller fonts, compact spacing */
}

/* Tablet */
@media (min-width: 768px) and (max-width: 1023px) {
  /* Single column with larger touch targets */
}

/* Desktop */
@media (min-width: 1024px) {
  /* Multi-column where appropriate */
  /* Hover states enabled */
}
```

---

## Content Writing Guidelines

### Tone & Voice

**Principles:**
- ✅ Supportive and constructive (not punitive)
- ✅ Plain language (avoid jargon)
- ✅ Action-oriented (tell users what to DO)
- ✅ Specific (no vague suggestions)
- ✅ Encouraging (celebrate what's working)

**Examples:**

❌ **Don't write:**
"Document exhibits insufficient coverage of requisite NDIS terminology pertaining to safeguarding protocols."

✅ **Do write:**
"Your document needs sections on safeguarding, which is a core NDIS requirement. Add procedures for preventing and responding to abuse, neglect, and exploitation."

---

❌ **Don't write:**
"Score degraded due to template structure detection."

✅ **Do write:**
"This appears to be a blank template. Fill in all placeholder sections to get an accurate compliance assessment."

---

### Writing Style by Section

**Hero Section:**
- 1-2 sentences maximum
- State the bottom line first
- No jargon or technical terms

**Score Breakdown:**
- Start with "What this measures"
- State "Your result" factually
- End with "Quick fix" action

**Priority Actions:**
- Use numbered steps
- Include before/after examples
- Quantify impact ("+ X points")
- End with encouragement

**NDIS Citations:**
- Quote standards briefly
- Explain gaps in plain language
- Suggest specific additions

**Warnings:**
- Explain "What this means"
- Quantify "Impact"
- Provide "How to fix"

### Word Choice

**Preferred Terms:**

| Instead of | Use |
|------------|-----|
| "Insufficient" | "Missing" or "Needs" |
| "Non-compliant" | "Gap" or "Requires attention" |
| "Deficient" | "Could be strengthened" |
| "Failed to address" | "Didn't include" |
| "Substandard" | "Needs improvement" |
| "Penalized" | "Reduced score" |

---

## API Response Structure

### JSON Schema

```json
{
  "analysis_id": "unique-analysis-id",
  "document": {
    "filename": "2280354_A3.pdf",
    "file_size_kb": 245,
    "upload_timestamp": "2026-05-18T10:30:00Z"
  },
  
  "overall_status": {
    "status": "CRITICAL_GAP",
    "confidence_percentage": 25,
    "status_label": "Critical Gap",
    "status_icon": "🔴",
    "summary": "This document needs significant work before it can demonstrate NDIS compliance.",
    "priority_action": {
      "text": "Fix blank template sections first",
      "potential_gain_points": 35,
      "tier": 3,
      "action_id": "action_1"
    }
  },
  
  "score_breakdown": {
    "total_score": 25,
    "max_possible": 100,
    "components": [
      {
        "dimension": "Coverage",
        "score": 3,
        "max_points": 25,
        "percentage": 12,
        "status": "CRITICAL",
        "icon": "🔴",
        "description": "Presence of NDIS terminology and requirement terms",
        "result": "Missing 88% of required NDIS terms",
        "quick_fix": "Add sections addressing participant consent, safeguarding, restrictive practice, and incident management"
      },
      {
        "dimension": "Depth",
        "score": 2,
        "max_points": 20,
        "percentage": 10,
        "status": "CRITICAL",
        "icon": "🔴",
        "description": "Document length and level of detail in procedures",
        "result": "Document is only 142 characters (need 800+)",
        "quick_fix": "Expand each section with step-by-step instructions, responsibilities, and timeframes"
      },
      {
        "dimension": "Substance",
        "score": 18,
        "max_points": 40,
        "percentage": 45,
        "status": "MODERATE",
        "icon": "🟡",
        "description": "Action-oriented language, responsibilities, and processes",
        "result": "Some action indicators found, but lacks comprehensive detail",
        "quick_fix": "Use must/shall/will language, assign clear responsibilities, specify timeframes"
      },
      {
        "dimension": "Structure",
        "score": 6,
        "max_points": 10,
        "percentage": 60,
        "status": "MODERATE",
        "icon": "🟡",
        "description": "Document organization with headings, lists, and structure",
        "result": "Numbered lists detected, but template penalty applied",
        "quick_fix": "Complete all placeholder sections and remove blank form fields"
      },
      {
        "dimension": "Evidence Quality",
        "score": 0,
        "max_points": 5,
        "percentage": 0,
        "status": "CRITICAL",
        "icon": "🔴",
        "description": "Strength of specific, contextual compliance evidence",
        "result": "No strong evidence snippets found in document",
        "quick_fix": "Include specific examples, completed risk assessments, and documented procedures"
      }
    ]
  },
  
  "priority_actions": [
    {
      "action_id": "action_1",
      "rank": 1,
      "priority": "CRITICAL",
      "priority_icon": "🔴",
      "title": "Blank Template Detected",
      "what_is_wrong": "Your document appears to be an unfilled template with placeholder text like [NAME], _____, etc.",
      "impact": {
        "description": "Current penalty: -70% score reduction",
        "affected_dimensions": [
          {"dimension": "Structure", "points_lost": 4},
          {"dimension": "Evidence Quality", "points_lost": 5}
        ],
        "blocks_assessment": true
      },
      "how_to_fix": {
        "steps": [
          {
            "step_number": 1,
            "instruction": "Fill in all [PLACEHOLDER] brackets",
            "example_before": "Policy owner: [NAME]",
            "example_after": "Policy owner: Sarah Chen, Compliance Manager"
          },
          {
            "step_number": 2,
            "instruction": "Replace all _____ blank lines",
            "example_before": "Review frequency: _______",
            "example_after": "Review frequency: Quarterly"
          }
        ]
      },
      "potential_gain": {
        "min_points": 35,
        "max_points": 40,
        "description": "This is your highest-impact action!"
      }
    },
    {
      "action_id": "action_2",
      "rank": 2,
      "priority": "CRITICAL",
      "priority_icon": "🔴",
      "title": "Document Too Short",
      "what_is_wrong": "Only 142 characters extracted (need at least 800 for reliable assessment)",
      "impact": {
        "description": "Lost 18 of 20 Depth points",
        "affected_dimensions": [
          {"dimension": "Depth", "points_lost": 18},
          {"dimension": "Coverage", "points_lost": 22},
          {"dimension": "Evidence Quality", "points_lost": 5}
        ]
      },
      "how_to_fix": {
        "steps": [
          {
            "step_number": 1,
            "instruction": "Expand each procedure section with complete details",
            "example_before": "Staff must complete training",
            "example_after": "All new staff members must complete NDIS Code of Conduct training within 30 days of hire. Training includes: Module 1: Rights and dignity (2hrs), Module 2: Safeguarding (3hrs)..."
          }
        ]
      },
      "potential_gain": {
        "min_points": 15,
        "max_points": 18
      }
    }
  ],
  
  "ndis_citations": {
    "total_found": 3,
    "target_for_mature": 5,
    "status": "MODERATE",
    "status_icon": "🟡",
    "matched_standards": [
      {
        "citation_id": "ndis_7_2",
        "standard_code": "7.2",
        "title": "Provider Governance and Operational Management",
        "relevance_score": 98.4,
        "standard_text": "Each participant's support is overseen by robust governance and operational management systems...",
        "what_doc_addresses": [
          "Mentions governance structure",
          "References operational management"
        ],
        "gaps_identified": [
          "No evidence of participant support oversight",
          "Missing operational management system details"
        ],
        "suggestion": "Add a section describing how governance committee oversees participant support quality...",
        "links": {
          "view_standard": "https://ndis.gov.au/standards/7-2",
          "compare": "/compare/ndis_7_2/doc_123"
        }
      }
    ],
    "missing_standards": [
      {
        "standard_code": "1",
        "title": "Exploitation and Discrimination",
        "required_content": [
          "Risk identification and prevention",
          "Staff training on recognizing exploitation",
          "Reporting procedures"
        ]
      }
    ],
    "impact_of_adding": {
      "potential_points": 20,
      "new_citation_count": 6,
      "would_achieve_mature": true
    }
  },
  
  "document_evidence": {
    "strong_snippets": {
      "count": 0,
      "snippets": []
    },
    "partial_snippets": {
      "count": 0,
      "snippets": []
    },
    "expected_but_missing": [
      {
        "category": "Participant Consent Procedures",
        "expected_elements": [
          "How consent is obtained",
          "When consent is required",
          "Documentation methods",
          "Withdrawal process"
        ]
      },
      {
        "category": "Incident Reporting Workflows",
        "expected_elements": [
          "Definition of reportable incidents",
          "Immediate response steps",
          "Notification timeframes",
          "Investigation procedures"
        ]
      }
    ],
    "quality_issues": [
      {
        "issue_type": "BLANK_TEMPLATE",
        "severity": "HIGH",
        "description": "Document contains template markers like [PLACEHOLDER], _____, and instructional text"
      },
      {
        "issue_type": "VERY_SHORT",
        "severity": "HIGH",
        "description": "Only 142 characters extracted (need 800+ for comprehensive assessment)"
      }
    ]
  },
  
  "warnings": [
    {
      "category": "EXTRACTION",
      "severity": "MODERATE",
      "icon": "🟡",
      "title": "Low Text Density for PDF",
      "description": "Your PDF contains minimal extractable text relative to file size. This suggests a scanned or image-based PDF.",
      "impact": "Score reliability reduced to 58% confidence",
      "how_to_fix": [
        "Re-scan document at 300 DPI or higher",
        "Use OCR software (Adobe Acrobat, ABBYY FineReader)",
        "Export original source document as text-based PDF"
      ],
      "learn_more_link": "/docs/pdf-quality"
    },
    {
      "category": "SCORING",
      "severity": "MODERATE",
      "icon": "🟡",
      "title": "Template-Like Structure Detected",
      "description": "The document appears to contain unfilled template sections",
      "impact": "Structure score penalized by 70%",
      "how_to_fix": [
        "Fill in all [PLACEHOLDER] sections",
        "Replace blank lines with actual content"
      ]
    }
  ],
  
  "metadata": {
    "engine": "azure-openai",
    "model": "gpt-4o-mini",
    "rubric_version": "auto-detected-cubic",
    "extraction_method": "low",
    "processing_time_ms": 3245,
    "updated_at": "2026-05-18T10:30:17Z"
  }
}
```

---

## Implementation Examples

### React Component Structure

```
src/
├── components/
│   ├── AnalysisResult/
│   │   ├── HeroSection.tsx          # Tier 1
│   │   ├── ScoreBreakdown.tsx       # Tier 2
│   │   ├── PriorityActions.tsx      # Tier 3
│   │   ├── NDISCitations.tsx        # Tier 4
│   │   ├── DocumentEvidence.tsx     # Tier 5
│   │   ├── Warnings.tsx             # Tier 6
│   │   └── index.tsx                # Main container
│   │
│   ├── shared/
│   │   ├── StatusBadge.tsx
│   │   ├── ProgressBar.tsx
│   │   ├── ActionCard.tsx
│   │   ├── CitationCard.tsx
│   │   ├── SnippetCard.tsx
│   │   └── WarningBanner.tsx
│   │
│   └── ui/
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Accordion.tsx
│       └── Tooltip.tsx
```

### Example Hero Section Component

```typescript
// HeroSection.tsx
import React from 'react';
import { StatusBadge } from '../shared/StatusBadge';
import { getStatusColor, getStatusIcon } from '@/lib/utils';

interface HeroSectionProps {
  documentName: string;
  status: 'CRITICAL_GAP' | 'HIGH_RISK_GAP' | 'OK' | 'MATURE';
  confidencePercentage: number;
  summary: string;
  priorityAction: {
    text: string;
    potentialGain: number;
    actionId: string;
  };
  onDownload: () => void;
  onJumpToAction: (actionId: string) => void;
}

export function HeroSection({
  documentName,
  status,
  confidencePercentage,
  summary,
  priorityAction,
  onDownload,
  onJumpToAction
}: HeroSectionProps) {
  const statusColor = getStatusColor(status);
  const statusIcon = getStatusIcon(status);
  const statusLabel = status.replace(/_/g, ' ');

  return (
    <div 
      className="p-8 rounded-lg border-2"
      style={{ 
        backgroundColor: `${statusColor}20`,
        borderColor: statusColor 
      }}
    >
      {/* Document Header */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">📄</span>
          <h2 className="text-lg font-semibold text-gray-900">
            {documentName}
          </h2>
        </div>
        <button
          onClick={onDownload}
          className="text-sm text-blue-600 hover:text-blue-700 px-3 py-1 border border-blue-600 rounded"
        >
          Download
        </button>
      </div>

      {/* Status Badge */}
      <div className="mb-4">
        <StatusBadge 
          status={status}
          label={statusLabel}
          icon={statusIcon}
        />
      </div>

      {/* Confidence Score */}
      <div className="mb-4">
        <div className="text-4xl font-bold" style={{ color: statusColor }}>
          {confidencePercentage}%
        </div>
        <div className="text-sm text-gray-600 mt-1">
          Coverage: 0% | Evidence: 56%
        </div>
      </div>

      {/* Summary */}
      <p className="text-gray-700 mb-4 max-w-2xl">
        {summary}
      </p>

      {/* Priority Action */}
      <div 
        className="flex items-start gap-3 p-4 bg-white rounded-lg border border-gray-200 cursor-pointer hover:border-blue-500 transition-colors"
        onClick={() => onJumpToAction(priorityAction.actionId)}
      >
        <span className="text-2xl">⚡</span>
        <div className="flex-1">
          <div className="font-semibold text-gray-900 mb-1">
            Priority: {priorityAction.text}
          </div>
          <div className="text-sm text-gray-600">
            Potential score gain: +{priorityAction.potentialGain} points
          </div>
        </div>
        <svg 
          className="w-5 h-5 text-gray-400"
          fill="none" 
          strokeLinecap="round" 
          strokeLinejoin="round" 
          strokeWidth="2" 
          viewBox="0 0 24 24" 
          stroke="currentColor"
        >
          <path d="M9 5l7 7-7 7"></path>
        </svg>
      </div>
    </div>
  );
}
```

---

## Mobile vs Desktop Layouts

### Desktop Layout (>1024px)

```
┌─────────────────────────────────────────────────────────────┐
│  [Sidebar Navigation]  │  [Main Content Area]              │
│                        │                                   │
│  • Overview            │  TIER 1: Hero Section             │
│  • Score Breakdown     │  (Full width)                     │
│  • Actions (3)         │                                   │
│  • Citations (3)       │  ────────────────────────────────  │
│  • Evidence            │                                   │
│  • Warnings (2)        │  TIER 2: Score Breakdown          │
│                        │  [Expanded by default]            │
│                        │                                   │
│                        │  ────────────────────────────────  │
│                        │                                   │
│                        │  TIER 3: Priority Actions         │
│                        │  [Expanded, scrollable]           │
│                        │                                   │
│                        │  ────────────────────────────────  │
│                        │                                   │
│                        │  TIER 4: NDIS Citations           │
│                        │  [Collapsed, expand on click]     │
│                        │                                   │
└────────────────────────┴───────────────────────────────────┘
```

**Features:**
- Sticky sidebar for quick navigation
- Jump-to-section links
- Two-column layout where appropriate
- Hover tooltips enabled

### Mobile Layout (<768px)

```
┌─────────────────────────────────┐
│                                 │
│  TIER 1: Hero Section           │
│  (Condensed)                    │
│                                 │
│  🔴 25%                          │
│  Critical Gap                   │
│  ⚡ Priority action              │
│                                 │
├─────────────────────────────────┤
│                                 │
│  📊 Score Breakdown  [Expand ▼] │
│                                 │
├─────────────────────────────────┤
│                                 │
│  🎯 Fix These (3)    [Expand ▼] │
│                                 │
├─────────────────────────────────┤
│                                 │
│  📚 Citations (3)    [Expand ▼] │
│                                 │
├─────────────────────────────────┤
│                                 │
│  ⚠️  Warnings (2)                │
│  [Always visible]               │
│                                 │
└─────────────────────────────────┘
```

**Features:**
- Vertical stack only
- All sections collapsed by default (except Hero + Warnings)
- Swipe to expand
- Larger touch targets (min 44px)
- Bottom sheet for detailed views

---

## Summary Checklist

Before implementing, ensure each tier includes:

- ✅ **Tier 1 (Hero)**
  - [ ] Status badge with icon
  - [ ] Confidence percentage (large)
  - [ ] One-sentence summary
  - [ ] Priority #1 action with score gain

- ✅ **Tier 2 (Breakdown)**
  - [ ] 5 component scores
  - [ ] Progress bars with colors
  - [ ] "What this measures" explanations
  - [ ] Quick fix suggestions

- ✅ **Tier 3 (Actions)**
  - [ ] Ranked by impact
  - [ ] What + Impact + How structure
  - [ ] Before/after examples
  - [ ] Potential score gains

- ✅ **Tier 4 (Citations)**
  - [ ] Matched standards list
  - [ ] Gap analysis per standard
  - [ ] Missing standards list
  - [ ] Links to full standards

- ✅ **Tier 5 (Evidence)**
  - [ ] Strong/partial/missing categories
  - [ ] Actual document snippets
  - [ ] Expected content checklist
  - [ ] Quality issue explanations

- ✅ **Tier 6 (Warnings)**
  - [ ] Category tags [EXTRACTION], [SCORING], [RAG]
  - [ ] What + Impact + How to fix
  - [ ] Severity indicators

---

## Next Steps

1. **Review this guide** with your team
2. **Create mockups** in Figma/Sketch based on layouts
3. **Implement API response** structure
4. **Build React components** tier by tier
5. **Test with real data** (Critical, OK, Mature cases)
6. **Gather user feedback** and iterate

---

**Document Version:** 1.0  
**Last Updated:** 2026-05-18  
**Author:** Claude (Anthropic)  
**For:** Cenaris NDIS Compliance SaaS

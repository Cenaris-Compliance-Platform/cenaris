# Walkthrough Implementation Plan

**Created:** May 14, 2026  
**Last Updated:** May 14, 2026
**Branch:** `paymentgate`  
**Status:** ✅ Phase 1 COMPLETE | Phase 2 Ready

---

## 1. Overview & Rationale

### Why Database Persistence (Not localStorage):
- ✅ Multi-device sync (user sees same progress on desktop, phone, tablet)
- ✅ Audit trail (track engagement metrics)
- ✅ Survives browser clears
- ✅ Team visibility (admins can see member progress)
- ✅ Resilient API state
- ✅ Can trigger server-side analytics/notifications

### Backfill Strategy for Existing Users:
- **Completed onboarding** → `state: 'not_started'`, `eligible: true`
- **Next dashboard visit** → Smart detection runs
- **Meets "needs help" criteria** → Soft banner appears
- **Otherwise** → Skip walkthrough, keep available in help menu

---

## 2. Phase Overview & Decisions

### Phase 1: Core Foundation (ESSENTIAL)
**Goal:** Database model, state management, API, dashboard trigger  
**Status:** ✅ COMPLETE

- [x] **Database Model** - `WalkthroughState` & `WalkthroughStage` tables
- [x] **Migration** - Alembic migration `s1a2b3c4d5e6_add_walkthrough_state.py`
- [x] **Service Layer** - `WalkthroughService` with state management & eligibility detection
- [x] **API Endpoints** - 7 REST endpoints for state management
- [x] **Dashboard Integration** - `eligible_walkthroughs` passed to template context
- [x] **Service Import** - `walkthrough_service` singleton tested & working

---

### Phase 2: Walkthrough Stages (CORE FEATURE)
**Goal:** Guided step-by-step flow with interactive components

- [ ] **Stage Model** - `WalkthroughStage` (title, description, cta, target element)
- [ ] **Stage Sequencing** - Logic for next/prev/skip/complete
- [ ] **Spotlight/Highlight** - DOM element targeting & visual guide
- [ ] **Step Tracking** - Track which stage user is on
- [ ] **Completion Logic** - Mark stages as complete, award badges
- [ ] **UI Components** - Modal/sidebar stage display
- [ ] **Persistence** - Save progress per stage

---

### Phase 3: Content & Personalization (IMPORTANT)
**Goal:** Dynamic content based on user type, engagement, and progress

- [ ] **User Segments** - Member vs Admin vs Org Admin personas
- [ ] **Segment-Specific Walkthroughs** - Different flows per role
- [ ] **Conditional Content** - Show/hide stages based on org features
- [ ] **Smart Detection** - Analyze user behavior to offer help
  - No documents uploaded? → Suggest upload walkthrough
  - No requirements linked? → Suggest linking walkthrough
  - Etc.
- [ ] **A/B Testing Support** - Track variant effectiveness
- [ ] **Analytics Events** - `walkthrough:started`, `walkthrough:completed`, `stage:skipped`

---

### Phase 4: Advanced Features (NICE-TO-HAVE)
**Goal:** Enhanced UX and admin controls

- [ ] **Admin Dashboard** - View member progress, trigger walkthroughs
- [ ] **Dismissal & Suppression** - "Don't show again" + time-based re-triggers
- [ ] **Contextual Help** - Embed mini-walkthroughs in feature sections
- [ ] **Feedback Capture** - "Was this helpful?" for each stage
- [ ] **Walkthrough Builder UI** - Non-technical creation of custom walkthroughs
- [ ] **Performance Metrics** - Time per stage, dropout analysis
- [ ] **Mobile Adaptation** - Responsive stage display for phones
- [ ] **Keyboard Navigation** - Accessibility (arrow keys, escape)

---

### Phase 5: Gamification & Engagement (OPTIONAL)
**Goal:** Motivate completion and learning

- [ ] **Badge System** - Award badges on walkthrough completion
- [ ] **Leaderboard** - Org-level "most onboarded" tracking
- [ ] **Streak Tracking** - Consecutive days completing tasks
- [ ] **Progress Visualization** - Visual progress bar/wheel
- [ ] **Milestone Celebrations** - Animations/confetti on major completions

---

## 3. Phase 1 Implementation Details

### 3.1 Database Model: `WalkthroughState`

```python
class WalkthroughState(db.Model):
    __tablename__ = 'walkthrough_states'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # State tracking
    walkthrough_key = db.Column(db.String(64), nullable=False)  # e.g., 'onboarding', 'upload_docs'
    state = db.Column(db.String(32), default='not_started')  # not_started, in_progress, completed, skipped
    current_stage = db.Column(db.Integer, default=0)
    
    # Eligibility & triggers
    eligible = db.Column(db.Boolean, default=True)
    auto_triggered = db.Column(db.Boolean, default=False)
    manual_triggered = db.Column(db.Boolean, default=False)
    dismissed_until = db.Column(db.DateTime, nullable=True)
    permanently_dismissed = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    first_started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_interacted_at = db.Column(db.DateTime, nullable=True)
    
    # Metadata
    completion_percentage = db.Column(db.Float, default=0.0)
    stages_completed = db.Column(db.Integer, default=0)
    total_stages = db.Column(db.Integer, default=0)
    metadata = db.Column(db.JSON, default={})  # Custom data per walkthrough
    
    # Relationships
    organization = db.relationship('Organization', backref='walkthrough_states')
    user = db.relationship('User', backref='walkthrough_states')
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'user_id', 'walkthrough_key', name='uq_walkthrough_state'),
        db.Index('ix_walkthrough_state_org_user', 'organization_id', 'user_id'),
    )
```

### 3.2 Service Layer: `WalkthroughService`

**Core Methods:**
- `get_or_create_state(org_id, user_id, walkthrough_key)` - Initialize state
- `detect_eligible_walkthroughs(org_id, user_id)` - Smart eligibility detection
- `start_walkthrough(state_id)` - Mark as in_progress
- `next_stage(state_id)` - Advance to next stage
- `skip_stage(state_id)` - Skip current stage
- `complete_walkthrough(state_id)` - Mark as completed
- `dismiss_walkthrough(state_id, hours=24)` - Temporary dismissal
- `get_state(org_id, user_id, walkthrough_key)` - Retrieve state
- `backfill_existing_users(org_id)` - Initialize for all members

**Eligibility Detection Logic:**
```
IF user is new (created < 7 days ago):
  → eligible for 'onboarding'
IF org has 0 documents:
  → eligible for 'upload_documents'
IF org has documents but 0 requirements linked:
  → eligible for 'link_requirements'
IF org has requirements but low coverage (<30%):
  → eligible for 'evidence_collection'
ELSE:
  → No eligible walkthroughs
```

### 3.3 API Endpoints

**Routes:**
- `GET /api/walkthroughs/state/<walkthrough_key>` - Get current state
- `POST /api/walkthroughs/state/<walkthrough_key>/start` - Start walkthrough
- `POST /api/walkthroughs/state/<walkthrough_key>/next-stage` - Next stage
- `POST /api/walkthroughs/state/<walkthrough_key>/skip-stage` - Skip stage
- `POST /api/walkthroughs/state/<walkthrough_key>/complete` - Complete
- `POST /api/walkthroughs/state/<walkthrough_key>/dismiss` - Dismiss
- `GET /api/walkthroughs/eligible` - List eligible walkthroughs for user
- `POST /api/walkthroughs/backfill` - (admin only) Backfill org users

**Response Format:**
```json
{
  "success": true,
  "state": {
    "walkthrough_key": "onboarding",
    "state": "in_progress",
    "current_stage": 2,
    "completion_percentage": 50.0,
    "eligible": true,
    "next_stage_url": "/api/walkthroughs/state/onboarding/next-stage"
  }
}
```

### 3.4 Dashboard Integration

**Data to Pass to Template:**
```python
{
    'walkthrough_state': walkthrough_state_obj,
    'eligible_walkthroughs': [
        {'key': 'onboarding', 'title': 'Getting Started', 'description': '...'},
        {'key': 'upload_documents', 'title': 'Upload Documents', 'description': '...'},
    ],
    'show_walkthrough_banner': bool,  # Auto-triggered + not dismissed
}
```

**UI Component:**
- Soft banner at top of dashboard: "📚 New to Cenaris? Start the walkthrough"
- Help menu item: "Show Walkthroughs"
- Launching modal/sidebar with stage display

### 3.5 Migration

```python
# versions/XXXX_add_walkthrough_state.py
def upgrade():
    op.create_table(
        'walkthrough_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        # ... all columns ...
    )
    # Create indexes and constraints

def downgrade():
    op.drop_table('walkthrough_states')
```

### 3.6 Tests

**Unit Tests:**
- `test_create_walkthrough_state()`
- `test_detect_eligible_walkthroughs()`
- `test_start_walkthrough()`
- `test_complete_walkthrough()`
- `test_dismiss_temporary()`
- `test_backfill_users()`

**Integration Tests:**
- `test_walkthrough_flow_end_to_end()`
- `test_api_endpoints()`
- `test_dashboard_with_state()`

---

## 4. Implementation Schedule

| Phase | Scope | Effort | Priority | Status |
|-------|-------|--------|----------|--------|
| **1** | Core model, service, API, dashboard | 2-3 days | 🔴 MUST | ✅ COMPLETE |
| **2** | Stages, sequencing, UI components | 3-4 days | 🔴 MUST | ⬜ Ready |
| **3** | Personalization, segments, analytics | 2-3 days | 🟡 SHOULD | ⬜ Not Started |
| **4** | Admin tools, mobile, accessibility | 2-3 days | 🟢 NICE | ⬜ Not Started |
| **5** | Gamification, badges, streaks | 1-2 days | 🔵 OPTIONAL | ⬜ Not Started |

---

## 5. Decision Matrix

### What We're Implementing

**✅ Phase 1: APPROVED FOR IMPLEMENTATION**
- [x] Database model
- [x] Migration
- [x] Service layer
- [x] API endpoints
- [x] Dashboard integration
- [x] Basic tests

**✅ Phase 2: APPROVED FOR IMPLEMENTATION**
- [x] Stage model
- [x] Stage sequencing
- [x] Spotlight/highlight (DOM targeting)
- [x] Step tracking
- [x] Completion logic
- [x] UI components (modal/sidebar)
- [x] Persistence (save progress per stage)
- [ ] ~~Admin triggers~~ (EXCLUDED)
- [ ] ~~Email notifications~~ (EXCLUDED)

**✅ Phase 3: ANALYTICS ONLY**
- [x] Analytics events (walkthrough:started, walkthrough:completed, stage:skipped)
- [ ] ~~User segments~~ (defer)
- [ ] ~~Personalization per role~~ (defer)

**⏸️ Phase 4-5: DEFERRED**

---

## 6. Next Steps

1. **Review this plan** - Confirm phases/priorities
2. **Approve Phase 1** - Lock in core implementation
3. **Start implementation** - Create model → migration → service → API → UI
4. **Update this file** - Mark completed items as ✅
5. **Execute phases sequentially** - Phase 2, 3, 4, 5 in order

---

## 7. Decisions Locked ✅

- ❌ Admin manual triggers - NOT IMPLEMENTING
- ❌ Email notifications - NOT IMPLEMENTING  
- ✅ Analytics tracking - YES, track completion in engagement metrics
- ✅ Default content - AI-generated reasonable defaults
- ❌ Feedback collection - NOT IMPLEMENTING

---

## 8. Default Walkthrough Content

### Walkthrough: "Getting Started" (for new users < 7 days old)
1. **Welcome** - "Welcome to Cenaris Compliance Management"
2. **Upload Documents** - "Upload your first policy or compliance document"
3. **Analyze Documents** - "AI reviews documents automatically"
4. **Link Requirements** - "Map evidence to NDIS requirements"
5. **View Dashboard** - "Track your organization's compliance progress"

### Walkthrough: "Strengthen Your Evidence" (when coverage < 30%)
1. **Review Gaps** - "See which requirements need evidence"
2. **Find Existing** - "Search your document library"
3. **Upload New** - "Add missing compliance documents"
4. **Auto-Link** - "AI matches documents to requirements automatically"
5. **Track Progress** - "Monitor your evidence coverage in real-time"

---

**Document Status:** 🟢 LOCKED - STARTING PHASE 1 IMPLEMENTATION

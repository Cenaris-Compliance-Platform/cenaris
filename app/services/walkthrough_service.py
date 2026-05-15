"""
Service for managing guided walkthroughs (onboarding, feature discovery, etc.)
Handles state tracking, eligibility detection, stage progression, and analytics events.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
import logging

from app import db
from app.models import WalkthroughState, WalkthroughStage, User, Organization, OrganizationRequirementAssessment
from app.services.analytics_service import analytics_service

logger = logging.getLogger(__name__)


class WalkthroughService:
    """
    Core service for walkthrough lifecycle management.
    
    Responsibilities:
    - Track user progress through walkthroughs (state, stages, completion)
    - Detect eligible users for walkthroughs (new users, low coverage orgs)
    - Manage dismissals and snoozes
    - Log analytics events for engagement tracking
    - Provide API layer for frontend
    """

    # Walkthrough definitions (used for eligibility detection and default content)
    WALKTHROUGHS = {
        'tour-dashboard': {
            'name': 'Dashboard Tour',
            'description': 'Learn the key areas of your Cenaris dashboard.',
            'focus': 'Quick orientation for the dashboard',
            'hint': 'Explore the upload area, recent documents, compliance stats, and navigation.',
            'target_audience': 'all_users',
            'total_stages': 6,
            'stages': [
                {
                    'title': 'Welcome to Cenaris',
                    'description': 'This is your command centre. Let\'s take a quick tour of the most important areas.',
                    'target_element': 'wt-dash-heading',
                    'placement': 'bottom',
                },
                {
                    'title': 'Navigation Bar',
                    'description': 'Use the top navigation to move between modules — AI Review, Repository, Policy Studio, and more.',
                    'target_element': 'wt-nav-main',
                    'placement': 'bottom',
                },
                {
                    'title': 'Upload Evidence',
                    'description': 'Drag and drop compliance documents here or click to browse. Supports PDF, DOC, DOCX, and images.',
                    'target_element': 'upload-documents',
                    'placement': 'top',
                },
                {
                    'title': 'Recent Documents',
                    'description': 'Your latest uploads appear here so you can quickly return to recent work.',
                    'target_element': 'wt-dash-recent-docs',
                    'placement': 'left',
                },
                {
                    'title': 'Compliance Stats',
                    'description': 'Track your overall compliance score and see exactly which requirements are missing or need review.',
                    'target_element': 'walkthrough-compliance-readiness',
                    'placement': 'top',
                },
                {
                    'title': 'Tour Complete!',
                    'description': 'You\'re all set. Explore AI Review, the Evidence Repository, and Policy Studio next.',
                    'target_element': None,
                    'placement': 'center',
                },
            ],
        },
        'tour-repository': {
            'name': 'Evidence Repository Tour',
            'description': 'Learn how to manage, filter, and review your compliance documents.',
            'focus': 'Document management and AI review',
            'hint': 'Upload, filter, bulk-download, and send documents for AI review from here.',
            'target_audience': 'all_users',
            'total_stages': 5,
            'stages': [
                {
                    'title': 'Evidence Repository',
                    'description': 'All your uploaded compliance documents live here. You can search, filter, and manage them.',
                    'target_element': 'wt-repo-header',
                    'placement': 'bottom',
                },
                {
                    'title': 'Filters & Search',
                    'description': 'Filter by type, framework, tags, or date to find exactly what you need.',
                    'target_element': 'wt-repo-filters',
                    'placement': 'bottom',
                },
                {
                    'title': 'Document Table',
                    'description': 'Select multiple documents using the checkboxes to bulk-download them as a ZIP.',
                    'target_element': 'wt-repo-table',
                    'placement': 'top',
                },
                {
                    'title': 'AI Review Column',
                    'description': 'Click "Review" on any document to send it for AI-powered compliance analysis.',
                    'target_element': 'wt-repo-ai-col',
                    'placement': 'left',
                },
                {
                    'title': 'Open AI Review',
                    'description': 'Use this button to jump directly to the AI Review module with your documents.',
                    'target_element': 'wt-repo-ai-btn',
                    'placement': 'bottom',
                },
            ],
        },
        'tour-ai-review': {
            'name': 'AI Review Tour',
            'description': 'Learn how to run AI-powered compliance checks on your documents.',
            'focus': 'AI document analysis',
            'hint': 'Select a framework, pick a document, and let AI score it against NDIS standards.',
            'target_audience': 'all_users',
            'total_stages': 5,
            'stages': [
                {
                    'title': 'AI Review',
                    'description': 'This is your dedicated workspace for deep compliance analysis using AI.',
                    'target_element': 'wt-ai-heading',
                    'placement': 'bottom',
                },
                {
                    'title': 'Select Document',
                    'description': 'Select a document from your repository to review.',
                    'target_element': 'storedDocId',
                    'placement': 'bottom',
                },
                {
                    'title': 'Advanced Options',
                    'description': 'Expand more options to select a specific document type or define common analysis questions.',
                    'target_element': 'aiReviewOptions',
                    'placement': 'top',
                },
                {
                    'title': 'Run Analysis',
                    'description': 'Click Analyze Document to start the AI review. Results appear within a few seconds.',
                    'target_element': 'runDemoBtn',
                    'placement': 'top',
                },
                {
                    'title': 'View Results',
                    'description': 'Your compliance score, strengths, gaps, and recommendations appear here.',
                    'target_element': 'wt-ai-results',
                    'placement': 'top',
                },
            ],
        },
        'tour-policy-studio': {
            'name': 'Policy Studio Tour',
            'description': 'Learn how to generate NDIS-compliant policy documents with AI.',
            'focus': 'AI policy generation',
            'hint': 'Choose a policy type, add context, and generate a draft Word document instantly.',
            'target_audience': 'all_users',
            'total_stages': 5,
            'stages': [
                {
                    'title': 'Policy Studio',
                    'description': 'Generate professional NDIS-compliant policies instantly using AI.',
                    'target_element': 'wt-ps-heading',
                    'placement': 'bottom',
                },
                {
                    'title': 'Select Policy Type',
                    'description': 'Choose the type of policy you need from the dropdown.',
                    'target_element': 'policyStudioType',
                    'placement': 'bottom',
                },
                {
                    'title': 'Advanced Options',
                    'description': 'Expand more options to select a requirement scope, organization profile, and custom instructions.',
                    'target_element': 'policyStudioAdvanced',
                    'placement': 'top',
                },
                {
                    'title': 'Generate Policy',
                    'description': 'Click Generate Policy to create a full draft. It will appear below in seconds.',
                    'target_element': 'wt-ps-generate',
                    'placement': 'top',
                },
                {
                    'title': 'Review & Download',
                    'description': 'Review the generated policy and download it as a Word document ready for review.',
                    'target_element': 'wt-ps-output',
                    'placement': 'top',
                },
            ],
        },
        'tour-requirements': {
            'name': 'Requirements Tour',
            'description': 'Learn how to track and manage your compliance requirements.',
            'focus': 'Requirements workboard',
            'hint': 'Track requirement status, add evidence links, and monitor your overall coverage.',
            'target_audience': 'all_users',
            'total_stages': 4,
            'stages': [
                {
                    'title': 'Requirements Workboard',
                    'description': 'All your NDIS compliance requirements are listed here with their current status.',
                    'target_element': 'wt-req-heading',
                    'placement': 'bottom',
                },
                {
                    'title': 'Filter Requirements',
                    'description': 'Filter by framework, status, or search by keyword to find specific requirements.',
                    'target_element': 'wt-req-filters',
                    'placement': 'bottom',
                },
                {
                    'title': 'Requirement Workboard',
                    'description': 'Each row shows the requirement, its owner, evidence coverage, and review due state.',
                    'target_element': 'wt-req-table',
                    'placement': 'top',
                },
                {
                    'title': 'Actions',
                    'description': 'Open individual requirements to edit them, assign owners, or update linked evidence.',
                    'target_element': 'wt-req-status',
                    'placement': 'left',
                },
            ],
        },
        'tour-audit-readiness': {
            'name': 'Audit Readiness Tour',
            'description': 'Learn how to identify and close evidence gaps before your audit.',
            'focus': 'Gap analysis and audit preparation',
            'hint': 'See your overall readiness score, identify gaps, and prioritise what to fix.',
            'target_audience': 'all_users',
            'total_stages': 4,
            'stages': [
                {
                    'title': 'Audit Readiness Centre',
                    'description': 'This is your audit preparation hub — see your evidence coverage against every NDIS standard.',
                    'target_element': 'wt-audit-heading',
                    'placement': 'bottom',
                },
                {
                    'title': 'Readiness Score',
                    'description': 'Your overall readiness score shows what percentage of requirements have sufficient evidence.',
                    'target_element': 'wt-audit-score',
                    'placement': 'bottom',
                },
                {
                    'title': 'Evidence Gap Table',
                    'description': 'This table lists every requirement with gaps. Sort by priority to tackle the most critical first.',
                    'target_element': 'readinessTable',
                    'placement': 'top',
                },
                {
                    'title': 'Filter Results',
                    'description': 'Filter by status or module to narrow down exactly what you want to focus on.',
                    'target_element': 'filterForm',
                    'placement': 'bottom',
                },
            ],
        },
    }

    def get_or_create_state(
        self,
        org_id: int,
        user_id: int,
        walkthrough_key: str,
        auto_triggered: bool = False
    ) -> WalkthroughState:
        """
        Get existing walkthrough state or create new one.
        
        Args:
            org_id: Organization ID
            user_id: User ID
            walkthrough_key: Key identifying walkthrough (e.g., 'getting-started')
            auto_triggered: Whether this was auto-triggered by system
            
        Returns:
            WalkthroughState instance
        """
        state = WalkthroughState.query.filter_by(
            organization_id=org_id,
            user_id=user_id,
            walkthrough_key=walkthrough_key
        ).first()

        if state:
            return state

        # Create new state
        walkthrough_def = self.WALKTHROUGHS.get(walkthrough_key, {})
        state = WalkthroughState(
            organization_id=org_id,
            user_id=user_id,
            walkthrough_key=walkthrough_key,
            state='not_started',
            current_stage=0,
            eligible=True,
            auto_triggered=auto_triggered,
            total_stages=walkthrough_def.get('total_stages', 0),
            completion_percentage=0,
            stages_completed=0,
        )
        db.session.add(state)
        db.session.flush() # flush to get state.id
        
        # Populate stages
        stages_def = walkthrough_def.get('stages', [])
        for i, stage_def in enumerate(stages_def):
            stage = WalkthroughStage(
                walkthrough_state_id=state.id,
                title=stage_def.get('title', f'Stage {i+1}'),
                description=stage_def.get('description', ''),
                target_element=stage_def.get('target_element'),
                stage_order=i,
                content=stage_def.get('description', ''), # Simplified for now
            )
            db.session.add(stage)

        db.session.commit()
        return state

    def detect_eligible_walkthroughs(
        self,
        org_id: int,
        user_id: int
    ) -> List[str]:
        """
        Detect which walkthroughs user is eligible for based on org/user context.
        
        Returns:
            List of walkthrough_keys the user is eligible for
        """
        eligible = []
        user = User.query.get(user_id)
        org = Organization.query.get(org_id)

        if not user or not org:
            return eligible

        from app.models import OrganizationAISettings
        settings = OrganizationAISettings.query.filter_by(organization_id=org_id).first()
        if settings and not settings.walkthroughs_enabled:
            return eligible

        # User requested to trigger for everyone regardless of account age or coverage
        eligible.extend([
            'tour-dashboard',
            'tour-repository',
            'tour-ai-review',
            'tour-policy-studio',
            'tour-requirements',
            'tour-audit-readiness'
        ])

        return eligible

    def _get_org_evidence_coverage_percentage(self, org_id: int) -> float:
        """
        Calculate organization's overall compliance coverage percentage.
        Coverage = (requirements with any assessed evidence / total requirements) * 100.
        A requirement is considered 'covered' if computed_score is not None and > 0,
        OR if at least one evidence_status field is not 'Not assessed'.
        """
        try:
            from sqlalchemy import func
            assessments = OrganizationRequirementAssessment.query.filter_by(
                organization_id=org_id
            ).all()

            if not assessments:
                return 0.0

            not_assessed = {'Not assessed', None, ''}
            requirements_with_evidence = sum(
                1 for a in assessments
                if (
                    (a.computed_score is not None and a.computed_score > 0)
                    or a.evidence_status_system not in not_assessed
                    or a.evidence_status_implementation not in not_assessed
                    or a.evidence_status_workforce not in not_assessed
                    or a.evidence_status_participant not in not_assessed
                )
            )
            total_requirements = len(assessments)

            if total_requirements == 0:
                return 0.0

            return (requirements_with_evidence / total_requirements) * 100
        except Exception as e:
            logger.error(f"Error calculating coverage for org {org_id}: {e}")
            return 0.0

    def start_walkthrough(self, state_id: int) -> bool:
        """
        Mark walkthrough as started (user clicked 'Start' or auto-triggered).
        
        Args:
            state_id: WalkthroughState ID
            
        Returns:
            Success boolean
        """
        try:
            state = WalkthroughState.query.get(state_id)
            if not state:
                logger.warning(f"Walkthrough state {state_id} not found")
                return False

            if state.state == 'not_started':
                state.state = 'in_progress'
                state.first_started_at = datetime.now(timezone.utc)
                state.last_interacted_at = datetime.now(timezone.utc)
                db.session.commit()

                # Log analytics event
                self._log_analytics_event(
                    state.organization_id,
                    state.user_id,
                    'walkthrough:started',
                    {
                        'walkthrough_key': state.walkthrough_key,
                        'triggered_by': 'auto' if state.auto_triggered else 'manual',
                    }
                )
                return True

            return True  # Already started
        except Exception as e:
            logger.error(f"Error starting walkthrough {state_id}: {e}")
            db.session.rollback()
            return False

    def reset_walkthrough(self, state_id: int) -> bool:
        """
        Reset walkthrough to initial state (for user restarting the tour).
        
        Args:
            state_id: WalkthroughState ID
            
        Returns:
            Success boolean
        """
        try:
            state = WalkthroughState.query.get(state_id)
            if not state:
                logger.warning(f"Walkthrough state {state_id} not found")
                return False

            state.state = 'not_started'
            state.current_stage = 0
            state.stages_completed = 0
            state.completion_percentage = 0
            state.completed_at = None
            state.dismissed_until = None
            state.permanently_dismissed = False
            
            db.session.commit()

            # Log analytics event
            self._log_analytics_event(
                state.organization_id,
                state.user_id,
                'walkthrough:reset',
                {
                    'walkthrough_key': state.walkthrough_key,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error resetting walkthrough {state_id}: {e}")
            db.session.rollback()
            return False

    def next_stage(self, state_id: int) -> bool:
        """
        Move to next stage of walkthrough.
        
        Args:
            state_id: WalkthroughState ID
            
        Returns:
            Success boolean
        """
        try:
            state = WalkthroughState.query.get(state_id)
            if not state:
                logger.warning(f"Walkthrough state {state_id} not found")
                return False

            if state.current_stage < state.total_stages - 1:
                state.current_stage += 1
                state.stages_completed += 1
                state.completion_percentage = int((state.stages_completed / state.total_stages) * 100)
                state.last_interacted_at = datetime.now(timezone.utc)
                db.session.commit()

                # Log analytics event
                self._log_analytics_event(
                    state.organization_id,
                    state.user_id,
                    'walkthrough:stage_advanced',
                    {
                        'walkthrough_key': state.walkthrough_key,
                        'current_stage': state.current_stage,
                        'total_stages': state.total_stages,
                    }
                )
                return True

            # Already at last stage
            return False
        except Exception as e:
            logger.error(f"Error advancing stage for walkthrough {state_id}: {e}")
            db.session.rollback()
            return False

    def complete_walkthrough(self, state_id: int) -> bool:
        """
        Mark walkthrough as completed.
        
        Args:
            state_id: WalkthroughState ID
            
        Returns:
            Success boolean
        """
        try:
            state = WalkthroughState.query.get(state_id)
            if not state:
                logger.warning(f"Walkthrough state {state_id} not found")
                return False

            state.state = 'completed'
            state.completed_at = datetime.now(timezone.utc)
            state.last_interacted_at = datetime.now(timezone.utc)
            state.completion_percentage = 100
            state.stages_completed = state.total_stages
            db.session.commit()

            # Log analytics event
            self._log_analytics_event(
                state.organization_id,
                state.user_id,
                'walkthrough:completed',
                {
                    'walkthrough_key': state.walkthrough_key,
                    'total_stages': state.total_stages,
                    'duration_seconds': int((state.completed_at - state.first_started_at).total_seconds()) if state.first_started_at else None,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error completing walkthrough {state_id}: {e}")
            db.session.rollback()
            return False

    def dismiss_walkthrough(self, state_id: int, hours: int = 24) -> bool:
        """
        Snooze walkthrough for specified hours (user can see it again later).
        
        Args:
            state_id: WalkthroughState ID
            hours: Hours to snooze (default 24)
            
        Returns:
            Success boolean
        """
        try:
            state = WalkthroughState.query.get(state_id)
            if not state:
                logger.warning(f"Walkthrough state {state_id} not found")
                return False

            state.state = 'dismissed'
            state.dismissed_until = datetime.now(timezone.utc) + timedelta(hours=hours)
            state.last_interacted_at = datetime.now(timezone.utc)
            db.session.commit()

            # Log analytics event
            self._log_analytics_event(
                state.organization_id,
                state.user_id,
                'walkthrough:dismissed',
                {
                    'walkthrough_key': state.walkthrough_key,
                    'current_stage': state.current_stage,
                    'snooze_hours': hours,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error dismissing walkthrough {state_id}: {e}")
            db.session.rollback()
            return False

    def permanently_dismiss_walkthrough(self, state_id: int) -> bool:
        """
        User permanently dismissed walkthrough (opt-out).
        
        Args:
            state_id: WalkthroughState ID
            
        Returns:
            Success boolean
        """
        try:
            state = WalkthroughState.query.get(state_id)
            if not state:
                logger.warning(f"Walkthrough state {state_id} not found")
                return False

            state.state = 'dismissed'
            state.permanently_dismissed = True
            state.last_interacted_at = datetime.now(timezone.utc)
            db.session.commit()

            # Log analytics event
            self._log_analytics_event(
                state.organization_id,
                state.user_id,
                'walkthrough:permanently_dismissed',
                {
                    'walkthrough_key': state.walkthrough_key,
                    'current_stage': state.current_stage,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error permanently dismissing walkthrough {state_id}: {e}")
            db.session.rollback()
            return False

    def skip_stage(self, state_id: int) -> bool:
        """
        Skip current stage and move to next (for optional/exploratory stages).
        
        Args:
            state_id: WalkthroughState ID
            
        Returns:
            Success boolean
        """
        try:
            state = WalkthroughState.query.get(state_id)
            if not state:
                logger.warning(f"Walkthrough state {state_id} not found")
                return False

            # Log analytics event
            self._log_analytics_event(
                state.organization_id,
                state.user_id,
                'walkthrough:stage_skipped',
                {
                    'walkthrough_key': state.walkthrough_key,
                    'skipped_stage': state.current_stage,
                    'total_stages': state.total_stages,
                }
            )

            # Advance to next stage
            return self.next_stage(state_id)
        except Exception as e:
            logger.error(f"Error skipping stage for walkthrough {state_id}: {e}")
            return False

    def get_eligible_walkthroughs_for_user(self, org_id: int, user_id: int) -> List[Dict]:
        """
        Get all eligible and active walkthroughs for a user (for dashboard display).
        
        Returns:
            List of walkthrough states with eligibility info
        """
        try:
            eligible_keys = self.detect_eligible_walkthroughs(org_id, user_id)
            walkthroughs = []

            for key in eligible_keys:
                state = self.get_or_create_state(org_id, user_id, key)
                
                # Skip if permanently dismissed or snoozed
                if state.permanently_dismissed:
                    continue
                
                if state.dismissed_until and state.dismissed_until > datetime.now(timezone.utc):
                    continue  # Still snoozed

                walkthrough_def = self.WALKTHROUGHS.get(key, {})
                walkthroughs.append({
                    'id': state.id,
                    'key': key,
                    'name': walkthrough_def.get('name', key),
                    'description': walkthrough_def.get('description', ''),
                    'state': state.state,
                    'current_stage': state.current_stage,
                    'total_stages': state.total_stages,
                    'completion_percentage': state.completion_percentage,
                })

            return walkthroughs
        except Exception as e:
            logger.error(f"Error getting eligible walkthroughs for user {user_id} in org {org_id}: {e}")
            return []

    def get_all_walkthroughs_for_user(self, org_id: int, user_id: int) -> List[Dict]:
        """
        Get all walkthroughs for a user, including dismissed/snoozed ones (for profile page).
        
        Returns:
            List of walkthrough states
        """
        try:
            eligible_keys = self.detect_eligible_walkthroughs(org_id, user_id)
            walkthroughs = []

            for key in eligible_keys:
                state = self.get_or_create_state(org_id, user_id, key)
                walkthrough_def = self.WALKTHROUGHS.get(key, {})
                walkthroughs.append({
                    'id': state.id,
                    'key': key,
                    'name': walkthrough_def.get('name', key),
                    'description': walkthrough_def.get('description', ''),
                    'state': state.state,
                    'current_stage': state.current_stage,
                    'total_stages': state.total_stages,
                    'completion_percentage': state.completion_percentage,
                    'permanently_dismissed': state.permanently_dismissed,
                })

            return walkthroughs
        except Exception as e:
            logger.error(f"Error getting all walkthroughs for user {user_id} in org {org_id}: {e}")
            return []

    def _log_analytics_event(
        self,
        org_id: int,
        user_id: int,
        event_type: str,
        event_data: Optional[Dict] = None
    ) -> None:
        """
        Log walkthrough-related analytics events.
        
        Args:
            org_id: Organization ID
            user_id: User ID
            event_type: Event type (e.g., 'walkthrough:started', 'walkthrough:completed')
            event_data: Additional event metadata
        """
        try:
            if hasattr(analytics_service, 'log_event'):
                analytics_service.log_event(
                    user_id=user_id,
                    organization_id=org_id,
                    event_type=event_type,
                    event_data=event_data or {}
                )
        except Exception as e:
            logger.error(f"Error logging analytics event {event_type}: {e}")


# Singleton instance
walkthrough_service = WalkthroughService()

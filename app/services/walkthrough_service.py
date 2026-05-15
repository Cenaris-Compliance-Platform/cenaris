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
        'getting-started': {
            'name': 'Getting Started',
            'description': 'New user onboarding walkthrough',
            'target_audience': 'new_users',
            'eligibility_criteria': {
                'max_user_days': 7,  # Users created less than 7 days ago
                'min_documents': 0,
            },
            'total_stages': 5,
        },
        'strengthen-evidence': {
            'name': 'Strengthen Your Evidence',
            'description': 'Guide users to improve compliance coverage',
            'target_audience': 'low_coverage_orgs',
            'eligibility_criteria': {
                'max_coverage_percentage': 30,  # Orgs with < 30% coverage
                'min_org_days': 30,  # Org created at least 30 days ago
            },
            'total_stages': 5,
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

        # Check 'getting-started' eligibility (new users < 7 days)
        if user.created_at:
            days_since_creation = (datetime.now(timezone.utc) - user.created_at).days
            if days_since_creation < 7:
                eligible.append('getting-started')

        # Check 'strengthen-evidence' eligibility (orgs with < 30% coverage, at least 30 days old)
        if org.created_at:
            days_since_org_creation = (datetime.now(timezone.utc) - org.created_at).days
            if days_since_org_creation >= 30:
                coverage_pct = self._get_org_evidence_coverage_percentage(org_id)
                if coverage_pct < 30:
                    eligible.append('strengthen-evidence')

        return eligible

    def _get_org_evidence_coverage_percentage(self, org_id: int) -> float:
        """
        Calculate organization's overall compliance coverage percentage.
        Coverage = (requirements with evidence / total requirements) * 100
        
        Returns:
            Coverage percentage (0-100)
        """
        try:
            assessments = OrganizationRequirementAssessment.query.filter_by(
                organization_id=org_id
            ).all()

            if not assessments:
                return 0.0

            requirements_with_evidence = sum(1 for a in assessments if a.has_evidence)
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

"""
Modular Prompt Manager for Dynamic System Prompt Injection

This module implements a context-aware prompt system that injects relevant
prompt sections based on conversation stage, avoiding the need for a single
large system prompt that can cause context loss.

Usage:
    from prompt_manager import PromptManager
    
    manager = PromptManager()
    system_prompt = manager.get_system_prompt(stage="startup")
"""

from typing import Dict, Optional, List
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConversationStage(Enum):
    """Enumeration of conversation stages"""
    STARTUP = "startup"
    MID_CONVERSATION = "mid_conversation"
    CLOSING = "closing"
    ACTIVE = "active"  # General active conversation


class PromptManager:
    """
    Manages modular system prompts with dynamic injection based on conversation stage.
    
    This class breaks down a large system prompt into smaller, contextual sections
    that are injected based on the conversation stage, reducing context window usage
    and improving maintainability.
    """
    
    def __init__(self):
        """Initialize the prompt manager with prompt sections"""
        self.prompt_sections: Dict[str, str] = {}
        self._load_prompt_sections()
    
    def _load_prompt_sections(self):
        """Load all prompt sections from system_prompt module"""
        from system_prompt import (
            CORE_IDENTITY,
            LANGUAGE_RULES,
            STARTUP_INSTRUCTIONS,
            MID_CONVERSATION_RULES,
            TOOL_USAGE_GUIDELINES,
            CLOSING_INSTRUCTIONS,
            FAQ_AND_INFO,
            CONVERSATION_FLOW,
            TONE_AND_STYLE
        )
        
        self.prompt_sections = {
            "core_identity": CORE_IDENTITY,
            "language_rules": LANGUAGE_RULES,
            "startup_instructions": STARTUP_INSTRUCTIONS,
            "mid_conversation": MID_CONVERSATION_RULES,
            "tool_usage": TOOL_USAGE_GUIDELINES,
            "closing": CLOSING_INSTRUCTIONS,
            "faq_info": FAQ_AND_INFO,
            "conversation_flow": CONVERSATION_FLOW,
            "tone_style": TONE_AND_STYLE,
        }
    
    def get_system_prompt(
        self,
        stage: str = "startup",
        datetime_info: Optional[Dict] = None,
        guardrails_context: str = "",
        include_sections: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None
    ) -> str:
        """
        Build a system prompt based on conversation stage and context.
        
        Args:
            stage: Conversation stage ("startup", "mid_conversation", "closing", "active")
            datetime_info: Optional datetime information dict
            guardrails_context: Optional guardrails context string
            include_sections: Optional list of specific sections to include (overrides stage logic)
            exclude_sections: Optional list of sections to exclude
        
        Returns:
            Complete system prompt string
        """
        # Always include core sections
        sections_to_include = ["core_identity", "language_rules"]
        
        # Add stage-specific sections
        if stage == ConversationStage.STARTUP.value or stage == "startup":
            sections_to_include.extend([
                "startup_instructions",
                "conversation_flow",
                "tone_style",
                "tool_usage",  # Tools available from start
            ])
        elif stage == ConversationStage.MID_CONVERSATION.value or stage == "mid_conversation":
            sections_to_include.extend([
                "mid_conversation",
                "tone_style",
                "tool_usage",
            ])
        elif stage == ConversationStage.CLOSING.value or stage == "closing":
            sections_to_include.extend([
                "closing",
                "tone_style",
            ])
        elif stage == ConversationStage.ACTIVE.value or stage == "active":
            sections_to_include.extend([
                "mid_conversation",
                "tone_style",
                "tool_usage",
            ])
        
        # Override with explicit include_sections if provided
        if include_sections:
            sections_to_include = include_sections
        
        # Remove excluded sections
        if exclude_sections:
            sections_to_include = [s for s in sections_to_include if s not in exclude_sections]
        
        # Build the prompt
        prompt_parts = []
        
        for section_name in sections_to_include:
            if section_name in self.prompt_sections:
                section_content = self.prompt_sections[section_name]
                if section_content.strip():
                    prompt_parts.append(section_content)
            else:
                logger.warning(f"Unknown prompt section: {section_name}")
        
        # Add datetime context if provided
        if datetime_info:
            datetime_section = self._format_datetime_context(datetime_info)
            prompt_parts.append(datetime_section)
        
        # Add guardrails context if provided
        if guardrails_context:
            prompt_parts.append(guardrails_context)
        
        # Join all parts
        system_prompt = "\n\n".join(prompt_parts)
        
        logger.debug(f"Built system prompt for stage '{stage}' with {len(sections_to_include)} sections, "
                    f"total length: {len(system_prompt)} chars")
        
        return system_prompt
    
    def _format_datetime_context(self, datetime_info: Dict) -> str:
        """Format datetime information as a prompt section"""
        return f"""
## CURRENT DATE AND TIME INFORMATION

**IMPORTANT: Use this information when answering questions about dates/times.**

- **Current Date**: {datetime_info.get('readable_date', 'N/A')} ({datetime_info.get('day_of_week', 'N/A')})
- **Current Date (YYYY-MM-DD format)**: {datetime_info.get('current_date', 'N/A')}
- **Current Time**: {datetime_info.get('current_time', 'N/A')} ({datetime_info.get('timezone', 'N/A')})
- **Tomorrow's Date**: {datetime_info.get('tomorrow_readable', 'N/A')} ({datetime_info.get('tomorrow_day', 'N/A')})
- **Tomorrow's Date (YYYY-MM-DD format)**: {datetime_info.get('tomorrow_date', 'N/A')}
- Current timezone is {datetime_info.get('timezone', 'N/A')}
"""
    
    def get_compact_prompt(self, context: Optional[Dict] = None) -> str:
        """
        Get a compact version of the prompt for mid-conversation updates.
        Only includes essential rules that need to be reinforced.
        
        Args:
            context: Optional context dict with conversation state
        
        Returns:
            Compact prompt string
        """
        compact_sections = [
            "core_identity",
            "language_rules",
            "mid_conversation",
        ]
        
        prompt_parts = []
        for section_name in compact_sections:
            if section_name in self.prompt_sections:
                section_content = self.prompt_sections[section_name]
                if section_content.strip():
                    prompt_parts.append(section_content)
        
        return "\n\n".join(prompt_parts)
    
    def update_system_instruction(
        self,
        llm_service,
        stage: str = "mid_conversation",
        datetime_info: Optional[Dict] = None,
        guardrails_context: str = ""
    ) -> bool:
        """
        Update the system instruction of an LLM service dynamically.
        
        Note: This may not be supported by all LLM services. Some services
        require the system instruction to be set at initialization.
        
        Args:
            llm_service: The LLM service instance to update
            stage: Conversation stage
            datetime_info: Optional datetime information
            guardrails_context: Optional guardrails context
        
        Returns:
            True if update was successful, False otherwise
        """
        try:
            new_prompt = self.get_system_prompt(
                stage=stage,
                datetime_info=datetime_info,
                guardrails_context=guardrails_context
            )
            
            # Try to update system instruction if the service supports it
            if hasattr(llm_service, 'system_instruction'):
                llm_service.system_instruction = new_prompt
                logger.info(f"Updated system instruction for stage: {stage}")
                return True
            elif hasattr(llm_service, 'update_system_instruction'):
                llm_service.update_system_instruction(new_prompt)
                logger.info(f"Updated system instruction via method for stage: {stage}")
                return True
            else:
                logger.warning("LLM service does not support dynamic system instruction updates")
                return False
        except Exception as e:
            logger.error(f"Error updating system instruction: {e}", exc_info=True)
            return False


# Global instance for convenience
_prompt_manager_instance: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create the global prompt manager instance"""
    global _prompt_manager_instance
    if _prompt_manager_instance is None:
        _prompt_manager_instance = PromptManager()
    return _prompt_manager_instance


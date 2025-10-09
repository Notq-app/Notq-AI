import os
import json
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate

from langchain_deepseek import ChatDeepSeek

try:
    from googlesearch import search
except ImportError:
    def fallback_search(query, num_results=3):
        print(f"Google search not available. Query was: {query}")
        return []
    search = fallback_search

class DailyWords(BaseModel):
    day: int = Field(..., description="Day number (1-7)")
    words: List[str] = Field(..., description="List of words to practice this day")
    notes: Optional[str] = Field(None, description="Special notes for this day")

class WeeklyPlan(BaseModel):
    week: int = Field(..., description="Week number")
    focus_area: str = Field(..., description="Main speech focus for this week (e.g., 'Basic sounds', 'Simple words')")
    daily_plans: List[DailyWords] = Field(..., description="Daily word plans for the week")
    weekly_goal: str = Field(..., description="What should be achieved by end of week")

class SpeechTherapyPlan(BaseModel):
    child_age: int = Field(..., description="Child's age in years")
    delay_level: str = Field(..., description="Level of speech delay (slight delay, medium delay, severe delay)")
    language: str = Field(..., description="Primary language")
    daily_time_minutes: int = Field(..., description="Available practice time per day in minutes")
    plan_duration_weeks: int = Field(..., description="Total plan duration in weeks")
    
    weekly_plans: List[WeeklyPlan] = Field(..., description="Week-by-week breakdown")



def _search_speech_therapy_resources(query: str, num_results: int = 3) -> List[str]:
    """Search for speech therapy resources and return relevant information."""
    try:
        search_results = []
        for result in search(query, num_results=num_results):
            search_results.append(result)
        return search_results
    except Exception as e:
        print(f"Search failed: {e}")
        return []

def _get_age_appropriate_guidelines(age: int) -> str:
    """Get age-appropriate speech development guidelines using Google search."""
    try:
        search_query = f"speech development milestones age {age} years children normal development"
        search_results = _search_speech_therapy_resources(search_query, num_results=5)
        
        if search_results:
            guidelines_text = f"Current research for age {age} speech development:\n"
            guidelines_text += "\n".join(search_results[:3])
            return guidelines_text
        else:
            basic_guidelines = {
                2: "Age 2: Basic words, simple combinations, family understanding",
                3: "Age 3: Vocabulary growth, short sentences, clearer speech",
                4: "Age 4: Complex sentences, storytelling, most sounds clear",
                5: "Age 5: Advanced grammar, abstract concepts, reading readiness",
                6: "Age 6: Mature speech patterns, reading skills, complex communication",
                7: "Age 7: Fluent reading, detailed narratives, advanced vocabulary",
                8: "Age 8: Adult-like speech, complex reasoning, academic language"
            }
            return basic_guidelines.get(age, f"Age {age}: Advanced communication development")
    except Exception as e:
        print(f"Error getting guidelines for age {age}: {e}")
        return f"Age {age}: Speech development guidelines (search unavailable)"

def _get_llm(temperature: float = 0.2):
    """Return Google Gemini via LangChain (requires DEEPSEEK_API_KEY in .env)."""
    load_dotenv()
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("Missing DEEPSEEK_API_KEY in .env for DeepSeek.")

    llm = ChatDeepSeek(
        model="distill-llama-8b_46e6iu",
        api_base="https://pangu.ap-southeast-1.myhuaweicloud.com/api/v2",
        temperature=temperature,
        api_key=api_key,
    )
    return llm
    # return ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=temperature, google_api_key=api_key)

def generate_speech_therapy_plan(
    child_age: int,
    delay_level: str,
    language: str = "English",
    daily_time_minutes: int = 15,
    plan_duration_weeks: int = 4,
    words_child_can_speak: str = "",
    additional_info: str = ""
):
    """Generate a structured speech therapy plan for children with speech delays."""
    try:
        parser = PydanticOutputParser(pydantic_object=SpeechTherapyPlan)
        
        age_guidelines = _get_age_appropriate_guidelines(child_age)
        
        search_query = f"speech therapy {delay_level} delay age {child_age} {language}"
        search_results = _search_speech_therapy_resources(search_query)
        search_context = "\n".join(search_results[:3]) if search_results else "No additional resources found"

        prompt = PromptTemplate(
            template="""
                You are a certified speech-language pathologist with 15+ years of experience working with children aged 2-8 who have speech delays.
                
                CRITICAL INSTRUCTIONS:
                - Create ONLY practical, evidence-based speech therapy plans
                - Use developmentally appropriate words for age {child_age}
                - Adjust complexity based on "{delay_level}" severity
                - Each day should have 3-7 words maximum (fewer for severe delays)
                - Words must be functional and meaningful to daily life
                - Progress should be gradual and achievable
                
                DELAY LEVEL GUIDELINES:
                - Slight delay: Start with 4-6 words/day, focus on clarity and expansion
                - Medium delay: Start with 2-4 words/day, emphasize basic communication needs
                - Severe delay: Start with 1-2 words/day, focus on foundational sounds
                
                CHILD PROFILE:
                - Age: {child_age} years old (CRITICAL: Words must match developmental stage)
                - Speech delay level: {delay_level}
                - Primary language: {language}
                - Daily practice time: {daily_time_minutes} minutes
                - Plan duration: {plan_duration_weeks} weeks
                
                LANGUAGE REQUIREMENTS:
                CRITICAL: Generate the ENTIRE plan in {language} language.
                - All word lists must be in {language}
                - All notes must be written in {language}
                - All weekly goals must be in {language}
                - All focus areas must be in {language}
                - If {language} is not English, provide words that are appropriate for {language} speaking children
                
                WORD SELECTION CRITERIA:
                1. High-frequency words child hears daily (mama, more, up, go)
                2. Functional communication needs (help, stop, yes, no)
                3. Early developing sounds first (p, b, m, t, d, n)
                4. Words that motivate the child (favorite foods, toys, activities)
                
                CRITICAL: WORDS TO SKIP
                The child can already speak these words: {words_child_can_speak}
                DO NOT include any of these words in the therapy plan since the child has already mastered them.
                Focus on NEW words that build upon their current abilities.
                
                PROGRESSION RULES:
                - Week 1: Establish core vocabulary foundation (excluding words child already knows)
                - Each subsequent week: Build on previous words + add 2-3 new ones
                - Repeat successful words across multiple days
                - Notes should be specific and actionable for parents
                
                EVIDENCE-BASED CONSIDERATIONS:
                {age_guidelines}
                
                RESEARCH CONTEXT:
                {search_context}
                
                ADDITIONAL CHILD INFO:
                {additional_info}
                
                OUTPUT REQUIREMENTS:
                - Each daily plan must have realistic word counts for the delay level
                - Notes must be specific, practical instructions for parents
                - Weekly goals should be measurable and achievable
                - Focus areas should progress logically (sounds → words → combinations)
                - IMPORTANT: ALL text output (words, notes, goals, focus areas) must be in {language}
                - If language is Arabic, use proper Arabic script and vocabulary
                - If language is not English, ensure cultural appropriateness of selected words
                
                Generate a plan that a parent can actually implement successfully at home with their {child_age}-year-old child who has {delay_level}.
                Remember: The entire plan must be written in {language} language.
                
                Schema to follow:
                {format_instructions}
            """,
            partial_variables={
                "child_age": child_age,
                "delay_level": delay_level,
                "language": language,
                "daily_time_minutes": daily_time_minutes,
                "plan_duration_weeks": plan_duration_weeks,
                "words_child_can_speak": words_child_can_speak or "None specified",
                "age_guidelines": age_guidelines,
                "additional_info": additional_info,
                "search_context": search_context,
                "format_instructions": parser.get_format_instructions(),
            },
        )

        llm = _get_llm(temperature=0.15)
        chain = prompt | llm | parser
        
        result = chain.invoke({})

        return {
            "success": True,
            "message": "Speech therapy plan generated successfully.",
            "plan": result.dict()
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to generate speech therapy plan: {e}",
            "plan": None
        }



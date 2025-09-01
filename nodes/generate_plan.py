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

class PlanStep(BaseModel):
    id: int = Field(..., description="Sequential step id starting at 1.")
    title: str = Field(..., description="Short name of the step.")
    description: str = Field(..., description="What to do in this step.")
    owner: Optional[str] = Field(None, description="Responsible person or role.")
    duration: Optional[str] = Field(None, description="Estimated duration, e.g., '2 days'.")
    dependencies: List[int] = Field(default_factory=list, description="List of step ids this depends on.")


class Plan(BaseModel):
    objective: str = Field(..., description="Primary objective of the plan.")
    assumptions: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    milestones: List[str] = Field(default_factory=list)
    steps: List[PlanStep] = Field(..., description="Ordered list of steps to execute.")
    risks: List[str] = Field(default_factory=list)
    mitigations: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list, description="How success will be measured.")
    timeline: Optional[str] = Field(None, description="Overall timeline summary.")
    notes: Optional[str] = Field(None)


def _get_llm(temperature: float = 0.2):
    """Return Google Gemini via LangChain (requires GOOGLE_API_KEY)."""
    load_dotenv()
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("Missing GOOGLE_API_KEY for Gemini.")
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temperature)


def generate_plan(
    system_prompt: str = "",
    context: str = "",
    objective: Optional[str] = None,
    constraints: Optional[List[str]] = None,
    steps_hint: Optional[int] = None,
):
    """Generate a structured plan from a system prompt and long-form context using LangChain.

    Returns a dict: { success, message, plan (parsed), raw }.
    """
    try:
        parser = PydanticOutputParser(pydantic_object=Plan)

        prompt = PromptTemplate(
            template="""
                {system_instructions}
                
                Schema instructions:
                {format_instructions}
                
                Context (for grounding):
                {context}
                
                Objective (if provided):
                {objective}

                Constraints (if any):
                {extra_constraints}
                
                Steps hint (if any):
                {steps_hint}
            """,
            partial_variables={
                "system_instructions": system_prompt,
                "context": context,
                "objective": objective,
                "extra_constraints": "\n".join(constraints or []) or "",
                "format_instructions": parser.get_format_instructions(),
                "steps_hint": f"Aim for approximately {steps_hint} steps." if steps_hint else ""
            },
        )

        llm = _get_llm(temperature=0.2)

        chain = prompt | llm | parser
        
        result = chain.invoke({})

        return {
            "success": True,
            "message": "Plan generated successfully.",
            "plan": result.dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to generate plan: {e}",
            "plan": None,
        }

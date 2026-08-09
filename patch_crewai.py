import sys
import logging
from typing import Any
from pydantic import BaseModel, ValidationError
from crewai.utilities.converter import Converter, handle_partial_json, ConverterError
from crewai import Agent

# Set up patch logger
logger = logging.getLogger("CrewAIPatch")
logger.setLevel(logging.INFO)
# Avoid duplicating logs if handlers already exist
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[CrewAI Patch] %(message)s"))
    logger.addHandler(handler)

# Save the original method just in case
original_coerce = Converter._coerce_response_to_pydantic

def patched_coerce_response_to_pydantic(self, response: Any) -> BaseModel:
    if isinstance(response, BaseModel):
        return response
    try:
        # First attempt: Try direct validation of raw response string
        return self.model.model_validate_json(response)
    except (ValidationError, Exception) as val_err:
        logger.info(f"Initial Pydantic validation failed: {val_err}. Launching LLM self-correction loop...")
        try:
            # Attempt LLM-based self-correction
            corrected_response = self.llm.call(
                [
                    {
                        "role": "user",
                        "content": (
                            f"The following JSON output failed Pydantic validation for the model '{self.model.__name__}'.\n\n"
                            f"Validation Error:\n{str(val_err)}\n\n"
                            f"Original output:\n{response}\n\n"
                            f"Please return ONLY the corrected valid JSON string conforming exactly to the expected schema. "
                            f"Do not wrap in markdown backticks (do not use ```json ... ```)."
                        )
                    }
                ]
            )
            
            cleaned_corrected = corrected_response.strip()
            # Safety check: strip markdown code block wrapper if the LLM ignored instructions
            if cleaned_corrected.startswith("```"):
                lines = cleaned_corrected.splitlines()
                if len(lines) >= 2:
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                cleaned_corrected = "\n".join(lines).strip()
                
            return self.model.model_validate_json(cleaned_corrected)
        except Exception as retry_err:
            logger.warning(f"LLM self-correction attempt failed: {retry_err}. Falling back to default JSON fixer...")
            logger.info("Extracting JSON block & executing correction loop if required...")
        
        # Lazy import json if needed
        import json
        
        # Create a dummy agent utilizing the converter's existing LLM instance
        dummy_agent = Agent(
            role="JSON Fixer",
            goal="Fix JSON validation and formatting errors",
            backstory="You are a JSON formatting validator. Your sole purpose is to convert raw strings into valid JSON conforming to schemas.",
            llm=self.llm,
            verbose=False
        )
        
        try:
            partial = handle_partial_json(
                result=response,
                model=self.model,
                is_json_output=False,
                agent=dummy_agent,
            )
        except Exception as e:
            logger.error(f"Fallback JSON correction loop encountered an error: {e}")
            raise ConverterError(f"Fallback correction failed: {e}") from e
            
        if isinstance(partial, BaseModel):
            return partial
        if isinstance(partial, dict):
            return self.model.model_validate(partial)
        if isinstance(partial, str):
            try:
                return self.model.model_validate_json(partial)
            except Exception as parse_err:
                raise ConverterError(
                    f"Failed to convert partial JSON result into Pydantic: {parse_err}"
                ) from parse_err
        raise ConverterError(
            "handle_partial_json returned an unexpected type."
        ) from None

# Apply the monkeypatch
Converter._coerce_response_to_pydantic = patched_coerce_response_to_pydantic
logger.info("Successfully monkeypatched Converter._coerce_response_to_pydantic to fix Agent=None TypeError.")

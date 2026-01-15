import os
import json
import httpx
import re
from dotenv import load_dotenv
from openai import AsyncOpenAI
from a2a.server.tasks import TaskUpdater
from a2a.types import Message, TaskState, Part, TextPart
from a2a.utils import get_message_text, new_agent_text_message

try:
    from messenger import Messenger
except ImportError:
    from .messenger import Messenger

load_dotenv()

async def search_fhir(base_url: str, resource_type: str, params: dict) -> str:
    """
    Search the FHIR server for resources.
    """
    if not base_url:
        return "Error: No FHIR base URL provided."
    
    url = f"{base_url.rstrip('/')}/{resource_type}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            return json.dumps(response.json())
    except Exception as e:
        return f"Error querying FHIR server: {str(e)}"

def parse_instruction(text: str) -> dict | None:
    """
    Heuristically parse the instruction to identify specific tasks.
    """
    # Heuristic: Look for "name ... dob ..." pattern for Patient Search
    # Example: "Find MRN for Brian Buchanan (DOB: 1954-08-10)" or "name Brian Buchanan and DOB of 1954-08-10"
    # We'll use a slightly more flexible regex to catch common variations
    
    # Matches: "name <Name> and DOB of <YYYY-MM-DD>" (Case insensitive)
    name_match = re.search(r"name\s+([\w\s]+?)\s+and\s+DOB\s+of\s+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    
    # Fallback/Alternative pattern matches could be added here
    # For now, implementing the specific requested pattern
    
    if name_match:
        return {
            "type": "search_patient",
            "name": name_match.group(1).strip(),
            "dob": name_match.group(2).strip()
        }

    # Check for another common pattern: "Find MRN for <Name> (DOB: <YYYY-MM-DD>)"
    mrn_match = re.search(r"Find\s+MRN\s+for\s+([\w\s]+?)\s+\(DOB:\s*(\d{4}-\d{2}-\d{2})\)", text, re.IGNORECASE)
    if mrn_match:
         return {
            "type": "search_patient",
            "name": mrn_match.group(1).strip(),
            "dob": mrn_match.group(2).strip()
        }

    # Task 2 Pattern: "What's the age of the patient with MRN of <ID>?"
    age_match = re.search(r"age of the patient with MRN of\s+(S\d+)", text, re.IGNORECASE)
    if age_match:
        return {
            "type": "get_patient_age",
            "mrn": age_match.group(1).strip()
        }

    # Task 3 Pattern: "measured the blood pressure for patient with MRN of <ID>, and it is "<BP>""
    bp_match = re.search(r"measured the blood pressure for patient with MRN of\s+(S\d+).*?is\s+\"([^\"]+)\"", text, re.IGNORECASE)
    if bp_match:
        return {
            "type": "record_vitals",
            "mrn": bp_match.group(1).strip(),
            "bp": bp_match.group(2).strip()
        }

    return None

class Agent:
    def __init__(self):
        self.messenger = Messenger()
        if os.getenv("NEBIUS_API_KEY"):
            self.api_key = os.getenv("NEBIUS_API_KEY")
            self.base_url = "https://api.studio.nebius.ai/v1/"
            self.model = os.getenv("NEBIUS_MODEL_NAME") or os.getenv("MODEL_NAME") or "deepseek-ai/DeepSeek-R1-0528"
        elif os.getenv("OPENROUTER_API_KEY"):
            self.api_key = os.getenv("OPENROUTER_API_KEY")
            self.base_url = "https://openrouter.ai/api/v1"
            self.model = os.getenv("OPENROUTER_MODEL_NAME") or os.getenv("MODEL_NAME") or "google/gemini-2.0-flash-exp:free"
        else:
            self.api_key = None
            self.model = None # Will cause error later if used
        
        self.client = None
        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
             print("Warning: No API key found for OpenRouter or Nebius.")

    async def run(self, message: Message, updater: TaskUpdater, task: "Task" = None) -> None:
        """Implement your agent logic here.

        Args:
            message: The incoming message
            updater: Report progress (update_status) and results (add_artifact)
            task: The current task object containing history

        Use self.messenger.talk_to_agent(message, url) to call other agents.
        """
        input_text = get_message_text(message)

        # 1. Payload Parsing
        try:
            payload = json.loads(input_text)
            # Check if it looks like the expected Green Agent payload
            if isinstance(payload, dict) and "instruction" in payload:
                instruction = payload.get("instruction")
                fhir_base_url = payload.get("fhir_base_url")
                system_context = payload.get("system_context")
            else:
                # Fallback for plain text or unexpected JSON structure
                instruction = input_text
                fhir_base_url = None
                system_context = None
        except json.JSONDecodeError:
            instruction = input_text
            fhir_base_url = None
            system_context = None

        await updater.update_status(
            TaskState.working, new_agent_text_message("Processing request...")
        )

        response_text = ""
        if not self.client:
            response_text = "Error: Agent not configured with API key."
        else:
            try:
                # 2. Heuristic Pre-Fetch
                heuristic_context = ""
                parsed_task = parse_instruction(instruction)
                
                # If we detected a supported task AND we have a FHIR URL, fetch immediately
                is_pre_fetched = False
                skip_tools = False

                if parsed_task and fhir_base_url:
                    if parsed_task["type"] == "search_patient":
                        await updater.update_status(
                            TaskState.working, new_agent_text_message(f"Detected Patient Search: Fetching data for {parsed_task['name']}...")
                        )
                        
                        # Direct fetch
                        name_parts = parsed_task["name"].split()
                        params = {
                            "name": name_parts if len(name_parts) > 1 else parsed_task["name"],
                            "birthdate": parsed_task["dob"]
                        }
                        data = await search_fhir(
                            fhir_base_url, 
                            "Patient", 
                            params
                        )
                        heuristic_context = f"\n[CONTEXT FROM FHIR (Pre-fetched)]:\n{data}\n"
                        is_pre_fetched = True
                        skip_tools = True # Task 1 optimization: Skip tools

                    elif parsed_task["type"] == "get_patient_age":
                        await updater.update_status(
                            TaskState.working, new_agent_text_message(f"Detected Age Check: Fetching patient {parsed_task['mrn']}...")
                        )
                        # Fetch by ID (assuming MRN maps to ID 'Sxxxx' in this benchmark per implementation plan)
                        params = {"_id": parsed_task["mrn"]} 
                        data = await search_fhir(fhir_base_url, "Patient", params)
                        heuristic_context = f"\n[CONTEXT FROM FHIR (Pre-fetched)]:\n{data}\n"
                        is_pre_fetched = True
                        skip_tools = True # Task 2 optimization: Skip tools (LLM can calc age from context)

                    elif parsed_task["type"] == "record_vitals":
                        await updater.update_status(
                            TaskState.working, new_agent_text_message(f"Detected Vitals Record: Fetching patient {parsed_task['mrn']} context...")
                        )
                        # Fetch by ID to provide valid reference context
                        params = {"_id": parsed_task["mrn"]}
                        data = await search_fhir(fhir_base_url, "Patient", params)
                        heuristic_context = f"\n[CONTEXT FROM FHIR (Pre-fetched)]:\n{data}\n"
                        is_pre_fetched = True
                        skip_tools = False # Task 3 optimization: DO NOT skip tools (LLM needs to POST)

                # 3. Context Injection & Prompt Construction
                system_prompt = "You are a helpful medical AI assistant. You are participating in a medical benchmark. Answer questions accurately and concisely."
                if system_context:
                    system_prompt += f"\n\nCurrent Context: {system_context}"
                
                # If we pre-fetched, we don't necessarily need the tool instruction as strictly, 
                # but we still tell it about validity.
                if fhir_base_url:
                    if is_pre_fetched:
                        system_prompt += f"\n\nRelevant FHIR data has been pre-fetched and provided below. Use this context to answer the user's question directly."
                    else:
                        system_prompt += f"\nYou have access to a FHIR server at: {fhir_base_url}\nWhen asked to retrieve patient information, ALWAYS use the provided FHIR server URL using the `search_fhir` tool. Do not hallucinate data."

                messages = [{"role": "system", "content": system_prompt}]
                
                # Handling History
                if task and task.history:
                     for msg in task.history:
                        # For now, we rely on the current instruction/payload.
                        pass

                user_content = instruction + heuristic_context
                messages.append({"role": "user", "content": user_content})

                # 4. Tool Configuration
                tools = []
                if fhir_base_url and not skip_tools:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": "search_fhir",
                            "description": "Search for resources on the FHIR server.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "resource_type": {
                                        "type": "string",
                                        "description": "The type of FHIR resource to search for (e.g., 'Patient', 'Observation', 'Condition')."
                                    },
                                    "params": {
                                        "type": "object",
                                        "description": "Key-value pairs for search parameters (e.g., {'name': 'John', 'birthdate': '1980-01-01'})."
                                    }
                                },
                                "required": ["resource_type", "params"]
                            }
                        }
                    })

                # 5. LLM Call
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools if tools else None,
                )
                
                message = completion.choices[0].message
                
                # Handle tool calls (Legacy path or if pre-fetch missed)
                if message.tool_calls:
                    messages.append(message) # Add the assistant's message with tool_calls
                    
                    for tool_call in message.tool_calls:
                        if tool_call.function.name == "search_fhir":
                            func_args = json.loads(tool_call.function.arguments)
                            resource_type = func_args.get("resource_type")
                            params = func_args.get("params")
                            
                            # Execute tool
                            tool_result = await search_fhir(fhir_base_url, resource_type, params)
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": "search_fhir",
                                "content": tool_result
                            })
                    
                    # Call LLM again with tool results
                    second_completion = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        # tools=tools # Optional
                    )
                    response_text = second_completion.choices[0].message.content
                else:
                    response_text = message.content

            except Exception as e:
                import traceback
                response_text = f"Error calling LLM: {str(e)}\n{traceback.format_exc()}"

        await updater.add_artifact(
            parts=[Part(root=TextPart(text=response_text))],
            name="Response",
        )

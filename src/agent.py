import os
import json
import httpx
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
        print("DEBUG: Agent.run called")
        input_text = get_message_text(message)
        print(f"DEBUG: Input text: {input_text[:100]}...")

        # 1. Payload Parsing
        try:
            payload = json.loads(input_text)
            # Check if it looks like the expected Green Agent payload
            if isinstance(payload, dict) and "instruction" in payload:
                instruction = payload.get("instruction")
                fhir_base_url = payload.get("fhir_base_url")
                system_context = payload.get("system_context")
                print(f"DEBUG: Parsed payload. FHIR URL: {fhir_base_url}")
            else:
                # Fallback for plain text or unexpected JSON structure
                instruction = input_text
                fhir_base_url = None
                system_context = None
                print("DEBUG: Payload not recognized as Green Agent payload.")
        except json.JSONDecodeError:
            instruction = input_text
            fhir_base_url = None
            system_context = None
            print("DEBUG: JSON decode error.")

        await updater.update_status(
            TaskState.working, new_agent_text_message("Processing request...")
        )

        response_text = ""
        if not self.client:
            print("DEBUG: No API key configured.")
            response_text = "Error: Agent not configured with API key."
        else:
            try:
                # 2. Context Injection
                system_prompt = "You are a helpful medical AI assistant. You are participating in a medical benchmark. Answer questions accurately and concisely."
                if system_context:
                    system_prompt += f"\n\nCurrent Context: {system_context}"
                if fhir_base_url:
                    system_prompt += f"\nYou have access to a FHIR server at: {fhir_base_url}\nWhen asked to retrieve patient information, ALWAYS use the provided FHIR server URL using the `search_fhir` tool. Do not hallucinate data."

                messages = [{"role": "system", "content": system_prompt}]
                
                # Handling History
                if task and task.history:
                     for msg in task.history:
                        # For now, we rely on the current instruction/payload.
                        pass

                messages.append({"role": "user", "content": instruction})

                # 3. Tool Configuration
                tools = []
                if fhir_base_url:
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

                # 4. LLM Call & Tool Execution Loop
                print("DEBUG: Calling LLM...")
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools if tools else None,
                )
                print("DEBUG: LLM returned.")
                
                message = completion.choices[0].message
                
                # Handle tool calls
                if message.tool_calls:
                    print(f"DEBUG: Tool calls: {len(message.tool_calls)}")
                    messages.append(message) # Add the assistant's message with tool_calls
                    
                    for tool_call in message.tool_calls:
                        if tool_call.function.name == "search_fhir":
                            func_args = json.loads(tool_call.function.arguments)
                            resource_type = func_args.get("resource_type")
                            params = func_args.get("params")
                            
                            print(f"DEBUG: Executing tool {tool_call.function.name} with params {params}")
                            # Execute tool
                            tool_result = await search_fhir(fhir_base_url, resource_type, params)
                            print(f"DEBUG: Tool result: {tool_result[:100]}...")
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": "search_fhir",
                                "content": tool_result
                            })
                    
                    # Call LLM again with tool results
                    print("DEBUG: Calling LLM with tool outputs...")
                    second_completion = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        # tools=tools # Optional: keep tools if you want multi-step, but maybe limit for now
                    )
                    response_text = second_completion.choices[0].message.content
                    print("DEBUG: Final response generated.")
                else:
                    response_text = message.content
                    print("DEBUG: No tool calls. Response generated.")

            except Exception as e:
                import traceback
                print(f"DEBUG: Exception: {str(e)}")
                traceback.print_exc()
                response_text = f"Error calling LLM: {str(e)}\n{traceback.format_exc()}"

        await updater.add_artifact(
            parts=[Part(root=TextPart(text=response_text))],
            name="Response",
        )

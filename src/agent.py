import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from a2a.server.tasks import TaskUpdater
from a2a.types import Message, TaskState, Part, TextPart
from a2a.utils import get_message_text, new_agent_text_message

from messenger import Messenger

load_dotenv()

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

        await updater.update_status(
            TaskState.working, new_agent_text_message("Processing request...")
        )

        response_text = ""
        if not self.client:
             response_text = "Error: Agent not configured with API key."
        else:
            try:
                # Build context from history
                messages = [{"role": "system", "content": "You are a helpful medical AI assistant. You are participating in a medical benchmark. Answer questions accurately and concisely."}]
                
                if task and task.history:
                    for msg in task.history:
                        role = "user" if msg.role == "user" else "assistant" # Map 'agent' to 'assistant'
                        if msg.role == "agent":
                             role = "assistant"
                        
                        text = get_message_text(msg)
                        if text:
                            messages.append({"role": role, "content": text})
                
                # Append current message if not already in history (it usually is, but checking just in case)
                # In A2A, the current message IS in task.history usually.
                # However, let's just trust task.history if it exists, otherwise use input_text.
                
                if not task or not task.history:
                     messages.append({"role": "user", "content": input_text})

                # Basic prompt - can be enhanced
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
                response_text = completion.choices[0].message.content
            except Exception as e:
                response_text = f"Error calling LLM: {str(e)}"

        await updater.add_artifact(
            parts=[Part(root=TextPart(text=response_text))],
            name="Response",
        )

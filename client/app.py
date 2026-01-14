import gradio as gr
import argparse
import sys
import os
import asyncio
import httpx
from uuid import uuid4

# Add parent directory to path to allow importing from src if needed, 
# although we will likely re-implement the basic send logic to keep client standalone-ish
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.messenger import send_message
except ImportError:
    # Fallback or re-implementation if src is not accessible
    # Copying essential parts from messenger.py to ensure standalone capability
    import json
    from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, Consumer
    from a2a.types import Message, Part, Role, TextPart, DataPart

    def create_message(*, role: Role = Role.user, text: str, context_id: str | None = None) -> Message:
        return Message(
            kind="message",
            role=role,
            parts=[Part(TextPart(kind="text", text=text))],
            message_id=uuid4().hex,
            context_id=context_id,
        )

    def merge_parts(parts: list[Part]) -> str:
        chunks = []
        for part in parts:
            if isinstance(part.root, TextPart):
                chunks.append(part.root.text)
            elif isinstance(part.root, DataPart):
                chunks.append(json.dumps(part.root.data, indent=2))
        return "\n".join(chunks)

    async def send_message(
        message: str,
        base_url: str,
        context_id: str | None = None,
        streaming: bool = False,
        timeout: int = 300,
        consumer: Consumer | None = None,
    ):
        async with httpx.AsyncClient(timeout=timeout) as httpx_client:
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
            agent_card = await resolver.get_agent_card()
            config = ClientConfig(httpx_client=httpx_client, streaming=streaming)
            factory = ClientFactory(config)
            client = factory.create(agent_card)
            if consumer:
                await client.add_event_consumer(consumer)

            outbound_msg = create_message(text=message, context_id=context_id)
            last_event = None
            outputs = {"response": "", "context_id": None}

            async for event in client.send_message(outbound_msg):
                last_event = event

            match last_event:
                case Message() as msg:
                    outputs["context_id"] = msg.context_id
                    outputs["response"] += merge_parts(msg.parts)
                case (task, update):
                    outputs["context_id"] = task.context_id
                    outputs["status"] = task.status.state.value
                    msg = task.status.message
                    if msg:
                        outputs["response"] += merge_parts(msg.parts)
                    if task.artifacts:
                        for artifact in task.artifacts:
                            outputs["response"] += merge_parts(artifact.parts)
                case _:
                    pass

            return outputs

async def chat(message, history, agent_url, state):
    if not message:
        return "", history, state

    context_id = state.get("context_id")
    
    # Append user message immediately
    history.append({"role": "user", "content": message})
    
    try:
        # Use a longer timeout for agent reasoning
        outputs = await send_message(
            message=message,
            base_url=agent_url,
            context_id=context_id,
            timeout=120 
        )
        
        response = outputs.get("response", "No response")
        new_context_id = outputs.get("context_id")
        
        # Update state
        state["context_id"] = new_context_id
        
        history.append({"role": "assistant", "content": response})
        return "", history, state
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        history.append({"role": "assistant", "content": error_msg})
        return "", history, state

def clear_conversation():
    return None, [], {} # Message, History, State

def build_ui(default_port, default_url):
    with gr.Blocks(title="Purple Agent Client", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Purple Agent Interaction Client")
        
        with gr.Row():
            with gr.Column(scale=3):
                agent_url = gr.Textbox(
                    label="Agent URL", 
                    value=default_url,
                    placeholder="http://localhost:9009"
                )
            with gr.Column(scale=1):
                new_chat_btn = gr.Button("New Conversation", variant="secondary")

        chatbot = gr.Chatbot(
            label="Conversation",
            height=500,
            show_label=True,
            avatar_images=(None, "https://api.iconify.design/carbon:bot.svg") 
        )
        
        msg_input = gr.Textbox(
            label="Your Message", 
            placeholder="Type a message and press Enter...",
            lines=2
        )
        
        send_btn = gr.Button("Send", variant="primary")
        
        # State to hold context_id
        state = gr.State({})

        # Event handlers
        submit_args = [msg_input, chatbot, agent_url, state]
        submit_outputs = [msg_input, chatbot, state]

        msg_input.submit(chat, submit_args, submit_outputs)
        send_btn.click(chat, submit_args, submit_outputs)
        
        new_chat_btn.click(
            clear_conversation,
            outputs=[msg_input, chatbot, state]
        )

    return demo

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Purple Agent Client")
    parser.add_argument("--port", type=int, default=7861, help="Port to run Gradio on")
    parser.add_argument("--agent-url", type=str, default="http://localhost:9009", help="URL of the Purple Agent")
    parser.add_argument("--share", action="store_true", help="Create a public share link")
    
    args = parser.parse_args()
    
    demo = build_ui(args.port, args.agent_url)
    print(f"Starting Gradio client on port {args.port} connecting to {args.agent_url}...")
    demo.queue().launch(server_port=args.port, share=args.share)

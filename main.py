


import dotenv
dotenv.load_dotenv()
from openai import OpenAI   
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool, ImageGenerationTool, CodeInterpreterTool
import base64



client = OpenAI()       


VECTOR_STORE_ID = "vs_6a2e3dc10dcc8191be0be21b8e0c4eb0"


if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name = "ChatGPT Clone",
        instructions = """
        You are a personal goal coach.

        Your role is to help the user make progress toward their personal goals by using two sources of information:

        The user's uploaded goal document
        Web search results when current or practical information is needed

        Core behavior:

        Always check the uploaded goal document first when the user asks about progress, advice, planning, motivation, or recommendations.
        Identify the user's stated goals, deadlines, habits, milestones, and preferred learning or action plan from the uploaded document.
        If the user's question would benefit from current information, practical examples, updated tools, recent best practices, or external references, perform a web search.
        Combine the user's personal goal document with web search results to give personalized, realistic, and actionable advice.
        Do not give generic advice before checking the goal document.
        If the goal document does not contain enough information, clearly say what is missing and ask one brief follow-up question.
        Keep responses supportive, concise, and practical.

        Response style:

        Speak like a friendly coach.
        Be encouraging but honest.
        Give specific next steps.
        Prefer short action plans over long explanations.
        When useful, structure the answer as:
        What your goal says
        What I found from web search
        Personalized recommendation
        Next small action

        Example workflow:
        User: Am I making good progress toward my AI agent study goal?

        Coach:
        First, I’ll check your uploaded goal document.

        According to your goal document, you want to study AI agents by learning the basics, practicing with tools, and building a simple agent project.

        I’ll also look up current learning recommendations for AI agents.

        Based on your goal and recent resources, I recommend focusing on three areas this week:

        Understand what AI agents are and how they use tools
        Practice prompt design for agent workflows
        Build one small agent that can search, summarize, or organize information

        Your next small action:
        Spend 30 minutes today learning how tool use works in AI agents, then write one example agent instruction prompt.
        """,
        tools=[
            WebSearchTool(),
            FileSearchTool(
                vector_store_ids=[VECTOR_STORE_ID],   
                max_num_results=3,    
            ),
            ImageGenerationTool(
                tool_config={
                    "type": "image_generation",
                    "quality": "low",
                    "output_format": "jpeg",
                    "moderation": "low",
                    "partial_images": 1,  
                }
            ),
            CodeInterpreterTool(
                tool_config={
                    "type":"code_interpreter",
                    "container": {
                        "type":"auto"
                    }
                }
            ),
        ]
    )

agent = st.session_state["agent"]   



if "session" not in st.session_state:      
    st.session_state["session"] = SQLiteSession(
        "chat-history", "chat-gpt-clone-memory.db"     
    )

session = st.session_state["session"]   

async def paint_history():
    messages = await session.get_items()

    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):  
                if message["role"] == "user":
                    content = message["content"]
                    if isinstance(content, str):
                        st.write(content)
                    elif isinstance(content, list):
                        for part in content:
                            if "image_url" in part:
                                st.image(part["image_url"])
                else: 
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"].replace("$", "\$"))
        if "type" in message:
            message_type = message["type"]
            if message_type == "web_search_call":
                with st.chat_message("ai"):
                    st.write("searched the web...")     
            elif message_type == "file_search_call":
                with st.chat_message("ai"):
                    st.write ("Searched your files...")
            elif message_type == "image_generation_call":
                image = base64.b64decode(message["result"])
                with st.chat_message("ai"):
                    st.image(image)
            elif message_type == "code_interpreter_call":
                with st.chat_message("ai"):
                    st.code(message["code"])
                


asyncio.run(paint_history())


def update_status(status_container, event):
    
    status_messages = {
        'response.web_search_call.completed' : ("Web search completed.", "complete"),
        'response.web_search_call.in_progress' : ("Starting Web search...", "running"),
        'response.web_search_call.searching' : ("Web search in progress...", "running"),
        
        'response.file_serarch_call.completed' : ("file search completed.", "complete"),
        'response.file_serarch_call.in_progress' : ("Starting file search...", "running"),
        'response.file_serarch_call.searching' : ("file search in progress...", "running"),

        'response.image_generation_call.generating' : ("Drawing image...", "running"),
        'response.image_generation_call.in_progress' : ("Drawing image...", "running"),

        'response.code_interpreter_call_code.done' : ("Ran code.", "complete"),
        'response.code_interpreter_call.completed' : ("Ran code.", "complete"),
        'response.code_interpreter_call.in_progress' : ("Running code.", "complete"),
        'response.code_interpreter_call.interpreting' : ("Running code.", "complete"),
        
        
        'response.completed' : ("", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)




async def run_agent(message): 
    with st.chat_message("ai"):
        status_container = st.status("모래시계", expanded=False) 
        code_placeholder = st.empty()
        image_placeholder = st.empty()
        text_placeholder = st.empty()
        response = ""
        code_response = ""

        st.session_state["code_placeholder"] = code_placeholder
        st.session_state["image_placeholder"] = image_placeholder
        st.session_state["text_placeholder"] = text_placeholder


        stream = Runner.run_streamed(agent, message, session=session)

    async for event in stream.stream_events():
        if event.type == "raw_response_event":

            update_status(status_container, event.data.type)
            if event.data.type == "response.output_text.delta":
                response += event.data.delta
                text_placeholder.write(response)  

            if event.data.type == "response.code_interpreter_call_code.delta":
                code_response += event.data.delta
                code_placeholder.code(code_response)   #streamlit의 기능임. code는 syntax highlight가 적용되어보임

            elif event.data.type == "response.image_generation_call.partial_image":
                image = base64.b64decode(event.data.partial_image_b64)
                image_placeholder.image(image)
            


prompt = st.chat_input(
    "Write a message for your assistant",
    accept_file=True,
    file_type=["txt", "jpg", "jpeg", "png"],
    )



if prompt: 

    if "code_placeholder" in st.session_state:  #계속 placeholder를 비우는게 아니라 새 입력을 받을때만 
        st.session_state["code_placeholder"].empty()
    if "image_placeholder" in st.session_state:
        st.session_state["image_placeholder"].empty()
    if "text_placeholder" in st.session_state:
        st.session_state["text_placeholder"].empty()

    for file in prompt.files:   
        if file.type.startswith("text/"):   
            with st.chat_message("ai"):
                with st.status("Uploading file...") as status:      
                    uploaded_file = client.files.create(
                        file=(file.name, file.getvalue()),    
                        purpose="user_data",   
                    )  
                    status.update(label="Attaching file...")
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORE_ID,
                        file_id=uploaded_file.id,
                    )
                    status.update(label="File Uploaded", state="complete")
        elif file.type.startswith("image/"):
            with st.status("Uploading image...") as status:
                file_bytes = file.getvalue()
                base64_data = base64.b64encode(file_bytes).decode("utf-8")
                data_uri = f"data:{file.type};base64,{base64_data}"
                asyncio.run(
                    session.add_items([
                        {
                            "role":"user",
                            "content" : [
                                {
                                    "type": "input_image",
                                    "detail": "auto",
                                    "image_url": data_uri,
                                }
                            ]
                        }
                
            ]))
                status.update(label="Image uploaded", state="complete")
            with st.chat_message("human"):
                st.image(data_uri)


    if prompt.text:
        with st.chat_message("human"):
            st.write(prompt.text)
        asyncio.run(run_agent(prompt.text))  
    
    




with st.sidebar:
    reset = st.button("Reset memory")   
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))   


import dotenv
dotenv.load_dotenv()
import time
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool


if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name = "ChatGPT Clone",
        instructions = """
        If the question is related to life coaching, do not answer based on your own knowledge; be sure to use a web search tool first and answer only based on the results.

        """,
        tools=[
            WebSearchTool()
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
                    st.write(message["content"])
                else: 
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"])
        if "type" in message and message["type"] == "web_search_call":
            with st.chat_message("ai"):
                st.write("searched the web...")     # 웹 서칭중이라는게 표시되도록 하기


asyncio.run(paint_history())


def update_status(status_container, event):
    
    status_messages = {
        'response.web_search_call.completed' : ("Web search completed.", "complete"),
        'response.web_search_call.in_progress' : ("Starting Web search...", "running"),
        'response.web_search_call.searching' : ("Web search in progress...", "running"),
        'response.completed' : ("", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)




async def run_agent(message): 
    with st.chat_message("ai"):
        status_container = st.status("모래시계", expanded=False) 
        text_placeholder = st.empty()
        response = ""
        stream = Runner.run_streamed(agent, message, session=session)

    async for event in stream.stream_events():
        if event.type == "raw_response_event":

            update_status(status_container, event.data.type)
            if event.data.type == "response.output_text.delta":
                response += event.data.delta
                text_placeholder.write(response)  


prompt = st.chat_input("Write a message for your assistant")

if prompt: 
    with st.chat_message("human"):
        st.write(prompt)
    asyncio.run(run_agent(prompt))  



with st.sidebar:
    reset = st.button("Reset memory")   
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))   

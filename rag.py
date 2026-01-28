# from langchain_core.runnables.history import RunnableWithMessageHistory
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_openai import ChatOpenAI
# from dotenv import load_dotenv
# from memory import get_session_history

# load_dotenv()

# # Create a prompt that includes history from memory
# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are a senior software engineer."),
#     MessagesPlaceholder(variable_name="history"),
#     ("human", "{input}"),
# ])

# # Define the LLM
# llm = ChatOpenAI(
#     model="gpt-4o-mini",
#     temperature=0.2
# )

# # Create a combined prompt+LLM pipeline
# chain = prompt | llm

# # Wrap with memory support
# with_history = RunnableWithMessageHistory(
#     chain,
#     get_session_history,
#     input_messages_key="input",
#     history_messages_key="history",
# )


# def ask_question(vectorstore, question: str, session_id: str):
#     # 1. Retrieve RAG context like before
#     docs = vectorstore.similarity_search(question, k=20)
#     context = "\n\n".join(doc.page_content for doc in docs)

#     # 2. Prepare combined question + context
#     combined_input = f"{question}\n\nRepository Context:\n{context}"

#     # 3. Invoke the model with history handling
#     result = with_history.invoke(
#         {"input": combined_input},
#         config={"configurable": {"session_id": session_id}}
#     )

#     answer = result.content
#     return {"answer": answer, "follow_ups": []}


# rag.py

from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from memory import get_session_history

load_dotenv()

# Prompt remains untouched
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior software engineer."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

chain = prompt | llm

with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)


def ask_question(vectorstore, question: str, session_id: str, context=None):
    """
    session_id is treated as conversation_id.
    No RAG logic is changed.
    """
    docs = vectorstore.similarity_search(question, k=20)
    context = "\n\n".join(doc.page_content for doc in docs)

    combined_input = f"{question}\n\nRepository Context:\n{context}"

    result = with_history.invoke(
        {"input": combined_input},
        config={"configurable": {"session_id": session_id}}
    )

    answer = result.content
    return {"answer": answer, "follow_ups": []}

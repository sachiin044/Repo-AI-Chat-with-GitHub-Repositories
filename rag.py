from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from followups import generate_followups


PROMPT = """
You are a senior software engineer.

Answer STRICTLY using the provided repository context.

Repository Context:
-------------------
{context}
-------------------

Question:
{question}

Explain clearly and technically.
"""

def ask_question(vectorstore, question: str):
    docs = vectorstore.similarity_search(question, k=20)
    context = "\n\n".join(doc.page_content for doc in docs)

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=PROMPT
    )

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2
    )

    answer = llm.invoke(
        prompt.format(context=context, question=question)
    ).content

    followups = generate_followups(question, answer)

    return {
        "answer": answer,
        "follow_ups": followups
    }

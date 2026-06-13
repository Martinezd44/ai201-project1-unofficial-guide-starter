"""
app.py — Milestone 5: grounded generation + interface
Connects retrieval (embed_and_retrieve.retrieve) to Groq's llama-3.3-70b.
 
Grounding is enforced two ways, per planning.md "What Can Go Wrong":
  1. System prompt instructs answer-from-context-only + the domain mitigations
     (hedge by sample size, surface contradictions, refuse when unsupported,
      only attribute claims to professors named in the retrieved chunks).
  2. Source attribution is built PROGRAMMATICALLY from retrieved metadata,
     not left to the LLM to promise — the checklist requires this.
 
Setup:
    pip install groq gradio python-dotenv
    echo GROQ_API_KEY=your_key_here > .env   # get a free key at console.groq.com
 
Run:
    python app.py            # launches Gradio at http://localhost:7860
    python app.py --cli      # terminal mode, no browser
"""
 
import argparse
import os
 
from dotenv import load_dotenv
from groq import Groq
 
from Embed_and_retrieve import retrieve, TOP_K
 
load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"
 
# Distance above this = too weak to trust as supporting evidence.
# Cosine distance; planning.md / checklist treat >0.5 as a weak match.
RELEVANCE_THRESHOLD = 0.5
 
SYSTEM_PROMPT = """You are an unofficial guide to Montclair State University professors, \
answering ONLY from student reviews provided to you in each query.
 
Rules you must follow:
1. Use ONLY the information in the provided reviews. If they do not contain enough \
information to answer, say exactly: "I don't have enough information on that in my \
reviews." Do not use any outside or general knowledge about professors or courses.
2. Only make claims about a professor when a provided review explicitly names that \
professor. Never attribute one professor's review to another.
3. Reflect the number of reviews. If only one student is quoted, say "a student says..."; \
if several agree, you may say "students report...". Do not present a single opinion as \
a general consensus.
4. When reviews disagree, present BOTH sides ("opinions are mixed: some students say X, \
others say Y") instead of picking one.
5. Be concise and factual. These are subjective student opinions, not official facts — \
frame them as such."""
 
 
def build_context(hits):
    """Format retrieved chunks for the prompt. Returns (context_str, usable_hits)."""
    usable = [h for h in hits if h["distance"] <= RELEVANCE_THRESHOLD]
    if not usable:
        return "", []
    lines = []
    for i, h in enumerate(usable, 1):
        lines.append(f"[Review {i}] {h['text']}")
    return "\n\n".join(lines), usable
 
 
def ask(question: str, k: int = TOP_K) -> dict:
    """End-to-end: retrieve -> ground -> generate. Returns answer + sources."""
    hits = retrieve(question, k=k)
    context, usable = build_context(hits)
 
    # Grounding guard BEFORE calling the LLM: if nothing clears the relevance
    # bar, refuse here rather than feeding weak context and hoping the model
    # declines. This is the negative-test behavior the checkpoint requires.
    if not usable:
        return {
            "answer": "I don't have enough information on that in my reviews.",
            "sources": [],
            "hits": hits,
        }
 
    user_msg = (
        f"Student reviews:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer using only the reviews above."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,  # low: we want faithful, not creative
    )
    answer = resp.choices[0].message.content
 
    # Source attribution built from metadata — NOT from the LLM's text.
    sources = []
    for h in usable:
        m = h["metadata"]
        label = m.get("source_file") or m.get("source") or h["id"]
        prof = m.get("professor", "")
        tag = f"{prof} — {label}" if prof else label
        if tag not in sources:
            sources.append(tag)
 
    return {"answer": answer, "sources": sources, "hits": usable}
 
 
# ---------------------------------------------------------------- interfaces
def run_cli():
    print("MSU Professor Guide (Ctrl+C to quit)\n")
    while True:
        try:
            q = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not q:
            continue
        result = ask(q)
        print("\n" + result["answer"])
        if result["sources"]:
            print("\nSources:")
            for s in result["sources"]:
                print(f"  - {s}")
        print("\n" + "-" * 50)
 
 
def run_gradio():
    import gradio as gr
 
    def handle_query(question):
        if not question.strip():
            return "Ask a question about an MSU professor.", ""
        result = ask(question)
        sources = "\n".join(f"• {s}" for s in result["sources"]) or "(no sources)"
        return result["answer"], sources
 
    with gr.Blocks(title="MSU Professor Guide") as demo:
        gr.Markdown("# Unofficial MSU Professor Guide\n"
                    "Answers come only from student reviews. Opinions are subjective.")
        inp = gr.Textbox(label="Your question",
                         placeholder="e.g. Is attendance mandatory for Professor Boddu?")
        btn = gr.Button("Ask", variant="primary")
        answer = gr.Textbox(label="Answer", lines=6)
        sources = gr.Textbox(label="Sources (retrieved reviews)", lines=4)
        btn.click(handle_query, inputs=inp, outputs=[answer, sources])
        inp.submit(handle_query, inputs=inp, outputs=[answer, sources])
 
    demo.launch()
 
 
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cli", action="store_true", help="terminal mode instead of Gradio")
    args = p.parse_args()
    if args.cli:
        run_cli()
    else:
        run_gradio()
 
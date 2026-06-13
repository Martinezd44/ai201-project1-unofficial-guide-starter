# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

---This system answers questions about Montclair State University professors using real student reviews. Covering teaching style, grading , workload, attedance policies, exam structure and whether students would take the professor again. This knowledge is valuable ebcause the offical course catalog dscribes what a course covers but says nothing about the actual experience of taking it. How a professor grades, whteher attednace is enforced, how exams are weighter, or whether the workload is manageable. That information is hard to find thorugh official channels and is otherwise scattered across hundreds of indiviudal Rate My professors pages and buried. With no single place to ask a focused question like is attedance mandatory in a class.

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

#SourceTypeURL or file path1Rate My Professors — CoutrasRMP professor pagehttps://www.ratemyprofessors.com/professor/18906382Rate My Professors — VijayakanthanRMP professor pagehttps://www.ratemyprofessors.com/professor/29058133Rate My Professors — Hu-AuRMP professor pagehttps://www.ratemyprofessors.com/professor/29562794Rate My Professors — JenqRMP professor pagehttps://www.ratemyprofessors.com/professor/23629555Rate My Professors — BodduRMP professor pagehttps://www.ratemyprofessors.com/professor/24601506Rate My Professors — ZhouRMP professor pagehttps://www.ratemyprofessors.com/professor/30709317Rate My Professors — AntoniouRMP professor pagedata/raw/prof_antoniou_rmp.txt8Rate My Professors — Arif (STAT-230)RMP professor pagedata/raw/prof_arif_rmp.txt

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**

**Overlap:**

**Why these choices fit your documents:**

**Final chunk count:**

---
Chunking Strategy

Chunk size: ~250 tokens, capped against the real MiniLM tokenizer (not character
count). In practice one Rate My Professors review = one chunk, since reviews are short
and self-contained.

Overlap: 0 tokens for RMP reviews (each chunk is a complete review, so there is no
boundary to bridge). A ~50-token overlap is applied only when a long Reddit comment
exceeds the token cap and must be split mid-text.

Why these choices fit your documents: The corpus is dominated by short, self-contained
RMP reviews — each already expresses a complete opinion about one professor's grading,
workload, or teaching style. Splitting a review would separate a claim from its context
(e.g. "tough grader" from which course it applies to), and merging several reviews into
one chunk would blend contradictory opinions from different students into a single
embedding, hurting retrieval. So the natural unit is one review = one chunk, which makes
overlap unnecessary for that portion of the corpus. Each chunk is prepended with a
metadata prefix — [Professor | Department | Course | Rating] — so a retrieved chunk is
never an orphaned opinion with no referent, and the professor's name is part of the
embedded text so professor/course queries match.

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** 

**Production tradeoff reflection:**
Model used: all-MiniLM-L6-v2 via sentence-transformers — free, runs locally with no
API key or rate limits, produces 384-dimensional embeddings, and its 256-token input
limit pairs well with the ~250-token chunk cap so nothing is silently truncated. Vectors
are stored in ChromaDB using cosine distance.

Production tradeoff reflection: If cost weren't a constraint, the biggest factor for
this domain would be accuracy on informal, opinionated text — student reviews are full of
slang, sarcasm, and abbreviations ("prof," "ez A," "attendance didn't matter"), and a
larger model like OpenAI's text-embedding-3-large or Cohere's embed-v3 captures the
semantics of casual language better than a small distilled model. Context length matters
less here because chunks are deliberately small, but it would matter if whole Reddit
threads were chunked together. Multilingual support is worth weighing at MSU specifically,
since it is a Hispanic-Serving Institution and some students might query in Spanish;
MiniLM is English-only, while a model like multilingual-e5 would let a Spanish query
retrieve English reviews. The tradeoff against all of this is latency and cost: MiniLM
embeds queries in milliseconds locally, while API-hosted models add a network round-trip
and a per-token charge on every query, not just at indexing time. For a real deployment I
would benchmark a small/large pair on real student queries and only pay for the larger
model if retrieval quality measurably improved.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**

**How source attribution is surfaced in the response:**
System prompt grounding instruction: The model is instructed to use only the
information in the provided reviews and, when they don't contain enough to answer, to
respond with a fixed refusal ("I don't have enough information on that in my reviews")
rather than drawing on general knowledge. The prompt also enforces domain-specific
mitigations: only make claims about a professor when a retrieved review explicitly names
that professor (no cross-attribution); reflect sample size ("a student says..." vs
"students report...") so a single opinion isn't presented as consensus; and present both
sides when reviews disagree instead of picking one. Generation runs at temperature 0.2 to
keep answers faithful rather than creative.

How source attribution is surfaced in the response: Sources are built
programmatically from the metadata of the retrieved chunks after generation — not left
to the LLM to cite — so every answer's source list is guaranteed to be the documents
actually retrieved. In addition, a relevance filter drops any retrieved chunk with cosine
distance above 0.5 before the prompt is built; if no chunk clears that bar, the system
returns the refusal before the LLM is ever called, so it cannot fabricate an answer from
context it never received.

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

#QuestionExpected answerSystem response (summarized)Retrieval qualityResponse accuracy1Is attendance mandatory in Professor Boddu's CSIT100 class?Yes — reviews list attendance as mandatory2What do students say about classes that use zybooks?Mixed — one student found zybooks useless (Zhou), another used it neutrally in a positive review (Hu-Au)3How is the grade weighted in Professor Coutras's networks class?Exams are ~80% of the grade; no study guides provided

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**
"How is the grade weighted in Professor Coutras's computer
networks class?" (the correct answer was retrieved, but the result set was padded with
irrelevant professors)
**What the system returned:**
 The top result was the correct Coutras review (cosine
distance 0.383), but ranks #2–#5 returned reviews of different professors —
Vijayakanthan (0.455), Hu-Au (0.462), Jenq (0.503), Boddu (0.524) — two of them above the
0.5 weak-match threshold.
**Root cause (tied to a specific pipeline stage):** This is a retrieval-stage issue caused
by corpus size, not by chunking or embedding quality. With a small corpus, a top-k=5 query
returns a large fraction of the entire collection regardless of relevance, so after the
single genuinely-relevant chunk, the system fills the remaining slots with whatever vectors
are nearest in a sparse embedding space — even when those are unrelated professors. The
rising distance scores (0.38 → 0.52) show the relevance dropping off sharply after the
first result.

**What you would change to fix it:** Expand the corpus by collecting the remaining reviews
for each professor (and add Reddit threads), so that top-k=5 represents a small, selective
slice of a larger collection rather than half the data. The relevance threshold (0.5)
already prevents the weak padding chunks from being passed to the LLM as evidence, so the
generated answer stays grounded even when retrieval over-returns.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**
Writing the Chunking Strategy
section in planning.md before coding forced the "one review = one chunk + metadata prefix"
decision up front, which turned out to be the single most important design choice. Because
the strategy was already specified, the implementation was a direct translation rather than
guesswork, and the metadata-prefix rule (professor/course/rating embedded in the chunk
text) is what makes professor-specific queries retrieve the right reviews at all. Having
the embedding section also pinned down the 250-token cap, which avoided the silent
truncation that MiniLM's 256-token limit would otherwise cause.
**One way your implementation diverged from the spec, and why:**
 The planning doc treated
grounding as primarily a prompt-engineering problem ("instruct the model to refuse when
context doesn't answer the question"). In implementation I added a structural guard that
the spec didn't anticipate: a cosine-distance relevance filter that refuses before the
LLM is called when no retrieved chunk clears the 0.5 threshold. I diverged because relying
on the prompt alone leaves grounding to the model's discretion, whereas filtering in code
makes the refusal deterministic — the model physically cannot answer from context it was
never given.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*
- *What it produced:*
- *What I changed or overrode:*

What I gave the AI: My Chunking Strategy section from planning.md plus sample raw
review files, and asked it to implement the ingestion + chunking function.
What it produced: A chunk_documents() implementation that splits RMP files one
review per chunk, prepends the metadata prefix, and uses the real MiniLM tokenizer to
enforce the token cap, with a --inspect mode to print sample chunks.
What I changed or overrode: [FILL IN something you actually did — e.g. "I defined the
raw-file header format (PROFESSOR/COURSE/SOURCE/TYPE + --- separators) so chunking was
deterministic," or "I had to add boilerplate regexes when real RMP data left 'Helpful · 2'
junk in chunks," or "I confirmed the token cap included the metadata prefix so chunks
wouldn't exceed MiniLM's 256-token limit."]
**Instance 2**

- *What I gave the AI:*
- *What it produced:*
- *What I changed or overrode:*
What I gave the AI: My Embedding and "What Can Go Wrong" sections from planning.md, and
asked it to wire retrieval to the LLM with grounding enforced.
What it produced: A generation module using Groq's llama-3.3-70b with a system prompt
encoding the grounding rules and domain mitigations, programmatic source attribution from
chunk metadata, and a Gradio interface.
What I changed or overrode: [FILL IN — e.g. "I tuned the relevance threshold after
seeing valid reviews come back at distance 0.50–0.52 on real queries," or "I tested the
refusal behavior on an uncovered topic and confirmed it declined rather than
hallucinating."]
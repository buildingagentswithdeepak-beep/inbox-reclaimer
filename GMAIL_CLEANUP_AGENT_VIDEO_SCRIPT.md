# Gmail Cleanup Agent — YouTube Video Script

## Production brief

- **Suggested title:** Gmail Storage Full? I Built a Cleanup Agent with LangGraph
- **Alternative title:** I Built a Gmail Cleanup Agent—But It Doesn't Decide What You Delete
- **Target runtime:** Approximately 10 minutes, including demonstrations and pauses. Timings are edit targets, not a measured voiceover recording.
- **Presenter:** The creator, speaking in first person.
- **Audience:** Gmail users, builders and viewers interested in practical agent workflows.
- **Tone:** Conversational, honest and technically credible. Avoid corporate presentation language and exaggerated AI claims.
- **Central message:** The application finds cleanup candidates. The user decides what stays.
- **Deliverable:** Full narration, screen text, visuals, motion direction and transitions. This document is not a rendered video.

## Assumptions and accuracy boundaries

1. Example messages are fictional and visibly labelled **Illustrative demo**. Genuine recordings must mask personal addresses, subjects, message IDs where unnecessary, credentials and login links.
2. Google account storage is shared across Gmail, Drive and Photos. Inbox clutter alone does not establish the cause of a storage warning.
3. Show a genuine storage-full warning only if available. Otherwise label the recreated warning **Illustrative**. Do not fabricate a current upgrade price.
4. Cleanup does not guarantee avoiding a paid upgrade. Moving mail to Trash does not immediately free storage. This application does not provide permanent deletion.
5. The current application uses Python, LangGraph, the Gmail API and local SQLite persistence. **There is no runtime LLM integration.** Do not name GPT, Claude or another model as the application's classifier or decision-maker.
6. Analysis uses metadata and deterministic rules. Gmail category labels are existing provider labels, not categories inferred by an application LLM. A newsletter signal is not proof an email is unwanted.
7. Human approval is separate from analysis. Show an actual supported approval flow before mailbox effects. No automatic background cleanup, standing consent, automatic unsubscribe, replies or automatic folder creation is claimed.
8. The sender workflow inspects at most 1,000 candidates per run. Protected or otherwise ineligible messages may be excluded. This is not a guarantee of 1,000 successful changes.
9. A limited analysis is a sample in Gmail listing order, not necessarily the newest messages or a representative whole-mailbox survey.
10. An AI assistant helping develop this application is distinct from an LLM integrated into its runtime.

## Visual and sound language

- Use polished screen captures, restrained depth, realistic desktop footage and readable typography. Avoid cartoon robots or fake product dashboards.
- Use **blue** for analysis and suggestions, **amber** for human review, and **green** for approved/confirmed results.
- Keep explanatory motion graphics outside the captured product window. If a visual is illustrative, label it.
- Recurring strip: **Analyze → Identify → Suggest → Review → Organize**. Stop its progress at Review until the user visibly approves.
- Opening: crowded framing and layered notification sounds. Later: quieter audio, more negative space and steadier shots.
- Label accelerated footage **Sped up** and waiting-period cuts **Processing time shortened**. Do not make a slow operation appear instantaneous without disclosure.
- Keep all private identifiers out of the edit, including terminal scrollback and browser address bars.

---

## Scene 1 — Hook: Storage full, upgrade offered
**Time: 00:00–00:20**

### Voiceover

> Your Gmail inbox is overflowing. Then Google says your storage is full—and offers a paid upgrade.
>
> But before paying for more space, what's actually worth keeping?
>
> I built a Gmail Cleanup Agent to find potential clutter. You review it. You decide what goes.

### Visuals and animation

| Time | Shot | On-screen text and sound |
|---|---|---|
| 00:00–00:05 | Quick cuts: crowded Gmail inbox, repeated promotions, endless scrolling. An illustrative inbox count increases. | “An inbox that never stops growing.” Notification sounds accumulate. |
| 00:05–00:09 | Show the storage-full warning and upgrade offer. Use genuine footage or clearly label the recreation. | “Storage full. Upgrade?” Music briefly stops. |
| 00:09–00:13 | Cursor hesitates over the upgrade option. Freeze the screen, then pull back to the crowded inbox. | “What's actually worth keeping?” |
| 00:13–00:20 | Reveal Gmail Cleanup Agent; show analysis, suggestions and user review. No automatic disappearance of emails. | “Find clutter. Review first. Stay in control.” Music resumes. |

**Transition:** Match-cut from the inbox to the same screen on the creator's monitor.

**Director's note:** The hook asks whether cleanup is worthwhile; it must not imply a guaranteed free alternative to more storage.

---

## Scene 2 — Introduction: Why I built it
**Time: 00:20–01:00**

### Voiceover / on-camera dialogue

> I built this because cleaning an inbox sounds like a small task—until you actually start.
>
> You recognise a sender, open a message, wonder whether you might need it later, and repeat that decision over and over.
>
> Meanwhile, more email arrives.
>
> I didn't want a tool that just deleted aggressively. I wanted help finding things worth reviewing.
>
> One important distinction: Google storage also includes Drive and Photos. Cleaning Gmail may help, but it won't necessarily solve every storage problem—and moving messages to Trash doesn't immediately free space.

**On-screen text:** “Less repetitive review. Not less control.”

**Visual:** Medium shot at your desk, intercut with genuine inbox navigation. Show a simple Gmail / Drive / Photos shared-storage graphic during the caveat, without invented percentages.

**Animation:** Three labels appear: Find → Review → Decide.

**Transition:** Push into a single email row, then pull out to a simplified tidy inbox.

---

## Scene 3 — The problem: Clutter arrives gradually
**Time: 01:00–01:50**

### Voiceover

> An overloaded inbox usually doesn't happen in one dramatic moment.
>
> You subscribe to a newsletter. You buy something and start receiving offers. You sign up for an event or download a guide.
>
> Individually, none of that seems like a problem. But those messages keep arriving alongside the emails you actually need.
>
> The difficulty isn't just the number of messages. It's deciding which ones deserve your attention.
>
> And promotional doesn't automatically mean unwanted. You might be waiting for one store's offer and ignoring another.
>
> That's why “delete everything that looks like marketing” isn't a good enough solution. I needed a clearer starting point.

**On-screen text:** “Promotional ≠ automatically unwanted.”

**Visual:** Clean inbox → emails arriving → recurring promotions accumulating → crowded inbox. Keep one fictional important message visible as the clutter grows.

**Animation:** Gradually accelerate the arrival of fictional rows to show time passing. Never animate important mail being deleted.

**Transition:** Stop the accumulation and hold on the crowded inbox.

---

## Scene 4 — Introduce the agent
**Time: 01:50–02:20**

### Voiceover

> The Gmail Cleanup Agent analyzes email information and surfaces potential cleanup candidates.
>
> Instead of starting with an endless list and asking, “Where do I begin?” I get a more useful place to start reviewing.
>
> But a suggestion isn't a command. The application can't know everything that matters to me.
>
> So the workflow is simple: analyze, identify, suggest, review—and only then apply the cleanup I've approved.

**On-screen text:** “Suggestions first. Your decision next.”

**Visual:** Reveal the actual application or real report output. Avoid presenting an explanatory graphic as a working web application.

**Animation:** Introduce the five-step strip. Illuminate Analyze, Identify and Suggest in blue; leave Review amber.

**Transition:** Cut to the creator: “Here's what I actually built underneath.”

---

## Scene 5 — Technical foundation: Framework, not an LLM
**Time: 02:20–03:25**

### Voiceover

> Which framework did I use—and which language model decides what to delete?
>
> This version doesn't use a language model at runtime. It's a Python application built with LangGraph, the Gmail API and local SQLite storage.
>
> The analysis uses sender addresses, existing Gmail labels, message ages and estimated sizes. A newsletter header is a candidate signal, not proof that an email is unwanted.
>
> LangGraph coordinates the steps. The user still decides what to approve.
>
> There is a tradeoff: this version processes messages individually and makes repeated checks, so cleanup can be slow. That's something to improve, not hide in the edit.
>
> First, let's see the user workflow. After the demo, I'll connect the architecture to the main code files.

**On-screen text:** “Python + LangGraph + Gmail API + SQLite” followed by “No runtime LLM calls.”

**Visual:** Presenter with a concise stack overlay; briefly highlight `langgraph==1.2.8` in `pyproject.toml`. Save the full diagram and module tour for Scenes 10–11.

**Animation:** Reveal the framework names one at a time. Show metadata flowing into a report—not a chatbot reasoning about messages.

**Transition:** Move to the five-step user workflow strip.

---

## Scene 6 — How it works: The user workflow
**Time: 03:25–05:35**

### Step 1 — Analyze
**Time: 03:25–03:50**

**Voiceover:**

> First, I start a metadata analysis. This is the looking stage, not the deleting stage.
>
> For a bounded preview, I can inspect up to a thousand messages. That's a sample in Gmail's listing order—not necessarily the newest thousand or the entire mailbox.
>
> Starting analysis doesn't approve any cleanup.

**On-screen text:** “1. ANALYZE — No cleanup approved.”

**Recommended visual:** Actual analysis command and output. Mask identifiers. Use `--redact-subjects` in recorded analysis.

**Recommended animation:** Blue scanning accent outside the captured product window.

**Transition:** Scan accent resolves into highlighted report categories.

### Step 2 — Identify
**Time: 03:50–04:15**

**Voiceover:**

> Next, the application surfaces useful patterns: frequent senders, promotional categories and newsletter candidates.
>
> It isn't labelling every promotion as unwanted. It's helping me choose what to inspect first.
>
> A frequent sender could be valuable. A newsletter could be worth keeping. Those decisions still need context from me.

**On-screen text:** “2. IDENTIFY — Candidate, not a verdict.”

**Recommended visual:** Redacted sender-frequency report and fictional promotional rows.

**Recommended animation:** Blue outlines around candidate groups; other rows remain visible and unchanged.

**Transition:** Move from the analysis report to a supported sender-specific preview.

### Step 3 — Suggest
**Time: 04:15–04:40**

**Voiceover:**

> I can then choose an exact sender and create a cleanup preview.
>
> That saves a specific selection under a plan ID. It isn't permission to execute it.
>
> This preview searches the sender's mailbox messages; it isn't automatically restricted to the earlier analysis sample.
>
> Nothing disappears just because it appears in a suggestion.

**On-screen text:** “3. SUGGEST — Preview before action.”

**Recommended visual:** Actual `sender-cleanup` preview without `--execute`, followed by its saved plan ID and local report.

**Recommended animation:** Amber “Awaiting review” editorial badge.

**Transition:** Cut to the creator before showing approval.

### Step 4 — User reviews
**Time: 04:40–05:10**

**Voiceover:**

> I check the account, sender, selected messages and intended action.
>
> If I'm not comfortable with the selection, I cancel. I'm not trying to accept as many suggestions as possible.
>
> When I'm ready, I request execution of that same saved plan and approve it in the native window.
>
> The application checks protections again before acting, so some selected messages may still be skipped.

**On-screen text:** “4. REVIEW — You decide what stays.”

**Recommended visual:** Genuine confirmation flow. Pause long enough for viewers to understand the fields. Do not automate or fake human approval.

**Recommended animation:** Hold at the amber boundary until approval is visibly granted.

**Transition:** Advance to Organize only after the user confirms.

### Step 5 — Organize
**Time: 05:10–05:35**

**Voiceover:**

> Now the approved cleanup can run. In this application, that means moving eligible selected messages to Trash—not permanently deleting them.
>
> I check the recorded results afterward rather than assume every message moved.
>
> The goal isn't a magically empty inbox. It's less unnecessary clutter, based on decisions I made.

**On-screen text:** “5. ORGANIZE — Approved action → Check results.”

**Recommended visual:** Actual result followed by Gmail verification footage where available. Do not equate the local result display with a newly observed remote mailbox state.

**Recommended animation:** Only approved rows leave the illustrative selection. No new folders or labels are invented.

**Transition:** Return to camera: “Let's put that into a realistic example.”

---

## Scene 7 — Example: The newsletter you actually want
**Time: 05:35–06:55**

### Voiceover

> Imagine this is your inbox.
>
> There's a project update you need to answer, a receipt you want to keep, a newsletter you genuinely enjoy, and repeated promotions from a store you haven't visited in months.
>
> Everything is mixed together.
>
> The analysis shows that the store is a frequent sender. That gives me a useful place to start—not a reason to delete automatically.
>
> I preview the store's messages and decide which selection I'm comfortable cleaning up.
>
> But that favourite newsletter? I leave it alone.
>
> Even if it appears as a newsletter candidate in the analysis, that doesn't make it unwanted. A rule can identify a pattern without understanding its personal value.
>
> I approve the appropriate store selection, let the cleanup run, and inspect the result.
>
> The point isn't “the agent knows best.” It's “the application helped me make a better-informed decision with less manual searching.”

**Persistent label:** “Illustrative demo · fictional emails.”

**Example rows:**

- Project update — keep for follow-up.
- Purchase receipt — keep for reference.
- Favourite newsletter — user chooses to keep.
- Store promotions — preview separately; user decides whether to approve cleanup.

**Visual:** Intercut realistic fictional inbox footage and the actual supported sender-preview interface.

**Animation:** Keep the retained newsletter anchored in place throughout. Highlight it amber during the judgment moment, then return it to the normal inbox style.

**UI constraint:** Do not invent per-message deselection controls. If the application requires a narrower sender selection, show cancellation followed by a separate supported preview.

**Transition:** Freeze on the final example and pull into a before/after split screen.

---

## Scene 8 — Before vs. after
**Time: 06:55–07:35**

### Voiceover

> Here's the difference.
>
> On the left, relevant messages are mixed into the clutter.
>
> On the right, the inbox is easier to navigate after the user has reviewed and applied the appropriate cleanup.
>
> The improvement isn't that every email disappeared. It's that the user kept what mattered and cleared the selected clutter out of the way.
>
> And this is an inbox-organization result—not a promise that the Google storage warning has gone away. Messages in Trash still occupy storage until permanently removed.

**On-screen text:**

- BEFORE: “More clutter. More manual searching.”
- AFTER: “User-reviewed cleanup. Clearer view.”
- Small readable note: “Moving to Trash does not immediately free storage.”

**Visual:** Matched before/after captures from the same illustrative example or verified real run.

**Animation:** Animated split-screen divider sweeps across. Retained messages remain consistent. Do not animate a storage meter dropping unless a separate actual measurement supports it.

**Sound:** Gentle musical resolution, not an exaggerated success effect.

**Transition:** Scale the comparison down and introduce the benefit labels.

---

## Scene 9 — Benefits
**Time: 07:35–08:05**

### Voiceover

> For me, the practical value is less manual hunting for cleanup candidates, an easier starting point for organizing email, and less clutter after the actions I approve.
>
> The application uses metadata and rules to structure the work. LangGraph helps manage the workflow. And I remain responsible for deciding what stays.
>
> It doesn't need to pretend it understands my whole life to be useful.

**On-screen text:**

- Less manual searching
- Easier organization
- Reduced inbox clutter
- Clearer focus
- **Your decisions**

**Visual:** Alternate presenter footage and the real report.

**Animation:** Restrained text reveals. Hold “Your decisions” longer than the other labels.

**Transition:** The five-step strip expands into the architecture graphic: “Now let me connect that experience to the code.”

---

## Scene 10 — Simplified architecture: Follow one request
**Time: 08:05–08:45**

### Voiceover

> Here's the architecture in one picture.
>
> On the read side, the Gmail API supplies metadata. Python rules turn that into a report, and I can choose a sender for a saved cleanup preview.
>
> On the action side, native approval is the boundary. Only then can the executor recheck protections and send a supported change.
>
> LangGraph coordinates the workflow. SQLite stores checkpoints and separate journal evidence.
>
> They're different jobs: the graph tracks where we are; the journal records what was approved and attempted. There isn't an LLM making the decision.

### Graphic to show

```text
READ AND REVIEW — no mailbox changes
[Gmail API] → [Metadata + Python rules] → [Report]
                                            |
                                    User chooses sender
                                            |
                                    [Saved preview]
                                            |
                              [Native user approval]
============================================|================
APPROVED ACTION                             v
                              [Executor + fresh checks]
                                            |
                              [Supported Gmail change]
                                            |
                              [Verify + record outcome]

[LangGraph]  Workflow coordination, approval pause and resume
[SQLite]    Graph checkpoints + separate approval/operation journal
[LLM]       None at runtime
```

**On-screen text:** “Graph = workflow progress” / “Journal = approval and operation evidence.”

**Recommended visual:** A full-screen, clean architecture diagram, not tiny code. Use two zones: Read and Review in blue; Approved Action behind an amber approval boundary. A diagram label should say “Simplified architecture.”

**Recommended animation:** Reveal one arrow per narration beat. Stop at native approval before revealing the write path. Show LangGraph and SQLite as supporting components, not as permission-granting boxes. A feedback arrow from verification to the journal represents recording outcomes, not automatic retries.

**Sound:** Quiet, steady music with light accents on the two role labels.

**Transition:** Match each architecture box to its corresponding source file in the editor.

---

## Scene 11 — Main code overview: Where each responsibility lives
**Time: 08:45–09:35**

### Voiceover

> In the code, cli.py is the command-line entry point. It connects analysis commands to the read workflow.
>
> sync.py fetches the inventory; analytics.py calculates the sender rankings and other summaries. render.py turns those results into reports.
>
> Sender cleanup has its own modules. selection.py creates the bounded selection. commands.py connects the saved plan, native confirmation and execution.
>
> workflow.py manages approval pauses. executor.py performs the safety checks and operations. journal.py stores their evidence, while gmail.py handles the provider calls.
>
> That separation lets us test analysis, approval and execution independently. The framework coordinates the process; the application code enforces the safety rules.

### Code walkthrough shots

All paths below are relative to `src/inbox_reclaimer/`. Display each path in the editor breadcrumb so the root and `sender/` files cannot be confused.

| Time | File(s) to show | What to highlight | Viewer takeaway |
|---|---|---|---|
| 08:45–08:53 | `cli.py`, root `workflow.py` | `analyze(...)`, `run_read_workflow(...)` | Commands connect to a read-only workflow. |
| 08:53–09:03 | `sync.py`, `analytics.py`, `render.py` | `limited_scan(...)`, sender aggregation, report rendering | Fetching, calculation and presentation are separate. |
| 09:03–09:13 | `sender/selection.py`, `sender/commands.py` | Selection cap and `_perform(...)` approval-before-writer ordering | A saved selection is not authorization. |
| 09:13–09:25 | `sender/workflow.py`, `sender/executor.py` | `interrupt(...)`, safety checks and effect boundary | Pause for approval, then check before acting. |
| 09:25–09:35 | `sender/journal.py`, `sender/gmail.py` | Intent/outcome records and provider transport | Record evidence and separate it from network effects. |

**On-screen text:** “Fetch → Analyze → Present” then “Select → Approve → Execute → Record.”

**Recommended visual:** Capture the actual editor at a readable font size. Keep excerpts short and use prepared tabs; do not scroll through complete files. Put the narrated responsibility beside the code as an editorial caption. The table is an editing guide, not a wall of text to display at once.

**Recommended animation:** Carry the highlighted architecture box into a matching file-tab highlight. Use consistent colours to show which module handles each responsibility. No animated fake code or fabricated execution output.

**Recording boundary:** This is a code-reading tour. Do not run a live Trash command just to obtain B-roll. If showing tests, use the offline command in the reference section and retain the actual output.

**Transition:** Close the code inset and return to the presenter: “That's the system behind the cleanup.”

---

## Scene 12 — Closing and CTA
**Time: 09:35–10:00**

### Voiceover

> If your inbox fills up faster than you can clean it, a workflow like this can give you a better place to start.
>
> Analyze. Suggest. Review. Then act.
>
> What's your biggest source of email clutter? Tell me below.
>
> And subscribe if you'd like a deeper walkthrough of the LangGraph workflow, the approval checks, and what I'd improve next.

**On-screen text:** “What would you review first?”

**Visual:** Presenter followed by an end screen with subscription and related-video spaces.

**Animation:** Clean, restrained end-card movement. Use an actual available related video rather than implying an unpublished tutorial already exists.

**Sound:** Resolve the music under the final line.

---

## Technical reference for the editor

These details were checked against the application source while preparing the technical segment.

| Technology | Actual role | Source reference |
|---|---|---|
| Python 3.11+ | Application logic and CLI runtime | `pyproject.toml` |
| LangGraph 1.2.8 | Read workflow and sender approval/execution coordination | `workflow.py`, `sender/workflow.py` |
| langgraph-checkpoint-sqlite 3.0.3 | Durable graph checkpoints | Workflow modules |
| SQLite | Local cache, immutable plans, approval and operation evidence | `storage.py`, `sender/journal.py` |
| Gmail API client 2.170.0 | Metadata reads and supported approved mutations | `gmail.py`, `sender/gmail.py` |
| google-auth 2.40.2 | Credentials and actual grant verification integration | `gmail.py`, authorization modules |
| Typer 0.16.0 + Rich 14.0.0 | CLI commands and readable terminal output | `cli.py` |
| Tkinter | Separate native confirmation window | `sender/confirmation.py` |
| Portalocker 3.2.0 | Cooperating-process account locking | `profile.py` |
| Pytest | Automated behavior and contract verification | `tests/` |
| LLM | **None at application runtime** | No model integration in the current implementation |

### Simplified architecture graphic

```text
                        Gmail API
                            |
                      Metadata reads
                            |
               Python analysis and explicit rules
                            |
                  Local report / saved preview
                            |
                  User reviews the selection
                            |
                 Native confirmation (Tkinter)
                            |
                Validate approval and protections
                            |
               Supported, user-approved operation
                            |
                    Verify and record result

LangGraph: coordinates workflow and approval pauses
SQLite: checkpoints plus separate plan/approval/operation records
Portalocker: prevents conflicting cooperating account executors
LLM: none in this version
```

This is an explanatory diagram, not a literal full call graph. LangGraph alone does not grant consent, prevent duplicate effects or make Gmail and SQLite one atomic transaction. The application's journal, executor and transport enforce those contracts.

## Optional code-and-test B-roll

Show small readable excerpts rather than scrolling through entire files:

1. `pyproject.toml`: actual LangGraph and supporting dependencies.
2. `analytics.py`: sender grouping and use of existing category labels.
3. `sender/workflow.py`: `interrupt(...)` approval boundary.
4. `sender/commands.py`: approval persistence before writer construction.
5. `sender/executor.py`: intent → effect → verification → journal outcome.

For a fresh offline demonstration in a local PowerShell terminal:

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
& .\.venv\Scripts\python.exe -m pytest tests/test_analytics.py tests/test_sender_workflow.py tests/test_architecture.py -q --tb=short
```

Historical preparation evidence: the focused analytics, sender-workflow and architecture run returned **51 passed in 14.31 seconds**. This is not a new full-suite result, a performance guarantee or a live Gmail test. If recording fresh test footage, use its actual output rather than overlaying the historical number.

Optional narration over that footage:

> I tested the analysis and workflow behavior as well. This focused run passed 51 tests. That doesn't mean software can never fail—but it gives us evidence beyond a successful-looking demo.

Use that exact number only with the matching historical footage or a fresh run that actually returns it.

## Final production checklist

- [ ] Read the narration aloud and adjust pauses to finish within 7–10 minutes.
- [ ] Keep the first hook to approximately 20 seconds.
- [ ] Storage-full and upgrade visuals are genuine or clearly illustrative.
- [ ] Shared storage and Trash storage caveats remain readable/audible.
- [ ] No runtime LLM is named or implied.
- [ ] Existing Gmail labels are not presented as this application's AI classifier.
- [ ] All mockups and fictional email examples are labelled.
- [ ] No unsupported product UI or automatic organizing capability appears.
- [ ] User approval is visible before any cleanup effect.
- [ ] Before/after footage corresponds to the selection actually approved.
- [ ] Processing-time cuts are disclosed; no fabricated speed claim appears.
- [ ] No private addresses, message content, credentials or login links are visible.
- [ ] No automatic permanent deletion or immediate storage recovery is implied.
- [ ] No claim that cleanup guarantees avoiding a paid upgrade appears.
- [ ] A sender's frequency or newsletter status is never treated as proof that the sender's mail is disposable.

## Compliance summary

This script combines the storage-full hook with the supplied analyze → identify → suggest → review → organize workflow and verified implementation details. It keeps human approval distinct from analysis, describes LangGraph without inventing an LLM, and presents a cleaner inbox as the result of user-approved actions rather than autonomous deletion. Timing remains an editorial estimate until a recorded read-through is completed.

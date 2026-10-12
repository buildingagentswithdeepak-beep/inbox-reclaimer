import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import source from './data/continuation-code.json';
import {CodeEditorPanel, type CodeWindow} from './continuation/CodeEditorPanel';
import {AudioBed, colors, enter} from './continuation/Shared';

// 1920 x 1080, 60 fps, 2640 frames. Registration remains owned by Root.
const chapters = [
  {title: 'The read-only entry point', label: 'READ ENTRY', caption: 'The CLI hands inventory work to the read-only workflow.'},
  {title: 'Fetch. Aggregate. Present.', label: 'READ + REPORT', caption: 'Python turns Gmail metadata into a report, not a deletion decision.'},
  {title: 'A preview is not permission.', label: 'SELECT + APPROVE', caption: 'Native approval comes before the live writer is constructed.'},
  {title: 'Pause. Check. Then dispatch.', label: 'EFFECT BOUNDARY', caption: 'Graph = workflow progress. Journal = approval and operation evidence.'},
  {title: 'Intent, outcome, provider.', label: 'JOURNAL + GMAIL', caption: 'Record intent and outcome. Gmail changes remain guarded.'},
] as const;

type Cue = {start: number; end: number; windows: readonly CodeWindow[]; note: string};
// Presentation timing refines the manifest's paired-card hints; source stays pinned.
const cues: readonly Cue[] = [
  {start: 0, end: 3, windows: [{id: 'cli'}], note: 'cli.py / analyze delegates the inventory read.'},
  {start: 3, end: 6, windows: [{id: 'read-workflow'}], note: 'workflow.py / coordinates read-only work; no mailbox mutation edges.'},
  {start: 6, end: 9.3, windows: [{id: 'scan'}], note: 'Bounded listing-order scan / not a newest-first guarantee.'},
  {start: 9.3, end: 12.6, windows: [{id: 'aggregation'}], note: 'Aggregate sender counts and estimated bytes with deterministic Python.'},
  {start: 12.6, end: 16, windows: [{id: 'render'}], note: 'render_html / escaped, self-contained HTML with packaged CSS.'},
  {start: 16, end: 19, windows: [{id: 'selection'}], note: 'Independent sender search / at most 1,000 inspected candidates.'},
  {start: 19, end: 22, windows: [{id: 'decision'}], note: 'Cancellation returns without constructing a writer or changing mail.'},
  {start: 22, end: 26, windows: [{id: 'writer'}], note: 'Persist approval first; then construct the live writer and executor.'},
  {start: 26, end: 29, windows: [{id: 'pause'}], note: 'Approval is captured outside the graph; a checkpoint does not grant consent.'},
  {start: 29, end: 32, windows: [
    {id: 'checks', startLine: 101, endLine: 104, label: 'Fresh reads / reject changed sender or message'},
    {id: 'intent', label: 'Intent boundary / journal.begin before dispatch'},
    {id: 'effect', startLine: 139, endLine: 140, label: 'Effect boundary / fallback local check, then call'},
  ], note: 'Separate executor ranges / guard rejection and installed-guard branch are not shown.'},
  {start: 32, end: 34, windows: [{id: 'journal-intent'}], note: 'The intent event binds an operation to its plan and message.'},
  {start: 34, end: 36, windows: [{id: 'outcome'}], note: 'Record the classified outcome / not an automatic retry instruction.'},
  {start: 36, end: 39, windows: [{id: 'transport'}], note: 'Add the TRASH label, not permanent deletion. Executor read-back is still required.'},
];

const groups = source.timeline.groups.map((group, index) => ({
  ...group,
  ...chapters[index],
  tabs: [...new Set(group.cards.flatMap((card) => card.excerptIds.map((id) => {
    const excerpt = source.excerpts.find((item) => item.id === id);
    if (!excerpt) throw new Error(`Missing source excerpt: ${id}`);
    return excerpt.file;
  })))],
}));

const CodeScene = ({group, cue}: {group: typeof groups[number]; cue: Cue}) => {
  const t = cue.start + useCurrentFrame() / useVideoConfig().fps;
  const leaving = enter(t, 39, 40);
  const accent = t < 19 ? colors.blue : colors.amber;
  return <AbsoluteFill style={{opacity: 1 - leaving, transform: `scale(${1 - .055 * leaving})`, transformOrigin: '50% 54%'}}>
    <div className="display" style={{position: 'absolute', left: 80, top: 110, fontSize: 60, lineHeight: '76px'}}>{group.title}</div>
    <div style={{position: 'absolute', left: 80, right: 80, top: 218, display: 'flex', gap: 28}}>
      {groups.map((item, index) => <div key={item.id} style={{flex: 1, paddingBottom: 14, borderBottom: `3px solid ${item.id === group.id ? accent : colors.border}`, color: item.id === group.id ? accent : colors.muted, fontSize: 20, letterSpacing: 1}}>
        {String(index + 1).padStart(2, '0')} / {item.label}
      </div>)}
    </div>
    <CodeEditorPanel windows={cue.windows} tabs={group.tabs} accent={accent}/>
    <div style={{position: 'absolute', left: 80, top: 915, right: 80, fontSize: 30, lineHeight: '40px', fontWeight: 500, color: accent}}>{group.caption}</div>
    <div style={{position: 'absolute', left: 80, top: 970, right: 80, fontSize: 24, lineHeight: '32px', color: colors.muted}}>{cue.note}</div>
  </AbsoluteFill>;
};

// Exported here so an end card can reuse it without adding an out-of-scope file.
export const PresenterPlaceholder = () => <AbsoluteFill style={{background: colors.background, color: colors.text, fontFamily: 'Inter, sans-serif'}}>
  <div style={{position: 'absolute', left: 360, top: 224, width: 1200, height: 438, border: `1px solid ${colors.border}`, borderRadius: 14, background: colors.panel, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 24}}>
    <div style={{width: 72, height: 4, background: colors.blue}}/>
    <div style={{fontSize: 24, letterSpacing: 3, color: colors.blue}}>TALKING-HEAD INSERT</div>
    <div className="display" style={{fontSize: 52, letterSpacing: -2}}>Presenter placeholder</div>
    <div style={{fontSize: 24, color: colors.muted}}>Reserved for presenter footage</div>
  </div>
  <div className="display" style={{position: 'absolute', left: 160, right: 160, top: 752, textAlign: 'center', fontSize: 64, lineHeight: '82px', letterSpacing: -2.8}}>That's the system behind the cleanup.</div>
</AbsoluteFill>;

export const GmailCleanupCodeTour = ({audio = true}: {audio?: boolean}) => {
  const {fps} = useVideoConfig();
  return <AbsoluteFill className="film" style={{background: colors.background}}>
    {groups.map((group) => <Sequence key={group.id} name={group.label} from={Math.round(group.startSecond * fps)} durationInFrames={Math.round(((group.endSecond === 39 ? 40 : group.endSecond) - group.startSecond) * fps)} layout="none">
      {cues.filter((cue) => cue.start >= group.startSecond && cue.start < group.endSecond).map((cue) => <Sequence key={cue.start} name={cue.windows.map((window) => window.id).join(' / ')} from={Math.round((cue.start - group.startSecond) * fps)} durationInFrames={Math.round(((cue.end === 39 ? 40 : cue.end) - cue.start) * fps)} layout="none">
        <CodeScene group={group} cue={cue}/>
      </Sequence>)}
    </Sequence>)}
    <Sequence name="Presenter handoff" from={Math.round(40 * fps)} durationInFrames={Math.round(4 * fps)}><PresenterPlaceholder/></Sequence>
    <div style={{position: 'absolute', left: 80, right: 80, top: 43, display: 'flex', justifyContent: 'space-between', color: colors.muted, fontSize: 20, letterSpacing: 2}}>
      <span>GMAIL CLEANUP AGENT / UNDER THE HOOD</span><span style={{color: colors.blue}}>11 / CODE TOUR</span>
    </div>
    <div style={{position: 'absolute', left: 80, right: 80, bottom: 25, fontSize: 18, color: colors.muted}}>Source responsibility tour / not a live execution or a literal call-order diagram</div>
    <AudioBed name="code" enabled={audio}/>
  </AbsoluteFill>;
};

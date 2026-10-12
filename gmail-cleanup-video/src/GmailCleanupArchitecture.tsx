import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {AudioBed, colors, enter} from './continuation/Shared';

// 1920 x 1080, 60 fps, 1680 frames (28 seconds). Registration is owned by Root.
const nodes = [
  {label: 'Gmail API', file: 'gmail.py', x: 80, y: 270, at: 1},
  {label: 'Metadata +\nPython rules', file: 'sync.py\n+ analytics.py', x: 470, y: 270, at: 3},
  {label: 'Report', file: 'render.py', x: 860, y: 270, at: 5},
  {label: 'User chooses\nsender', file: 'cli.py', x: 860, y: 445, at: 7},
  {label: 'Saved preview', file: 'sender/\nselection.py', x: 470, y: 445, at: 9},
  {label: 'Native user\napproval', file: 'sender/\ncommands.py', x: 80, y: 445, at: 11},
  {label: 'Executor +\nfresh checks', file: 'sender/\nexecutor.py', x: 80, y: 710, at: 15},
  {label: 'Supported\nGmail change', file: 'sender/\ngmail.py', x: 470, y: 710, at: 17},
  {label: 'Verify + record\noutcome', file: 'sender/\njournal.py', x: 860, y: 710, at: 19},
] as const;

const arrows = [
  {d: 'M 418 314 H 460', tip: 'M 451 307 L 460 314 L 451 321', at: 3},
  {d: 'M 808 314 H 850', tip: 'M 841 307 L 850 314 L 841 321', at: 5},
  {d: 'M 1025 366 V 435', tip: 'M 1018 426 L 1025 435 L 1032 426', at: 7},
  {d: 'M 852 489 H 810', tip: 'M 819 482 L 810 489 L 819 496', at: 9},
  {d: 'M 462 489 H 420', tip: 'M 429 482 L 420 489 L 429 496', at: 11},
  // This is a conditional edge, never evidence of approval or a simulated click.
  {d: 'M 380 541 V 700', tip: 'M 373 691 L 380 700 L 387 691', at: 15},
  {d: 'M 418 754 H 460', tip: 'M 451 747 L 460 754 L 451 761', at: 17},
  {d: 'M 808 754 H 850', tip: 'M 841 747 L 850 754 L 841 761', at: 19},
  {d: 'M 1025 806 V 869 H 1280 V 552 H 1340', tip: 'M 1331 545 L 1340 552 L 1331 559', at: 23},
] as const;

const support = [
  {label: 'LangGraph', y: 270, height: 175, at: 20,
    description: 'Workflow coordination\nApproval pause / resume',
    file: 'workflow.py\nsender/workflow.py'},
  {label: 'SQLite', y: 485, height: 208, at: 21,
    description: 'Graph checkpoints + separate\napproval / operation journal',
    file: 'storage.py'},
  {label: 'LLM', y: 733, height: 100, at: 22,
    description: 'None at runtime', file: ''},
] as const;

export const GmailCleanupArchitecture = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const tabs = enter(t, 26, 27.2);
  const graphRole = enter(t, 21, 21.5);
  const journalRole = enter(t, 23, 23.5);
  const feedback = enter(t, 23, 23.5);

  return <AbsoluteFill className="film" style={{background: colors.background}}>
    <div style={{position: 'absolute', left: 80, right: 80, top: 43, display: 'flex', justifyContent: 'space-between', color: colors.muted, fontSize: 20, letterSpacing: 2}}>
      <span>GMAIL CLEANUP AGENT / UNDER THE HOOD</span>
      <span style={{color: colors.blue}}>10 / ARCHITECTURE</span>
    </div>
    <div className="display" style={{position: 'absolute', left: 80, top: 110, fontSize: 60}}>Simplified architecture</div>
    <div style={{position: 'absolute', left: 80, top: 214, fontSize: 24, lineHeight: '30px', color: colors.blue}}>
      {'READ AND REVIEW \u2014 no mailbox changes'}
    </div>
    <div style={{position: 'absolute', left: 1350, top: 214, fontSize: 24, lineHeight: '30px', color: colors.muted}}>
      SUPPORTING COMPONENTS
    </div>

    {/* Fixed SVG geometry makes both arrow direction and arbitrary-frame seeking explicit. */}
    <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
      {arrows.map((arrow, index) => {
        const draw = interpolate(t, [arrow.at, arrow.at + .4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const color = index < 4 ? colors.blue : index < 8 ? colors.amber : colors.muted;
        return <g key={arrow.d} fill="none" stroke={color} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
          <path d={arrow.d} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - draw} opacity={draw > 0 ? 1 : 0}/>
          <path d={arrow.tip} opacity={enter(t, arrow.at + .32, arrow.at + .4)}/>
        </g>;
      })}
      <path d="M 80 605 H 1220" fill="none" stroke={colors.amber} strokeWidth={3}/>
    </svg>

    {nodes.map((node, index) => {
      const reveal = enter(t, node.at, node.at + .5);
      const color = index < 5 ? colors.blue : colors.amber;
      // cli.py is the blue active tab for the following code-tour entry point.
      const tabColor = node.file === 'cli.py' ? colors.blue : color;
      return <div key={node.label} style={{position: 'absolute', left: node.x, top: node.y, width: 330, height: 88, boxSizing: 'border-box', border: `2px solid ${tabColor}`, borderRadius: 12 - 6 * tabs, background: index < 5 ? colors.panel : colors.review, opacity: reveal}}>
        <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', whiteSpace: 'pre-line', fontSize: 30, lineHeight: '34px', fontWeight: 600, color, opacity: 1 - tabs}}>
          {node.label}
        </div>
        <div style={{position: 'absolute', left: 14, right: 14, top: -2, height: 5, background: tabColor, opacity: tabs}}/>
        <div style={{position: 'absolute', inset: '7px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontSize: 30, lineHeight: '33px', fontWeight: 600, color: tabColor, opacity: tabs}}>
          {node.file.split('\n').map((line) => <span key={line} style={{fontSize: line === 'sender/' ? 24 : 30}}>{line}</span>)}
        </div>
      </div>;
    })}

    {/* The boundary persists during the conditional write path and the file handoff. */}
    <div style={{position: 'absolute', left: 470, top: 541, width: 750, fontSize: 24, lineHeight: '28px', fontWeight: 600, color: colors.amber}}>
      APPROVAL BOUNDARY /<br/>NO EXECUTION FROM A SAVED PREVIEW
    </div>
    <div style={{position: 'absolute', left: 80, top: 660, paddingRight: 18, fontSize: 24, lineHeight: '30px', color: colors.amber, background: colors.background}}>
      APPROVED ACTION
    </div>
    <div style={{position: 'absolute', left: 470, top: 660, fontSize: 24, lineHeight: '30px', color: colors.amber}}>
      Only after native approval
    </div>

    {support.map((item) => <div key={item.label} style={{position: 'absolute', left: 1350, top: item.y, width: 490, height: item.height, border: `1px solid ${colors.border}`, borderRadius: 12 - 6 * tabs, background: colors.panel, opacity: enter(t, item.at, item.at + .5)}}>
      <div style={{position: 'absolute', left: 22, right: 22, top: 15, fontSize: 30, lineHeight: '36px', fontWeight: 600, color: colors.blue, opacity: item.file ? 1 - tabs : 1}}>{item.label}</div>
      <div style={{position: 'absolute', left: 22, right: 22, top: 59, fontSize: 24, lineHeight: '30px', whiteSpace: 'pre-line', color: colors.muted, opacity: item.file ? 1 - tabs : 1}}>{item.description}</div>
      {item.label === 'LangGraph' && <div style={{position: 'absolute', left: 22, top: 132, fontSize: 24, lineHeight: '30px', color: colors.blue, opacity: graphRole * (1 - tabs)}}>Graph = workflow progress</div>}
      {item.label === 'SQLite' && <div style={{position: 'absolute', left: 22, top: 134, fontSize: 24, lineHeight: '30px', color: colors.amber, opacity: journalRole * (1 - tabs)}}>Journal = approval and<br/>operation evidence.</div>}
      {item.file && <>
        <div style={{position: 'absolute', left: 18, right: 18, top: 0, height: 4, background: colors.blue, opacity: tabs}}/>
        <div style={{position: 'absolute', inset: '12px 22px', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', whiteSpace: 'pre-line', fontSize: 30, lineHeight: '38px', fontWeight: 600, color: colors.blue, opacity: tabs}}>{item.file}</div>
      </>}
    </div>)}

    <div style={{position: 'absolute', left: 600, top: 900, width: 670, fontSize: 24, lineHeight: '30px', textAlign: 'right', color: colors.muted, opacity: feedback}}>
      Record outcome / not automatic retry
    </div>
    <div style={{position: 'absolute', left: 80, top: 940, fontSize: 24, lineHeight: '30px', color: colors.blue, opacity: tabs}}>
      SOURCE FILES / src/inbox_reclaimer/ / NEXT: cli.py
    </div>
    <div style={{position: 'absolute', left: 80, right: 80, bottom: 38, display: 'flex', justifyContent: 'space-between', fontSize: 22, lineHeight: '28px', color: colors.muted}}>
      <span>Conceptual sequence, not a literal call graph.</span>
      <span style={{color: colors.amber}}>This diagram does not grant permission.</span>
    </div>
    <AudioBed name="architecture" enabled={audio}/>
  </AbsoluteFill>;
};

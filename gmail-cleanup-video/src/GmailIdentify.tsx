import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const blue = '#83b6ff';
const amber = '#ffd086';
const enter = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.22, 1, .36, 1)});
const rows = [
  ['Northstar Store', 'Weekend offers', 'PROMOTION'],
  ['Northstar Store', 'New collection', 'PROMOTION'],
  ['Project team', 'Milestone review', 'PROJECT'],
  ['Field Notes', 'A newsletter worth keeping?', 'NEWSLETTER'],
  ['Travel desk', 'Your receipt', 'RECEIPT'],
  ['Design circle', 'Next week\'s discussion', 'UPDATE'],
];

export const GmailIdentify = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const opening = enter(t, 0, .6);
  const handoff = enter(t, 6.5, 7.3);
  const reportScale = 1 - .32 * handoff;
  const reportHighlight = enter(t, .6, 1.5);
  const preview = enter(t, 6.8, 7.5);
  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 85% 70%, #1b3552, #0a1422 73%)'}}>
    <div style={{position: 'absolute', left: 90, right: 90, top: 43, display: 'flex', justifyContent: 'space-between', color: '#9eb2cd', letterSpacing: 2, fontSize: 17}}><span>GMAIL CLEANUP AGENT / THE WORKFLOW</span><span style={{color: blue}}>02 / IDENTIFY</span></div>
    <div className="display" style={{position: 'absolute', top: 112, left: 90, fontSize: 60, opacity: opening, transform: `translateY(${18 * (1 - opening)}px)`}}>2. IDENTIFY <span style={{color: '#607b9d'}}>{'\u2014'}</span> <span style={{color: amber}}>Candidate, not a verdict.</span></div>
    <div style={{position: 'absolute', left: 93, top: 202, color: '#a9bfd9', fontSize: 23}}>Frequency is a signal. Your context decides what is worth keeping.</div>

    <div style={{position: 'absolute', left: 90, top: 274, color: '#9cb5d4', fontSize: 16, letterSpacing: 1.5}}>RECORDED REPORT / HELD FOR READABILITY</div>
    <div style={{position: 'absolute', left: 90, top: 310, width: 1040, height: 535, background: '#1a1a1a', border: '1px solid #50647e', borderRadius: 12, overflow: 'hidden', transform: `scale(${reportScale})`, transformOrigin: 'top left'}}>
      <div style={{height: 48, background: '#18283b', color: '#b5c9e1', fontSize: 16, padding: '14px 20px', display: 'flex', justifyContent: 'space-between'}}><span>SENDER FREQUENCY / EXCERPT</span><span>ACTUAL SENDERS</span></div>
      <Img src={staticFile('identify-senders.png')} style={{position: 'absolute', top: 48, left: 0, width: 1040, height: 476.67}}/>
      <svg width="1040" height="535" style={{position: 'absolute', inset: 0}}><rect x="27" y="328" width="992" height="104" rx="5" fill="none" stroke={blue} strokeWidth="3" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - reportHighlight}/></svg>
    </div>
    <div style={{position: 'absolute', left: 90, top: 877, opacity: 1 - handoff}}><div className="display" style={{fontSize: 35, letterSpacing: -1.2}}>Frequent does not mean unwanted.</div><div style={{fontSize: 20, color: '#9fb6d2', marginTop: 14}}>Recorded counts. Limited analysis sample. No deletion recommendation.</div></div>

    <div style={{position: 'absolute', left: 1180, top: 274, color: '#9cb5d4', fontSize: 16, letterSpacing: 1.5}}>FICTIONAL INBOX / NOT THE RECORDED SENDERS</div>
    <div style={{position: 'absolute', left: 1180, top: 310, width: 650, padding: '0 20px', border: '1px solid #3b526e', borderRadius: 12, background: '#132337'}}>
      {rows.map(([sender, subject, type], i) => <div key={subject} style={{height: 94, display: 'flex', alignItems: 'center', gap: 18, borderBottom: i === rows.length - 1 ? 'none' : '1px solid #2c415b'}}><div style={{width: 10, height: 10, border: '1px solid #7188a7', borderRadius: 3, flexShrink: 0}}/><div style={{flex: 1}}><div style={{fontSize: 24, fontWeight: 600}}>{sender}</div><div style={{fontSize: 19, color: '#b1c1d5', marginTop: 7}}>{subject}</div></div><span style={{fontSize: 12, letterSpacing: 1, color: '#9ab1d0'}}>{type}</span></div>)}
      <svg width="650" height="564" style={{position: 'absolute', left: -1, top: 0, pointerEvents: 'none'}}>
        <rect x="5" y="5" width="640" height="178" rx="8" fill="none" stroke={blue} strokeWidth="3" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - enter(t, 1.5, 2.5)}/>
        <rect x="5" y="287" width="640" height="84" rx="8" fill="none" stroke={blue} strokeWidth="3" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - enter(t, 4, 4.8)}/>
      </svg>
    </div>
    <div style={{position: 'absolute', left: 1183, top: 909, fontSize: 21, color: '#b1c6df'}}>Outlined for inspection. All rows stay unchanged.</div>

    <div style={{position: 'absolute', left: 90, top: 704, width: 1040, height: 252, opacity: preview, transform: `translateY(${24 * (1 - preview)}px)`, border: '1px solid #658dbd', borderRadius: 12, background: '#102238', padding: '20px 25px'}}>
      <div style={{fontSize: 16, letterSpacing: 1, color: blue, marginBottom: 16}}>NEXT / EXACT-SENDER PREVIEW</div>
      <div style={{fontFamily: 'Consolas, monospace', fontSize: 23, lineHeight: 1.55, color: '#d6e7ff'}}>reclaim --workspace-scripts $helper {'`'}<br/>{'  '}sender-cleanup --sender noreply@medium.com {'`'}<br/>{'  '}--redact-subjects</div>
      <div style={{fontSize: 17, color: amber, marginTop: 15}}>Illustrative command, not executed. No --execute. No approval.</div>
    </div>
    <div style={{position: 'absolute', left: 829, top: 406, width: 280, opacity: handoff}}><div className="display" style={{fontSize: 33, letterSpacing: -1}}>One exact<br/><span style={{color: blue}}>sender next.</span></div><div style={{fontSize: 18, lineHeight: 1.5, color: '#b0c4de', marginTop: 20}}>Separate search,<br/>not limited to the<br/>earlier analysis sample.</div></div>
    <div style={{position: 'absolute', left: 90, right: 90, bottom: 38, display: 'flex', justifyContent: 'space-between', fontSize: 18, color: '#93acca'}}><span>Fictional examples are independent of the recorded sender rankings.</span><span style={{color: amber}}>NO CLEANUP APPROVED / NO MAIL CHANGED</span></div>
    {audio && <><Audio src={staticFile('audio/identify-music.wav')}/><Audio src={staticFile('audio/identify-sfx.wav')}/></>}
  </AbsoluteFill>;
};

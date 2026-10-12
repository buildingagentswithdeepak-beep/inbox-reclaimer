import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const blue = '#83b6ff';
const amber = '#ffd086';
const ink = '#101e30';
const ease = Easing.bezier(.22, 1, .36, 1);
const p = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
const useTime = () => useCurrentFrame() / useVideoConfig().fps;

const Label = ({children}: {children: React.ReactNode}) => <div style={{fontSize: 18, letterSpacing: 2.4, color: '#9fb0c6', fontWeight: 600}}>{children}</div>;
const Header = ({chapter, badge}: {chapter: string; badge: string}) => <div style={{position: 'absolute', left: 86, right: 86, top: 48, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}><Label>GMAIL CLEANUP AGENT <span style={{margin: '0 20px', color: '#476080'}}>/</span> {chapter}</Label><span style={{fontSize: 16, color: '#a5bad3', padding: '10px 15px', border: '1px solid #3b4e67', borderRadius: 7}}>{badge}</span></div>;
const Arrow = ({color = blue}: {color?: string}) => <svg width="72" height="32" viewBox="0 0 72 32" fill="none"><path d="M0 16h67M54 3l13 13-13 13" stroke={color} strokeWidth="2"/></svg>;

const Brand = ({name}: {name: 'Gmail' | 'Drive' | 'Photos'}) => <svg width="85" height="76" viewBox="0 0 80 72" fill="none">
  {name === 'Gmail' ? <><path d="M9 60V15l31 23 31-23v45" stroke="#4285f4" strokeWidth="10" strokeLinejoin="round"/><path d="M9 15 40 38 71 15" stroke="#ea4335" strokeWidth="10"/><path d="M9 15v45" stroke="#34a853" strokeWidth="10"/><path d="M71 15v45" stroke="#fbbc04" strokeWidth="10"/></> : name === 'Drive' ? <><path d="M29 4h23L79 51H56Z" fill="#fbbc04"/><path d="M29 4 2 51l12 20 27-47Z" fill="#34a853"/><path d="M2 51h77L67 71H14Z" fill="#4285f4"/></> : <><path d="M40 36V3C19 3 8 20 8 36Z" fill="#ea4335"/><path d="M40 36h33C73 15 57 4 40 4Z" fill="#4285f4"/><path d="M40 36v33c21 0 32-17 32-33Z" fill="#34a853"/><path d="M40 36H7c0 21 16 32 33 32Z" fill="#fbbc04"/></>}
</svg>;

const OpeningTitle = () => {
  const t = useTime();
  return <AbsoluteFill>
    <Header chapter="WHY I BUILT IT" badge="YOUR INBOX. YOUR DECISION."/>
    <div style={{position: 'absolute', left: 88, right: 88, top: 279, textAlign: 'center'}}>
      <Label>LESS MANUAL HUNTING.</Label>
      <div className="display" style={{fontSize: 112, lineHeight: 1.15, marginTop: 38, opacity: p(t, .08, .45), transform: `translateY(${30 * (1 - p(t, .08, .7))}px)`}}>Less repetitive review.</div>
      <div className="display" style={{fontSize: 112, lineHeight: 1.15, color: amber, marginTop: 18, opacity: p(t, .95, 1.4), transform: `translateY(${25 * (1 - p(t, .95, 1.6))}px)`}}>Not less control.</div>
      <div style={{fontSize: 26, lineHeight: 1.55, color: '#acbed5', marginTop: 35, opacity: p(t, 1.85, 2.25)}}>Help finding what to review.<br/>The decision stays with you.</div>
    </div>
    <div style={{position: 'absolute', left: 90, bottom: 68, display: 'flex', gap: 14, alignItems: 'center', color: blue, fontSize: 20}}><span style={{width: 36, height: 2, background: blue}}/>A better starting point, not an autopilot.</div>
  </AbsoluteFill>;
};

const Row = ({subject = 'Project update: ready for your review', sender = 'Northstar Studio', selected = false, compact = false}: {subject?: string; sender?: string; selected?: boolean; compact?: boolean}) => <div style={{height: compact ? 89 : 116, background: selected ? '#fff1d6' : '#f8fafc', borderBottom: '1px solid #e2e7ef', display: 'flex', alignItems: 'center', padding: '0 30px', gap: 23, color: ink, boxShadow: selected ? 'inset 5px 0 #d5a24d' : 'none'}}>
  <div style={{width: 19, height: 19, border: '1.5px solid #8c9cb0', borderRadius: 3}}/><span style={{fontSize: 26, color: selected ? '#bf8831' : '#8b9bb0'}}>☆</span>
  <span style={{fontSize: 22, fontWeight: 600, width: 230, flexShrink: 0}}>{sender}</span><span style={{fontSize: 24, fontWeight: 500, flex: 1}}>{subject}</span><span style={{fontSize: 17, color: '#6b7c91'}}>9:42 AM</span>
</div>;

const InboxContext = () => {
  const t = useTime();
  const focus = p(t, .5, 1.4);
  return <AbsoluteFill>
    <Header chapter="ONE DECISION AT A TIME" badge="SCREENSHOT + ILLUSTRATIVE ROWS"/>
    <div className="display" style={{position: 'absolute', left: 88, top: 128, fontSize: 63}}>Recognise. Open. <span style={{color: amber}}>Consider.</span> Repeat.</div>
    <div style={{position: 'absolute', left: 88, top: 254, width: 1744, borderRadius: 20, overflow: 'hidden', boxShadow: '0 35px 80px #0005', transform: `translateY(${30 * (1 - p(t, 0, .4))}px)`}}>
      <Img src={staticFile('intro-gmail-crop.png')} style={{width: 1744, height: 332.1, display: 'block'}}/>
      <div style={{height: 51, background: '#e3ebf5', padding: '16px 30px', color: '#617489', fontSize: 16, letterSpacing: 1}}>ILLUSTRATIVE EMAIL ROWS BELOW / NOT A LIVE RECORDING</div>
      <Row selected={focus > .5}/><Row compact sender="Field & Form" subject="Your weekly offers are here"/><Row compact sender="The Weekly Dispatch" subject="This week's ideas worth keeping"/>
      <div style={{position: 'absolute', left: 383 + 205 * focus, top: 455, opacity: p(t, .25, .6)}}><svg width="48" height="60" viewBox="0 0 40 52"><path d="M4 3v35l9-8 8 17 7-4-8-16 13-1Z" fill="white" stroke="#142238" strokeWidth="2.5"/></svg></div>
    </div>
    <div style={{position: 'absolute', left: 90, bottom: 48, right: 90, display: 'flex', justifyContent: 'space-between', color: '#a1b1c5', fontSize: 18}}><span>Supplied Gmail screenshot, cropped for privacy. Date and price as captured.</span><span>No mailbox access. No changes.</span></div>
  </AbsoluteFill>;
};

const SharedStorage = () => {
  const t = useTime();
  return <AbsoluteFill>
    <Header chapter="ONE IMPORTANT DISTINCTION" badge="SHARED STORAGE / NO PERCENTAGES"/>
    <div style={{position: 'absolute', top: 143, width: '100%', textAlign: 'center'}}><div className="display" style={{fontSize: 74}}>It&apos;s not just <span style={{color: blue}}>Gmail.</span></div><div style={{fontSize: 28, marginTop: 16, color: '#b7c7db'}}>Three services. One Google storage allowance.</div></div>
    <svg width="1920" height="1080" style={{position: 'absolute', inset: 0}}><path d="M460 539v90q0 25 25 25h950q25 0 25-25v-90M960 539v171" fill="none" stroke="#5b7a9f" strokeWidth="3" strokeDasharray="1600" strokeDashoffset={1600 * (1 - p(t, .5, 1.45))}/></svg>
    {(['Gmail', 'Drive', 'Photos'] as const).map((name, i) => <div key={name} style={{position: 'absolute', left: 290 + i * 500, top: 338, width: 340, height: 217, borderRadius: 22, background: '#edf2f8', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 22, opacity: p(t, i * .12, .4 + i * .12), transform: `translateY(${32 * (1 - p(t, i * .12, .6 + i * .12))}px)`, boxShadow: '0 15px 40px #0003'}}><Brand name={name}/><span style={{fontSize: 31, color: ink, fontWeight: 600}}>{name}</span></div>)}
    <div style={{position: 'absolute', left: 659, top: 709, width: 602, padding: '23px 0', border: '1px solid #5e82af', borderRadius: 70, textAlign: 'center', fontSize: 29, color: '#d8e7fa', background: '#162b43', opacity: p(t, .8, 1.35)}}>Shared Google Account storage</div>
    <div style={{position: 'absolute', top: 853, width: '100%', textAlign: 'center', fontSize: 29, lineHeight: 1.6, color: amber, opacity: p(t, .4, .85)}}>Cleaning Gmail may help. It may not solve every storage problem.<br/><span style={{fontSize: 25, color: '#b8c6d9'}}>Moving mail to Trash does not immediately free space.</span></div>
  </AbsoluteFill>;
};

const FindReviewDecide = () => {
  const t = useTime();
  const steps = [['Find', 'A place to start.', 'Surface potential clutter.'], ['Review', 'Context matters.', 'Inspect before any action.'], ['Decide', 'Your call.', 'Keep what matters to you.']];
  return <AbsoluteFill>
    <Header chapter="THE WORKFLOW" badge="HUMAN REVIEW FIRST"/>
    <div className="display" style={{position: 'absolute', left: 90, top: 145, fontSize: 78}}>Less repetition. <span style={{color: amber}}>Same control.</span></div>
    {steps.map(([title, sub, detail], i) => <div key={title} style={{position: 'absolute', left: 90 + i * 605, top: 346, width: 530, height: 393, opacity: p(t, .12 + .82 * i, .47 + .82 * i), transform: `translateY(${35 * (1 - p(t, .12 + .82 * i, .7 + .82 * i))}px)`}}>
      <div style={{paddingTop: 28, borderTop: `2px solid ${i ? amber : blue}`}}><Label>0{i + 1}</Label><div className="display" style={{fontSize: 94, marginTop: 29, color: i ? amber : blue}}>{title}</div><div style={{fontSize: 34, marginTop: 24}}>{sub}</div><div style={{fontSize: 23, color: '#a9bbd1', marginTop: 19}}>{detail}</div></div>
      {i < 2 && <div style={{position: 'absolute', right: -47, top: 113}}><Arrow color={i ? amber : blue}/></div>}
    </div>)}
    <div style={{position: 'absolute', left: 90, right: 90, top: 865, borderTop: '1px solid #33475e', paddingTop: 31, fontSize: 27, color: '#b3c3d6', opacity: p(t, 1.9, 2.35)}}>A suggestion is not permission to delete.</div>
  </AbsoluteFill>;
};

const TidyTransition = () => {
  const t = useTime();
  const push = interpolate(t, [.35, 1.18], [1, 3.6], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.cubic)});
  const pull = interpolate(t, [1.18, 2.45], [3.6, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const tidy = t >= 1.18;
  const scale = tidy ? pull : push;
  return <AbsoluteFill>
    <Header chapter="KEEP WHAT MATTERS" badge="ILLUSTRATIVE TRANSITION / NOT A RESULT"/>
    <div className="display" style={{position: 'absolute', left: 90, top: 143, fontSize: 72, opacity: tidy ? p(t, 1.65, 2.3) : 1 - p(t, .4, .95)}}>{tidy ? <>A clearer view.<span style={{color: amber}}> Still your call.</span></> : <>Start with <span style={{color: amber}}>one email.</span></>}</div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 285, bottom: 134, overflow: 'hidden'}}>
      {/* Both sides of the cut share the same selected row and transform origin. */}
      <div style={{position: 'absolute', left: 142, top: 22, width: 1636, borderRadius: 19, overflow: 'hidden', background: '#fff', transform: `scale(${scale})`, transformOrigin: '52% 194px', boxShadow: '0 22px 75px #0005'}}>
        <div style={{height: 136, padding: '27px 31px', background: '#eaf0f7', color: '#25405f', display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}><div><div style={{fontSize: 18, color: '#6d8097', letterSpacing: 1.5}}>ILLUSTRATIVE INBOX</div><div style={{fontSize: 35, marginTop: 9, fontWeight: 600}}>{tidy ? 'A simplified view of what matters' : 'Inbox'}</div></div><div style={{fontSize: 18, color: '#72849b'}}>Fictional messages</div></div>
        <Row selected/>
        {tidy ? <><Row sender="Atlas Supply" subject="Your purchase receipt"/><Row sender="The Weekly Dispatch" subject="This week's ideas worth keeping"/><div style={{height: 99, display: 'flex', alignItems: 'center', padding: '0 32px', fontSize: 20, color: '#738298', background: '#f5f7fb'}}>Concept illustration only. No cleanup action was performed.</div></> : <><Row sender="Field & Form" subject="A fresh offer in your inbox"/><Row sender="Field & Form" subject="Your weekly offers are here"/><Row sender="The Weekly Dispatch" subject="This week's ideas worth keeping"/></>}
      </div>
    </div>
    <div style={{position: 'absolute', left: 90, right: 90, bottom: 65, display: 'flex', justifyContent: 'space-between', fontSize: 23, color: '#a9bcd3'}}><span>Find <span style={{color: blue, margin: '0 14px'}}>→</span> Review <span style={{color: amber, margin: '0 14px'}}>→</span> Decide</span><span>No automatic deletion. No storage recovery claimed.</span></div>
  </AbsoluteFill>;
};

export const GmailIntroduction = ({audio = true}: {audio?: boolean}) => <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 80% 60%, #1b3550, #0a1422 70%)'}}>
  <Sequence durationInFrames={240}><OpeningTitle/></Sequence>
  <Sequence from={240} durationInFrames={180}><InboxContext/></Sequence>
  <Sequence from={420} durationInFrames={240}><SharedStorage/></Sequence>
  <Sequence from={660} durationInFrames={180}><FindReviewDecide/></Sequence>
  <Sequence from={840} durationInFrames={240}><TidyTransition/></Sequence>
  {audio && <><Audio src={staticFile('audio/intro-music.wav')}/><Audio src={staticFile('audio/intro-sfx.wav')}/></>}
</AbsoluteFill>;

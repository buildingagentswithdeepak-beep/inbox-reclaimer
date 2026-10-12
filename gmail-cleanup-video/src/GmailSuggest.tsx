import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const blue = '#83b6ff';
const amber = '#ffd086';
const enter = (t: number, start: number, end: number) => interpolate(t, [start, end], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.22, 1, .36, 1)});

export const GmailSuggest = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const opening = enter(t, 0, .5);
  const stage = t < 2.3 ? 0 : t < 4.5 ? 1 : 2;
  const stageStart = [0, 2.3, 4.5][stage];
  const arrival = enter(t, stageStart, stageStart + .3);
  const badge = enter(t, 5.5, 6.1);
  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 85% 70%, #1b3552, #0a1422 73%)'}}>
    <div style={{position: 'absolute', top: 43, left: 90, right: 90, display: 'flex', justifyContent: 'space-between', color: '#9eb2cd', fontSize: 17, letterSpacing: 2}}><span>GMAIL CLEANUP AGENT / THE WORKFLOW</span><span style={{color: blue}}>03 / SUGGEST</span></div>
    <div className="display" style={{position: 'absolute', top: 112, left: 90, fontSize: 64, opacity: opening, transform: `translateY(${18 * (1 - opening)}px)`}}>3. SUGGEST <span style={{color: '#607b9d'}}>{'\u2014'}</span> <span style={{color: amber}}>Preview before action.</span></div>
    <div style={{position: 'absolute', left: 93, top: 207, fontSize: 24, color: '#adc2dc'}}>Exact sender: <span style={{color: blue}}>noreply@medium.com</span></div>

    <div style={{position: 'absolute', left: 90, top: 281, width: 1300, display: 'flex', justifyContent: 'space-between', color: '#a8bed9', fontSize: 16, letterSpacing: 1}}><span>{['RECORDED PREVIEW COMMAND', 'RECORDED SAVED-PLAN OUTPUT', 'ACTUAL SAVED HTML REPORT'][stage]}</span><span>HELD FOR READABILITY / PRIVATE FIELDS EXCLUDED</span></div>
    <div style={{position: 'absolute', left: 90, top: 320, width: 1300, height: 505, border: '1px solid #4a627f', borderRadius: 13, overflow: 'hidden', background: stage === 2 ? '#f3f6fb' : '#1a1a1a', boxShadow: '0 24px 80px #0004'}}>
      <div style={{position: 'absolute', inset: 0, transform: `translateY(${16 * (1 - arrival)}px)`}}>
        {stage === 0 && <>
          <div style={{position: 'absolute', left: 30, top: 37, fontSize: 18, color: '#a8bdd7', letterSpacing: 1.5}}>sender-cleanup / PREVIEW ONLY</div>
          <Img src={staticFile('suggest-command.png')} style={{position: 'absolute', left: 24, top: 137, width: 1250, height: 154}}/>
          <div style={{position: 'absolute', left: 30, bottom: 45, display: 'flex', gap: 40, fontSize: 22, color: '#b4cce9'}}><span>--max-messages 20</span><span>--redact-subjects</span><span style={{color: amber}}>No --execute</span></div>
        </>}
        {stage === 1 && <>
          <Img src={staticFile('suggest-plan.png')} style={{position: 'absolute', left: 95, top: 14, width: 1100, height: 477.23}}/>
          <svg width="1300" height="505" style={{position: 'absolute', inset: 0}}><rect x="121" y="354" width="872" height="48" rx="5" fill="none" stroke={blue} strokeWidth="3" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - enter(t, 2.3, 2.85)}/><rect x="121" y="403" width="700" height="84" rx="5" fill="none" stroke={amber} strokeWidth="2" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - enter(t, 2.65, 3.15)}/></svg>
        </>}
        {stage === 2 && <Img src={staticFile('suggest-report.png')} style={{position: 'absolute', left: 0, top: 45, width: 1300, height: 415}}/>}
      </div>
    </div>

    <div style={{position: 'absolute', left: 1450, top: 324, width: 380}}>
      {['Preview command', 'Saved plan ID', 'Local report'].map((label, i) => <div key={label} style={{display: 'flex', gap: 17, alignItems: 'center', height: 78, color: stage >= i ? blue : '#869bb8'}}><div style={{width: 42, height: 42, borderRadius: 22, border: `1px solid ${stage >= i ? blue : '#405670'}`, display: 'grid', placeItems: 'center', fontSize: 17}}>0{i + 1}</div><span style={{fontSize: 25}}>{label}</span></div>)}
      <div style={{marginTop: 40, borderTop: '1px solid #4a5260', paddingTop: 27}}><div style={{fontSize: 13, color: '#a9bad0', letterSpacing: 2, marginBottom: 17}}>EDITORIAL STATUS</div><div style={{padding: '20px 18px', borderRadius: 10, background: '#392e20', border: `1px solid ${amber}`, color: amber, fontSize: 29, fontWeight: 600, transform: `scale(${1 + .025 * badge})`, transformOrigin: 'left center', boxShadow: `0 0 0 ${5 * badge}px #ffd08612`}}>Awaiting review</div><div style={{fontSize: 21, color: '#b9c8da', marginTop: 23, lineHeight: 1.55}}>A saved selection.<br/>Not permission to act.</div></div>
    </div>
    <div style={{position: 'absolute', left: 93, top: 873, fontSize: 24, color: '#aec4dd'}}>{stage === 0 ? 'The preview searches this sender separately from the earlier analysis sample.' : stage === 1 ? 'The real output confirms: approval_created = false; mail_changed = false.' : 'Same sender. Same saved plan. Review comes next.'}</div>
    <div style={{position: 'absolute', left: 90, right: 90, bottom: 38, display: 'flex', justifyContent: 'space-between', color: '#93acca', fontSize: 18}}><span>Recorded candidate cap: 20. A preview is not a full-mailbox result.</span><span style={{color: amber}}>NO APPROVAL / NO MAIL CHANGED</span></div>
    {audio && <><Audio src={staticFile('audio/suggest-music.wav')}/><Audio src={staticFile('audio/suggest-sfx.wav')}/></>}
  </AbsoluteFill>;
};

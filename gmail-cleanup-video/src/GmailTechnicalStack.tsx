import {Audio} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const blue = '#83b6ff';
const amber = '#ffd086';
const p = (t: number, a: number, b: number) => interpolate(t, [a, b], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.22, 1, .36, 1)});
const Lock = () => <svg width="24" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></svg>;

export const GmailTechnicalStack = ({audio = true}: {audio?: boolean}) => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const technicalExit = p(t, 7.65, 8.05);
  const framework = ['Python', 'LangGraph', 'Gmail API', 'SQLite'];
  return <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 85% 65%,#1d3652,#0a1422 70%)'}}>
    <div style={{position: 'absolute', left: 88, right: 88, top: 47, display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#a1b5cf', fontSize: 18, letterSpacing: 2}}><span>GMAIL CLEANUP AGENT <span style={{margin: '0 20px', color: '#567293'}}>/</span> FRAMEWORK, NOT AN LLM</span><span style={{fontSize: 16, letterSpacing: .5, border: '1px solid #3d536d', borderRadius: 7, padding: '11px 16px'}}>TECHNICAL OVERVIEW</span></div>

    <div style={{opacity: 1 - technicalExit, transform: `translateY(${-technicalExit * 75}px)`}}>
      <div className="display" style={{position: 'absolute', left: 90, top: 150, fontSize: 75, letterSpacing: -2.5}}>{t < 4.5 ? 'A practical stack. Explicit rules.' : <>No runtime <span style={{color: amber}}>LLM calls.</span></>}</div>
      <div style={{position: 'absolute', left: 90, right: 90, top: 299, display: 'flex', alignItems: 'center', gap: 23}}>
        {framework.map((name, i) => {
          const reveal = p(t, .15 + i * .6, .55 + i * .6);
          return <div key={name} style={{display: 'flex', alignItems: 'center', flex: 1, gap: 23, opacity: reveal, transform: `translateY(${27 * (1 - reveal)}px)`}}><div style={{flex: 1, borderTop: `2px solid ${blue}`, paddingTop: 22}}><div style={{fontSize: 16, color: '#8fa6c2', letterSpacing: 2}}>0{i + 1}</div><div className="display" style={{fontSize: 49, letterSpacing: -1.5, marginTop: 14, color: '#e4edf9'}}>{name}</div></div>{i < 3 && <span style={{fontSize: 33, color: '#5e7eaa', marginTop: 50}}>+</span>}</div>;
        })}
      </div>

      {t < 4.5 && <div style={{position: 'absolute', left: 90, right: 90, top: 498, display: 'flex', alignItems: 'center', gap: 55, opacity: p(t, 2.5, 2.85), transform: `translateY(${26 * (1 - p(t, 2.5, 3))}px)`}}><Img src={staticFile('stack-source.svg')} style={{width: 1160, height: 450, boxShadow: '0 20px 60px #0003', borderRadius: 16}}/><div style={{flex: 1}}><div style={{fontSize: 18, letterSpacing: 2, color: amber}}>VERIFIED DEPENDENCY</div><div className="display" style={{fontSize: 46, lineHeight: 1.2, letterSpacing: -1, marginTop: 21}}>LangGraph<br/>coordinates<br/>the workflow.</div><div style={{fontSize: 23, lineHeight: 1.5, color: '#9fb4cf', marginTop: 25}}>It does not decide<br/>what you delete.</div></div></div>}

      {t >= 4.5 && <div style={{position: 'absolute', left: 90, right: 90, top: 500, opacity: p(t, 4.5, 4.8)}}>
        <div style={{fontSize: 18, color: '#8ea6c3', letterSpacing: 2, marginBottom: 25}}>ILLUSTRATIVE METADATA FLOW / NOT LIVE EXECUTION</div>
        <div style={{position: 'relative', height: 308}}>
          <div style={{position: 'absolute', left: 0, top: 0, width: 540, height: 290, background: '#12283e', border: '1px solid #3c5d7f', borderRadius: 18, padding: 28}}><div style={{fontSize: 31, color: '#e0eafb', fontWeight: 600}}>Message metadata</div><div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 27}}>{['Sender', 'Existing labels', 'Message age', 'Estimated size'].map(label => <div key={label} style={{background: '#213e5b', padding: '16px 19px', borderRadius: 7, color: '#abc8eb', fontSize: 21}}>{label}</div>)}</div></div>
          <div style={{position: 'absolute', left: 594, top: 105, width: 380, height: 1, background: '#456889'}}/>
          <div style={{position: 'absolute', left: 657, top: 27, color: '#a7bdd7', fontSize: 21}}>Python rules</div>
          {[0, 1, 2, 3].map(i => {
            const move = p(t, 5.3 + i * .35, 6.15 + i * .35);
            return <div key={i} style={{position: 'absolute', left: 582 + 392 * move, top: 93, width: 24, height: 24, background: blue, borderRadius: 5, opacity: t >= 5.3 + i * .35 && move < 1 ? .95 : 0}}/>;
          })}
          <div style={{position: 'absolute', left: 1030, right: 0, top: 0, height: 290, background: '#edf2f8', borderRadius: 18, padding: 28, color: '#203751'}}><div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}><span style={{fontSize: 31, fontWeight: 600}}>Report</span><span style={{fontSize: 14, color: '#597899'}}>READ ONLY</span></div>{[0, 1, 2].map(i => <div key={i} style={{height: 35, marginTop: 21, opacity: p(t, 5.95 + i * .35, 6.35 + i * .35)}}><div style={{width: `${80 - i * 16}%`, height: 8, background: '#6b9cc7', borderRadius: 5}}><div/></div><div style={{width: '92%', height: 4, background: '#d1dfeb', marginTop: 10}}/></div>)}</div>
        </div>
        <div style={{fontSize: 27, color: amber, marginTop: 37}}>Metadata in. A report out. Your judgment stays essential.</div>
      </div>}
    </div>

    {t >= 7.65 && <div style={{position: 'absolute', left: 90, right: 90, top: 282, opacity: technicalExit, transform: `translateY(${95 * (1 - technicalExit)}px)`}}>
      <div style={{fontSize: 19, letterSpacing: 2.5, color: blue}}>NEXT / THE USER WORKFLOW</div><div className="display" style={{fontSize: 81, marginTop: 29}}>The framework coordinates.<br/><span style={{color: amber}}>You stay in control.</span></div>
      <div style={{display: 'flex', alignItems: 'center', marginTop: 94}}>{['Analyze', 'Identify', 'Suggest', 'Review', 'Organize'].map((name, i) => <div key={name} style={{display: 'flex', alignItems: 'center', flex: i === 4 ? '0 0 255px' : 1}}><div style={{display: 'flex', alignItems: 'center', gap: 13, color: i === 3 ? amber : i === 4 ? '#6e829b' : blue}}><div style={{width: 47, height: 47, borderRadius: 25, border: '1px solid currentColor', display: 'grid', placeItems: 'center', fontSize: 16}}>{i === 4 ? <Lock/> : `0${i + 1}`}</div><span style={{fontSize: 28}}>{name}</span></div>{i < 4 && <div style={{height: 1, flex: 1, margin: '0 20px', background: '#3e5879'}}/>}</div>)}</div><div style={{fontSize: 24, color: '#9eb5d1', marginTop: 57}}>Review before action. No cleanup approved here.</div>
    </div>}
    <div style={{position: 'absolute', bottom: 36, left: 90, right: 90, display: 'flex', justifyContent: 'space-between', color: '#829ab8', fontSize: 17}}><span>Current implementation: metadata + deterministic rules.</span><span>Full architecture and module tour come later.</span></div>
    {audio && <><Audio src={staticFile('audio/stack-music.wav')}/><Audio src={staticFile('audio/stack-sfx.wav')}/></>}
  </AbsoluteFill>;
};

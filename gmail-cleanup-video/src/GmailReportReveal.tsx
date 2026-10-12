import {Audio, Video} from '@remotion/media';
import {AbsoluteFill, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

const blue = '#83b6ff';
const amber = '#ffd086';
const enter = (t: number, start: number, end: number) => interpolate(t, [start, end], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.22, 1, .36, 1)});
const Lock = () => <svg width="20" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></svg>;

const ReportScene = () => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  const arrival = enter(t, 0, .65);
  const captions = t < 4 ? ['READ-ONLY OVERVIEW', 'Understand the patterns before considering cleanup.'] : t < 8 ? ['SENDER RANKINGS', 'A frequent sender is a starting point, not a verdict.'] : t < 11 ? ['CANDIDATE SIGNALS', 'A suggestion is not a command.'] : ['YOUR REVIEW BOUNDARY', 'No approval is shown. Organize stays inactive.'];
  return <AbsoluteFill>
    <div style={{position: 'absolute', top: 42, left: 86, right: 86, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 17, color: '#9eb2cd'}}><span style={{letterSpacing: 2}}>GMAIL CLEANUP AGENT <span style={{margin: '0 20px', color: '#577394'}}>/</span> MEET THE AGENT</span><span style={{border: '1px solid #415671', padding: '10px 16px', borderRadius: 7}}>YOUR REPORT RECORDING</span></div>
    <div className="display" style={{position: 'absolute', top: 111, left: 87, fontSize: 65, lineHeight: 1.2, opacity: arrival, transform: `translateY(${22 * (1 - arrival)}px)`}}>Suggestions first. <span style={{color: amber}}>Your decision next.</span></div>
    <div style={{position: 'absolute', left: 90, right: 90, top: 208, display: 'flex', justifyContent: 'space-between', fontSize: 17, letterSpacing: 1, color: '#a8bdd7'}}><span>REAL REPORT OUTPUT / {captions[0]}</span><span>{t < 4 ? 'OVERVIEW HELD FOR READABILITY' : 'EDITED EXCERPTS · NORMAL PLAYBACK SPEED'}</span></div>

    <div style={{position: 'absolute', left: 184, top: 250, width: 1552, height: 568, background: '#edf1f7', border: '1px solid #57667d', borderRadius: 15, overflow: 'hidden', boxShadow: '0 24px 75px #0006', opacity: arrival, transform: `translateY(${38 * (1 - arrival)}px)`}}>
      <Sequence durationInFrames={240} layout="none"><Img src={staticFile('report-overview.png')} style={{position: 'absolute', width: 1552, height: 717.9, left: 0, top: 0}}/></Sequence>
      <Sequence from={240} durationInFrames={240} layout="none"><Video src={staticFile('report-senders.mp4')} muted objectFit="fill" style={{position: 'absolute', width: 1552, height: 717.9, left: 0, top: 0}}/></Sequence>
      <Sequence from={480} durationInFrames={480} layout="none"><Video src={staticFile('report-safe.mp4')} trimBefore={480} muted objectFit="fill" style={{position: 'absolute', width: 1552, height: 717.9, left: 0, top: 0}}/></Sequence>
    </div>
    <div style={{position: 'absolute', left: 90, right: 90, top: 844, display: 'flex', justifyContent: 'space-between', fontSize: 19}}><span style={{color: t >= 11 ? amber : '#b5c9e1'}}>{captions[1]}</span><span style={{color: '#8ba1bf', fontSize: 16}}>Editorial workflow below, not product controls.</span></div>

    <div style={{position: 'absolute', left: 90, right: 90, top: 905, display: 'flex', alignItems: 'center'}}>
      {['Analyze', 'Identify', 'Suggest', 'Review', 'Organize'].map((name, i) => {
        const entry = enter(t, .65 + i * .11, 1.15 + i * .11);
        const lit = i < 3 ? enter(t, [2, 5, 8][i], [2.45, 5.45, 8.45][i]) : 0;
        const color = i === 3 ? amber : i === 4 ? '#6c7d93' : lit > 0 ? blue : '#7e92ab';
        const review = i === 3 && t >= 11;
        return <div key={name} style={{display: 'flex', alignItems: 'center', flex: i === 4 ? '0 0 252px' : 1, opacity: entry, transform: `translateY(${18 * (1 - entry)}px)`}}>
          <div style={{display: 'flex', gap: 13, alignItems: 'center', color}}><div style={{width: 47, height: 47, borderRadius: 25, display: 'grid', placeItems: 'center', fontSize: 17, border: `1px solid ${color}`, background: i === 3 ? '#3c3122' : `rgba(80,137,215,${lit * .18})`, boxShadow: review ? '0 0 0 5px #ffd08614' : 'none'}}>{i === 4 ? <Lock/> : `0${i + 1}`}</div><div style={{fontSize: 26, fontWeight: 500}}>{name}</div></div>
          {i < 4 && <div style={{flex: 1, height: 1, background: '#33465f', margin: '0 25px', position: 'relative'}}><div style={{width: `${lit * 100}%`, height: 1, background: blue}}/></div>}
        </div>;
      })}
    </div>
    <div style={{position: 'absolute', bottom: 40, left: 90, right: 90, display: 'flex', justifyContent: 'space-between', fontSize: 17, color: '#8fa7c5'}}><span>Report estimates are not Google quota or a recovery forecast.</span><span style={{color: amber}}>Review first. No cleanup action shown.</span></div>
  </AbsoluteFill>;
};

const Handoff = () => {
  const t = useCurrentFrame() / useVideoConfig().fps;
  return <AbsoluteFill style={{padding: '0 144px', justifyContent: 'center'}}>
    <div style={{fontSize: 19, letterSpacing: 3, color: blue, marginBottom: 34}}>NEXT / UNDER THE HOOD</div>
    <div className="display" style={{fontSize: 98, lineHeight: 1.15, opacity: enter(t, 0, .2), transform: `translateY(${24 * (1 - enter(t, 0, .5))}px)`}}>Here&apos;s what I actually<br/>built <span style={{color: amber}}>underneath.</span></div>
    <div style={{marginTop: 47, width: 110 * enter(t, .2, .75), height: 3, background: amber}}/>
    <div style={{position: 'absolute', bottom: 58, left: 144, fontSize: 18, color: '#94acca'}}>GMAIL CLEANUP AGENT</div>
  </AbsoluteFill>;
};

export const GmailReportReveal = ({audio = true}: {audio?: boolean}) => <AbsoluteFill className="film" style={{background: 'radial-gradient(ellipse at 85% 70%,#1c3653,#0a1422 70%)'}}>
  <Sequence durationInFrames={960}><ReportScene/></Sequence>
  <Sequence from={960} durationInFrames={180}><Handoff/></Sequence>
  {audio && <><Audio src={staticFile('audio/report-music.wav')}/><Audio src={staticFile('audio/report-sfx.wav')}/></>}
</AbsoluteFill>;
